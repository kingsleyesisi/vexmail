"""
IMAP Manager with connection pooling and IDLE support
"""
import imaplib
import threading
import time
import logging
from typing import Optional, Dict, List, Any
from queue import Queue, Empty
from contextlib import contextmanager
from decouple import config
import email
from email.header import decode_header
import json
from datetime import datetime
import uuid

from redis_client import redis_client

logger = logging.getLogger(__name__)

class IMAPConnection:
    """Individual IMAP connection wrapper"""
    
    def __init__(self, server: str, username: str, password: str, mailbox: str = 'INBOX'):
        self.server = server
        self.username = username
        self.password = password
        self.mailbox = mailbox
        self.connection: Optional[imaplib.IMAP4_SSL] = None
        self.last_used = time.time()
        self.is_idle = False
        self.lock = threading.Lock()
        
    def connect(self) -> bool:
        """Establish IMAP connection"""
        try:
            with self.lock:
                if self.connection:
                    try:
                        self.connection.logout()
                    except:
                        pass
                
                self.connection = imaplib.IMAP4_SSL(self.server)
                self.connection.login(self.username, self.password)
                self.connection.select(self.mailbox)
                self.last_used = time.time()
                logger.info(f"IMAP connection established for {self.username}")
                return True
        except Exception as e:
            logger.error(f"IMAP connection failed for {self.username}: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from IMAP server"""
        try:
            with self.lock:
                if self.connection:
                    if self.is_idle:
                        self.connection.done()
                        self.is_idle = False
                    self.connection.logout()
                    self.connection = None
        except Exception as e:
            logger.error(f"IMAP disconnect error: {e}")
    
    def is_connected(self) -> bool:
        """Check if connection is active"""
        try:
            with self.lock:
                if not self.connection:
                    return False
                # Test connection with a simple command
                self.connection.noop()
                return True
        except:
            return False
    
    def get_connection(self) -> Optional[imaplib.IMAP4_SSL]:
        """Get the IMAP connection (thread-safe)"""
        with self.lock:
            if self.is_connected():
                self.last_used = time.time()
                return self.connection
            return None

class IMAPConnectionPool:
    """Pool of IMAP connections"""
    
    def __init__(self, server: str, username: str, password: str, 
                 max_connections: int = 5, mailbox: str = 'INBOX'):
        self.server = server
        self.username = username
        self.password = password
        self.max_connections = max_connections
        self.mailbox = mailbox
        
        self.connections: List[IMAPConnection] = []
        self.available_connections = Queue(maxsize=max_connections)
        self.lock = threading.Lock()
        
        # Initialize connections
        for _ in range(max_connections):
            conn = IMAPConnection(server, username, password, mailbox)
            if conn.connect():
                self.connections.append(conn)
                self.available_connections.put(conn)
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        conn = None
        try:
            # Try to get an available connection
            try:
                conn = self.available_connections.get(timeout=10)
            except Empty:
                # Create a temporary connection if pool is empty
                conn = IMAPConnection(self.server, self.username, self.password, self.mailbox)
                if not conn.connect():
                    raise Exception("Failed to create temporary IMAP connection")
            
            yield conn
        finally:
            if conn:
                if conn.is_connected():
                    self.available_connections.put(conn)
                else:
                    # Connection is bad, try to reconnect
                    if conn.connect():
                        self.available_connections.put(conn)
    
    def cleanup_stale_connections(self):
        """Remove stale connections and create new ones"""
        with self.lock:
            current_time = time.time()
            stale_connections = []
            
            for conn in self.connections:
                if not conn.is_connected() or (current_time - conn.last_used) > 1800:  # 30 minutes
                    stale_connections.append(conn)
            
            for conn in stale_connections:
                conn.disconnect()
                self.connections.remove(conn)
                
                # Create replacement connection
                new_conn = IMAPConnection(self.server, self.username, self.password, self.mailbox)
                if new_conn.connect():
                    self.connections.append(new_conn)
                    self.available_connections.put(new_conn)

class IMAPManager:
    """Main IMAP Manager with IDLE support"""
    
    def __init__(self):
        self.server = config('IMAP_SERVER')
        self.username = config('EMAIL_USER')
        self.password = config('EMAIL_PASS')
        self.mailbox = config('IMAP_MAILBOX', default='INBOX')
        
        self.connection_pool = IMAPConnectionPool(
            self.server, self.username, self.password, 
            max_connections=3, mailbox=self.mailbox
        )
        
        self.idle_thread: Optional[threading.Thread] = None
        self.idle_running = False
        self.idle_lock = threading.Lock()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
    
    def _cleanup_loop(self):
        """Background cleanup of stale connections"""
        while True:
            try:
                time.sleep(300)  # Run every 5 minutes
                self.connection_pool.cleanup_stale_connections()
            except Exception as e:
                logger.error(f"Connection cleanup error: {e}")
    
    def start_idle(self):
        """Start IDLE monitoring for new emails"""
        with self.idle_lock:
            if self.idle_running:
                return
            
            self.idle_running = True
            self.idle_thread = threading.Thread(target=self._idle_loop, daemon=True)
            self.idle_thread.start()
            logger.info("IDLE monitoring started")
    
    def stop_idle(self):
        """Stop IDLE monitoring"""
        with self.idle_lock:
            self.idle_running = False
            if self.idle_thread:
                self.idle_thread.join(timeout=5)
            logger.info("IDLE monitoring stopped")
    
    def _idle_loop(self):
        """IDLE monitoring loop"""
        conn = None
        while self.idle_running:
            try:
                with self.connection_pool.get_connection() as connection:
                    conn = connection
                    imap_conn = conn.get_connection()
                    if not imap_conn:
                        time.sleep(5)
                        continue
                    
                    # Start IDLE
                    imap_conn.idle()
                    conn.is_idle = True
                    
                    # Wait for responses
                    while self.idle_running:
                        try:
                            responses = imap_conn.response('IDLE')
                            if responses:
                                # New email detected
                                self._handle_new_email()
                                break
                        except imaplib.IMAP4.abort:
                            # Connection lost, break to reconnect
                            break
                        
                        time.sleep(1)
                    
                    # End IDLE
                    if conn.is_idle:
                        imap_conn.done()
                        conn.is_idle = False
                
            except Exception as e:
                logger.error(f"IDLE error: {e}")
                if conn and conn.is_idle:
                    try:
                        conn.connection.done()
                        conn.is_idle = False
                    except:
                        pass
                time.sleep(10)  # Wait before retry
    
    def _handle_new_email(self):
        """Handle new email notification"""
        try:
            # Publish event to Redis
            redis_client.publish_imap_event('new_email', {
                'timestamp': datetime.utcnow().isoformat(),
                'server': self.server,
                'mailbox': self.mailbox
            })
            logger.info("New email detected via IDLE")
        except Exception as e:
            logger.error(f"Error handling new email: {e}")
    
    def fetch_emails(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """Fetch emails from IMAP server"""
        emails = []
        try:
            with self.connection_pool.get_connection() as conn:
                imap_conn = conn.get_connection()
                if not imap_conn:
                    raise Exception("No active IMAP connection")
                
                # Search for emails
                status, messages = imap_conn.search(None, 'ALL')
                if status != 'OK':
                    raise Exception(f"IMAP search failed: {status}")
                
                message_ids = messages[0].split()
                total = len(message_ids)
                
                if total == 0:
                    return emails
                
                # Get recent emails (highest IDs first)
                start_idx = max(0, total - offset - limit)
                end_idx = total - offset
                recent_ids = message_ids[start_idx:end_idx][::-1]
                
                for eid in recent_ids:
                    try:
                        uid = eid.decode()
                        
                        # Fetch email
                        status, msg_data = imap_conn.fetch(eid, '(RFC822 FLAGS)')
                        if status != 'OK':
                            continue
                        
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        
                        # Parse email
                        email_data = self._parse_email(msg, uid)
                        if email_data:
                            emails.append(email_data)
                            
                    except Exception as e:
                        logger.error(f"Error processing email {eid}: {e}")
                        continue
                
                logger.info(f"Fetched {len(emails)} emails from IMAP")
                return emails
                
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return emails
    
    def _parse_email(self, msg: email.message.Message, uid: str) -> Optional[Dict]:
        """Parse email message into structured data"""
        try:
            # Extract headers
            subject_hdr = decode_header(msg.get("Subject", ""))
            from_hdr = decode_header(msg.get("From", ""))
            to_hdr = decode_header(msg.get("To", ""))
            date_hdr = msg.get("Date", "")
            
            subject = self._decode_header_part(subject_hdr[0]) if subject_hdr else ""
            sender = self._decode_header_part(from_hdr[0]) if from_hdr else ""
            recipient = self._decode_header_part(to_hdr[0]) if to_hdr else ""
            
            # Extract email address
            email_address = self._extract_email_from_string(sender)
            sender_name = sender.replace(f'<{email_address}>', '').strip()
            if not sender_name:
                sender_name = email_address
            
            # Parse date
            try:
                date_obj = email.utils.parsedate_to_datetime(date_hdr)
            except:
                date_obj = datetime.utcnow()
            
            # Get email body
            body = self._get_email_body(msg)
            
            # Check if read
            flags = msg.get('X-Gmail-Labels', '')  # Gmail specific
            is_read = '\\Seen' in flags or 'UNREAD' not in flags
            
            return {
                'id': uid,
                'uid_validity': str(int(time.time())),  # Using timestamp for reliability
                'subject': subject,
                'sender_name': sender_name,
                'sender_email': email_address,
                'recipient': recipient,
                'body': body,
                'date': date_obj.isoformat(),
                'is_read': is_read,
                'raw_headers': dict(msg.items())
            }
            
        except Exception as e:
            logger.error(f"Error parsing email {uid}: {e}")
            return None
    
    def _decode_header_part(self, header_part) -> str:
        """Decode header part to UTF-8"""
        decoded, encoding = header_part
        if isinstance(decoded, bytes):
            return decoded.decode(encoding or "utf-8", errors="ignore")
        return decoded
    
    def _extract_email_from_string(self, email_string: str) -> str:
        """Extract email address from string like 'John Doe <john@example.com>'"""
        import re
        email_pattern = r'<(.+?)>'
        match = re.search(email_pattern, email_string)
        if match:
            return match.group(1)
        return email_string
    
    def _get_email_body(self, msg: email.message.Message) -> str:
        """Extract email body content"""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        body = part.get_payload(decode=True).decode(charset, errors="ignore")
                    except (UnicodeDecodeError, AttributeError):
                        body = part.get_payload(decode=True).decode("latin-1", errors="ignore")
                    break
        else:
            try:
                charset = msg.get_content_charset() or "utf-8"
                body = msg.get_payload(decode=True).decode(charset, errors="ignore")
            except (UnicodeDecodeError, AttributeError):
                body = msg.get_payload(decode=True).decode("latin-1", errors="ignore")
        return body
    
    def execute_operation(self, operation_type: str, email_uid: str, **kwargs) -> bool:
        """Execute IMAP operation (read, unread, delete)"""
        try:
            with self.connection_pool.get_connection() as conn:
                imap_conn = conn.get_connection()
                if not imap_conn:
                    return False
                
                if operation_type == 'read':
                    status, data = imap_conn.uid('STORE', email_uid, '+FLAGS', '(\\Seen)')
                elif operation_type == 'unread':
                    status, data = imap_conn.uid('STORE', email_uid, '-FLAGS', '(\\Seen)')
                elif operation_type == 'delete':
                    status, data = imap_conn.uid('STORE', email_uid, '+FLAGS', '(\\Deleted)')
                    if status == 'OK':
                        status, data = imap_conn.expunge()
                else:
                    return False
                
                return status == 'OK'
                
        except Exception as e:
            logger.error(f"Error executing IMAP operation {operation_type} on {email_uid}: {e}")
            return False

# Global IMAP manager instance
imap_manager = IMAPManager()
