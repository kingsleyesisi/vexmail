"""
Email Sync Service - Handles email fetching, caching, and database storage
"""
import logging
import json
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from decouple import config

from flask import current_app
from sqlalchemy.exc import IntegrityError
from models import db, Email, EmailAttachment, User
from imap_manager import imap_manager
from email_parser import email_parser
from storage_client import storage_client

logger = logging.getLogger(__name__)

class EmailSyncService:
    """Service for syncing emails from IMAP to database with caching"""
    
    def __init__(self):
        self.cache_prefix = "vexmail:email:"
        self.list_cache_prefix = "vexmail:email_list:"
        self.sync_interval = 600  # 10 minutes
        
    def generate_email_id(self, message_id: str, uid: str) -> str:
        """Generate a unique email ID from message ID and UID"""
        if message_id:
            return hashlib.md5(message_id.encode()).hexdigest()
        else:
            return hashlib.md5(f"{uid}_{datetime.utcnow().timestamp()}".encode()).hexdigest()
    
    def is_email_exists(self, email_id: str) -> bool:
        """Check if email exists in database"""
        try:
            return Email.query.filter_by(id=email_id).first() is not None
        except Exception as e:
            logger.error(f"Error checking email existence: {e}")
            return False
    
    def get_cached_emails(self, page: int = 1, per_page: int = 20) -> Optional[Dict]:
        """Get emails from Redis cache"""
        from app import cache
        try:
            cache_key = f"{self.list_cache_prefix}page:{page}:per_page:{per_page}"
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        except Exception as e:
            logger.error(f"Error getting cached emails: {e}")
        return None
    
    def cache_emails(self, emails_data: Dict, page: int = 1, per_page: int = 20, expire: int = 300):
        """Cache emails list in Redis"""
        from app import cache
        try:
            cache_key = f"{self.list_cache_prefix}page:{page}:per_page:{per_page}"
            cache.set(cache_key, emails_data, timeout=expire)
        except Exception as e:
            logger.error(f"Error caching emails: {e}")
    
    def get_cached_email_detail(self, email_id: str) -> Optional[Dict]:
        """Get email detail from Redis cache"""
        from app import cache
        try:
            cache_key = f"{self.cache_prefix}detail:{email_id}"
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        except Exception as e:
            logger.error(f"Error getting cached email detail: {e}")
        return None
    
    def cache_email_detail(self, email_id: str, email_data: Dict, expire: int = 3600):
        """Cache email detail in Redis"""
        from app import cache
        try:
            cache_key = f"{self.cache_prefix}detail:{email_id}"
            cache.set(cache_key, email_data, timeout=expire)
        except Exception as e:
            logger.error(f"Error caching email detail: {e}")
    
    def store_email_safely(self, email_data: Dict) -> Optional[Email]:
        """Store email in database with duplicate prevention"""
        try:
            # Generate unique email ID
            email_id = self.generate_email_id(
                email_data.get('message_id', ''), 
                email_data.get('uid', '')
            )
            
            # Check if email already exists
            if self.is_email_exists(email_id):
                logger.debug(f"Email {email_id} already exists, skipping")
                return Email.query.get(email_id)
            
            # Parse email content
            parsed_email = email_parser.parse_email(email_data.get('raw_content', ''))
            if not parsed_email:
                logger.error("Failed to parse email content")
                return None
            
            # Check if email is suspicious
            is_suspicious, reasons = email_parser.is_suspicious_email(parsed_email)
            
            # Create email record
            email_record = Email(
                id=email_id,
                uid_validity=email_data.get('uid_validity', str(int(datetime.utcnow().timestamp()))),
                message_id=email_data.get('message_id', ''),
                subject=parsed_email.get('subject', ''),
                sender_name=parsed_email.get('from', {}).get('name', ''),
                sender_email=parsed_email.get('from', {}).get('email', ''),
                recipient=email_data.get('recipient', ''),
                body=parsed_email.get('body', ''),
                html_content=parsed_email.get('html_content', ''),
                text_content=parsed_email.get('text_content', ''),
                date=datetime.fromisoformat(parsed_email.get('date', datetime.utcnow().isoformat())),
                size=email_data.get('size', 0),
                priority=parsed_email.get('priority', 'normal'),
                is_read=email_data.get('is_read', False),
                is_deleted=False,
                is_flagged=False,
                is_starred=False,
                thread_id=parsed_email.get('thread_id', ''),
                is_suspicious=is_suspicious,
                suspicious_reasons=json.dumps(reasons) if reasons else None,
                raw_headers=json.dumps(parsed_email.get('raw_headers', {})),
                attachments_info=json.dumps(parsed_email.get('attachments', [])),
                attachment_count=len(parsed_email.get('attachments', [])),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                synced_at=datetime.utcnow()
            )
            
            # Handle CC and BCC
            if parsed_email.get('cc'):
                email_record.cc = json.dumps(parsed_email['cc'])
            if parsed_email.get('bcc'):
                email_record.bcc = json.dumps(parsed_email['bcc'])
            
            # Save to database with duplicate handling
            try:
                db.session.add(email_record)
                db.session.commit()
                logger.info(f"Successfully stored email {email_id}")
                
                # Cache the email detail
                self.cache_email_detail(email_id, {
                    'id': email_record.id,
                    'subject': email_record.subject,
                    'from': email_record.sender_name,
                    'email': email_record.sender_email,
                    'body': email_record.body,
                    'html_content': email_record.html_content,
                    'date': email_record.date.strftime("%b %d, %Y %I:%M %p"),
                    'is_read': email_record.is_read,
                    'is_flagged': email_record.is_flagged,
                    'is_starred': email_record.is_starred,
                    'priority': email_record.priority,
                    'size': email_record.size,
                    'attachment_count': email_record.attachment_count,
                    'thread_id': email_record.thread_id,
                    'cc': email_record.get_cc_list(),
                    'bcc': email_record.get_bcc_list(),
                    'is_suspicious': email_record.is_suspicious,
                    'suspicious_reasons': email_record.get_suspicious_reasons()
                })
                
                # Invalidate email list cache
                self.invalidate_email_list_cache()
                
                # Process attachments
                if parsed_email.get('attachments'):
                    self.process_attachments(email_record, parsed_email['attachments'])
                
                return email_record
                
            except IntegrityError as e:
                db.session.rollback()
                logger.warning(f"Email {email_id} already exists (integrity error): {e}")
                return Email.query.get(email_id)
                
        except Exception as e:
            logger.error(f"Error storing email: {e}")
            db.session.rollback()
            return None
    
    def process_attachments(self, email_record: Email, attachments: List[Dict]):
        """Process email attachments and store them"""
        try:
            for attachment_data in attachments:
                try:
                    # Generate unique attachment ID
                    attachment_id = hashlib.md5(
                        f"{email_record.id}_{attachment_data.get('filename', '')}_{attachment_data.get('size', 0)}".encode()
                    ).hexdigest()
                    
                    # Check if attachment already exists
                    existing_attachment = EmailAttachment.query.filter_by(
                        email_id=email_record.id,
                        filename=attachment_data.get('filename', '')
                    ).first()
                    
                    if existing_attachment:
                        continue
                    
                    # Store attachment in local storage
                    if attachment_data.get('content'):
                        import base64
                        decoded_content = base64.b64decode(attachment_data['content'])
                        storage_result = storage_client.upload_attachment(
                            email_id=email_record.id,
                            filename=attachment_data.get('filename', 'unknown'),
                            content=decoded_content,
                            content_type=attachment_data.get('content_type', 'application/octet-stream'),
                            attachment_id=attachment_id
                        )
                        
                        # Create attachment record
                        attachment_record = EmailAttachment(
                            id=attachment_id,
                            email_id=email_record.id,
                            filename=attachment_data.get('filename', 'unknown'),
                            content_type=attachment_data.get('content_type', 'application/octet-stream'),
                            size=attachment_data.get('size', 0),
                            storage_path=storage_result.get('object_key', ''),
                            storage_provider='local',
                            checksum=storage_result.get('checksum', ''),
                            is_scanned=True,
                            is_safe=True,
                            created_at=datetime.utcnow()
                        )
                        
                        db.session.add(attachment_record)
                        
                except Exception as e:
                    logger.error(f"Error processing attachment: {e}")
                    continue
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error processing attachments: {e}")
            db.session.rollback()
    
    def fetch_emails_from_imap(self, limit: int = 50) -> List[Dict]:
        """Fetch emails from IMAP server"""
        try:
            # Use IMAP manager to fetch emails
            emails = imap_manager.fetch_emails(limit=limit)
            logger.info(f"Fetched {len(emails) if emails else 0} emails from IMAP")
            return emails or []
        except Exception as e:
            logger.error(f"Error fetching emails from IMAP: {e}")
            return []
    
    def sync_emails(self, limit: int = 50) -> Dict[str, Any]:
        """Main sync function - fetches and stores new emails"""
        try:
            logger.info(f"Starting email sync (limit: {limit})")
            
            # Fetch emails from IMAP
            emails = self.fetch_emails_from_imap(limit)
            
            if not emails:
                return {
                    'status': 'success',
                    'message': 'No emails found',
                    'count': 0,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            stored_count = 0
            skipped_count = 0
            
            for email_data in emails:
                try:
                    email_record = self.store_email_safely(email_data)
                    if email_record:
                        stored_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    logger.error(f"Error processing email: {e}")
                    skipped_count += 1
                    continue
            
            result = {
                'status': 'success',
                'message': f'Processed {len(emails)} emails',
                'count': stored_count,
                'skipped': skipped_count,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Sync completed: {stored_count} stored, {skipped_count} skipped")
            return result
            
        except Exception as e:
            logger.error(f"Error in email sync: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'count': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def get_emails_from_db(self, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Get emails from database with pagination and caching"""
        try:
            # Try cache first
            cached_emails = self.get_cached_emails(page, per_page)
            if cached_emails:
                return cached_emails
            
            # Fetch from database
            emails_query = Email.query.filter_by(is_deleted=False).order_by(Email.date.desc())
            emails = emails_query.paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            # Convert to dict format
            emails_list = []
            for email in emails.items:
                email_dict = {
                    'id': email.id,
                    'subject': email.subject,
                    'from': email.sender_name,
                    'email': email.sender_email,
                    'body': email.body,
                    'date': email.date.strftime("%b %d, %Y %I:%M %p") if email.date else '',
                    'preview': email.body[:150] + "..." if email.body and len(email.body) > 150 else (email.body or ''),
                    'is_read': email.is_read,
                    'is_flagged': email.is_flagged,
                    'is_starred': email.is_starred,
                    'priority': email.priority,
                    'size': email.size,
                    'attachment_count': email.attachment_count,
                    'thread_id': email.thread_id
                }
                emails_list.append(email_dict)
            
            result = {
                "pagination": {
                    "total": emails.total,
                    "pages": emails.pages,
                    "current_page": emails.page,
                    "per_page": emails.per_page
                },
                "emails": emails_list
            }
            
            # Cache the result
            self.cache_emails(result, page, per_page)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching emails from database: {e}")
            return {
                "pagination": {"total": 0, "pages": 0, "current_page": 1, "per_page": per_page},
                "emails": []
            }
    
    def get_email_detail(self, email_id: str) -> Optional[Dict]:
        """Get email detail with caching"""
        try:
            # Try cache first
            email_data = self.get_cached_email_detail(email_id)
            
            if not email_data:
                # Fetch from database
                email = Email.query.get(email_id)
                if not email:
                    return None

                email_data = email.to_dict()
                # Cache the result
                self.cache_email_detail(email_id, email_data)

            # Always fetch attachments from DB to ensure they are up-to-date
            attachments = EmailAttachment.query.filter_by(email_id=email_id).all()
            email_data['attachments'] = [attachment.to_dict() for attachment in attachments]
            
            return email_data
            
        except Exception as e:
            logger.error(f"Error getting email detail: {e}")
            return None
    
    def invalidate_email_list_cache(self):
        """Invalidate email list cache"""
        from app import cache
        try:
            cache.clear()
        except Exception as e:
            logger.error(f"Error invalidating email list cache: {e}")
    
    def start_background_sync(self):
        """Start background email sync every 10 minutes"""
        import threading
        import time
        
        def sync_worker():
            while True:
                try:
                    logger.info("Running background email sync...")
                    result = self.sync_emails(limit=100)
                    logger.info(f"Background sync result: {result}")
                except Exception as e:
                    logger.error(f"Error in background sync: {e}")
                
                # Wait 10 minutes
                time.sleep(self.sync_interval)
        
        # Start background thread
        sync_thread = threading.Thread(target=sync_worker, daemon=True)
        sync_thread.start()
        logger.info("Background email sync started")

# Global instance
email_sync_service = EmailSyncService()
