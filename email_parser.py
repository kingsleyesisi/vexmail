"""
Email parser and sanitizer module
"""
import email
import re
import html
import logging
from typing import Dict, List, Optional, Any, Tuple
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import base64
import hashlib
import uuid
from datetime import datetime
import mimetypes

logger = logging.getLogger(__name__)

class EmailParser:
    """Advanced email parsing and sanitization"""
    
    def __init__(self):
        self.suspicious_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'onclick\s*=',
            r'onload\s*=',
            r'onerror\s*=',
            r'<iframe[^>]*>.*?</iframe>',
            r'<object[^>]*>.*?</object>',
            r'<embed[^>]*>.*?</embed>',
            r'<form[^>]*>.*?</form>',
            r'<input[^>]*>',
            r'<textarea[^>]*>.*?</textarea>',
            r'<select[^>]*>.*?</select>',
        ]
        
        self.url_patterns = [
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            r'www\.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
        ]
    
    def parse_email(self, raw_email: bytes) -> Dict[str, Any]:
        """Parse raw email into structured data"""
        try:
            msg = email.message_from_bytes(raw_email)
            
            # Extract basic information
            parsed = {
                'id': self._generate_email_id(msg),
                'headers': self._extract_headers(msg),
                'subject': self._extract_subject(msg),
                'from': self._extract_from(msg),
                'to': self._extract_to(msg),
                'cc': self._extract_cc(msg),
                'bcc': self._extract_bcc(msg),
                'date': self._extract_date(msg),
                'message_id': msg.get('Message-ID', ''),
                'references': self._extract_references(msg),
                'in_reply_to': msg.get('In-Reply-To', ''),
                'thread_id': self._extract_thread_id(msg),
                'body': self._extract_body(msg),
                'attachments': self._extract_attachments(msg),
                'html_content': self._extract_html_content(msg),
                'text_content': self._extract_text_content(msg),
                'priority': self._extract_priority(msg),
                'importance': self._extract_importance(msg),
                'security_info': self._extract_security_info(msg),
                'size': len(raw_email),
                'parsed_at': datetime.utcnow().isoformat()
            }
            
            # Sanitize content
            parsed['body'] = self.sanitize_content(parsed['body'])
            parsed['html_content'] = self.sanitize_html(parsed['html_content'])
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing email: {e}")
            return {}
    
    def _generate_email_id(self, msg: email.message.Message) -> str:
        """Generate unique email ID"""
        message_id = msg.get('Message-ID', '')
        if message_id:
            # Use message ID hash for consistency
            return hashlib.md5(message_id.encode()).hexdigest()
        else:
            # Fallback to UUID
            return str(uuid.uuid4())
    
    def _extract_headers(self, msg: email.message.Message) -> Dict[str, str]:
        """Extract all email headers"""
        headers = {}
        for header, value in msg.items():
            try:
                decoded_value = self._decode_header(value)
                headers[header.lower()] = decoded_value
            except:
                headers[header.lower()] = str(value)
        return headers
    
    def _extract_subject(self, msg: email.message.Message) -> str:
        """Extract and decode subject"""
        subject = msg.get('Subject', '')
        if subject:
            return self._decode_header(subject)
        return '(No Subject)'
    
    def _extract_from(self, msg: email.message.Message) -> Dict[str, str]:
        """Extract sender information"""
        from_header = msg.get('From', '')
        return self._parse_email_address(from_header)
    
    def _extract_to(self, msg: email.message.Message) -> List[Dict[str, str]]:
        """Extract recipient information"""
        to_header = msg.get('To', '')
        return self._parse_email_addresses(to_header)
    
    def _extract_cc(self, msg: email.message.Message) -> List[Dict[str, str]]:
        """Extract CC recipients"""
        cc_header = msg.get('Cc', '')
        return self._parse_email_addresses(cc_header)
    
    def _extract_bcc(self, msg: email.message.Message) -> List[Dict[str, str]]:
        """Extract BCC recipients"""
        bcc_header = msg.get('Bcc', '')
        return self._parse_email_addresses(bcc_header)
    
    def _extract_date(self, msg: email.message.Message) -> str:
        """Extract and parse date"""
        date_header = msg.get('Date', '')
        try:
            date_obj = email.utils.parsedate_to_datetime(date_header)
            return date_obj.isoformat()
        except:
            return datetime.utcnow().isoformat()
    
    def _extract_references(self, msg: email.message.Message) -> List[str]:
        """Extract message references"""
        references = msg.get('References', '')
        if references:
            return [ref.strip() for ref in references.split() if ref.strip()]
        return []
    
    def _extract_thread_id(self, msg: email.message.Message) -> str:
        """Extract or generate thread ID"""
        # Try to use In-Reply-To or References for threading
        in_reply_to = msg.get('In-Reply-To', '')
        if in_reply_to:
            return hashlib.md5(in_reply_to.encode()).hexdigest()
        
        references = msg.get('References', '')
        if references:
            refs = [ref.strip() for ref in references.split() if ref.strip()]
            if refs:
                return hashlib.md5(refs[0].encode()).hexdigest()
        
        # Fallback to subject-based threading
        subject = self._extract_subject(msg)
        if subject.startswith('Re:') or subject.startswith('Fwd:'):
            clean_subject = re.sub(r'^(Re:|Fwd:)\s*', '', subject, flags=re.IGNORECASE)
            return hashlib.md5(clean_subject.encode()).hexdigest()
        
        return hashlib.md5(subject.encode()).hexdigest()
    
    def _extract_body(self, msg: email.message.Message) -> str:
        """Extract main email body"""
        html_content = self._extract_html_content(msg)
        text_content = self._extract_text_content(msg)
        
        # Prefer text content, fallback to HTML
        if text_content:
            return text_content
        elif html_content:
            return self._html_to_text(html_content)
        else:
            return ""
    
    def _extract_html_content(self, msg: email.message.Message) -> str:
        """Extract HTML content from email"""
        html_content = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        html_content = part.get_payload(decode=True).decode(charset, errors="ignore")
                        break
                    except:
                        continue
        else:
            if msg.get_content_type() == "text/html":
                try:
                    charset = msg.get_content_charset() or "utf-8"
                    html_content = msg.get_payload(decode=True).decode(charset, errors="ignore")
                except:
                    pass
        
        return html_content
    
    def _extract_text_content(self, msg: email.message.Message) -> str:
        """Extract plain text content from email"""
        text_content = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        text_content = part.get_payload(decode=True).decode(charset, errors="ignore")
                        break
                    except:
                        continue
        else:
            if msg.get_content_type() == "text/plain":
                try:
                    charset = msg.get_content_charset() or "utf-8"
                    text_content = msg.get_payload(decode=True).decode(charset, errors="ignore")
                except:
                    pass
        
        return text_content
    
    def _extract_attachments(self, msg: email.message.Message) -> List[Dict[str, Any]]:
        """Extract attachment information"""
        attachments = []
        
        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = part.get('Content-Disposition', '')
                content_type = part.get_content_type()
                
                if 'attachment' in content_disposition or (
                    content_type and not content_type.startswith('text/') and 
                    not content_type.startswith('multipart/')
                ):
                    try:
                        filename = part.get_filename()
                        if not filename:
                            filename = f"attachment_{len(attachments)}"
                        
                        # Decode filename
                        filename = self._decode_header(filename)
                        
                        attachment = {
                            'filename': filename,
                            'content_type': content_type,
                            'size': len(part.get_payload(decode=True) or b''),
                            'content_id': part.get('Content-ID', ''),
                            'content_disposition': content_disposition,
                            'checksum': self._calculate_checksum(part.get_payload(decode=True) or b'')
                        }
                        
                        attachments.append(attachment)
                        
                    except Exception as e:
                        logger.error(f"Error extracting attachment: {e}")
        
        return attachments
    
    def _extract_priority(self, msg: email.message.Message) -> str:
        """Extract email priority"""
        priority = msg.get('X-Priority', '')
        importance = msg.get('Importance', '')
        
        if 'high' in priority.lower() or 'urgent' in importance.lower():
            return 'high'
        elif 'low' in priority.lower() or 'low' in importance.lower():
            return 'low'
        else:
            return 'normal'
    
    def _extract_importance(self, msg: email.message.Message) -> str:
        """Extract importance level"""
        importance = msg.get('Importance', '')
        if importance:
            return importance.lower()
        return 'normal'
    
    def _extract_security_info(self, msg: email.message.Message) -> Dict[str, Any]:
        """Extract security-related information"""
        security_info = {
            'is_encrypted': False,
            'is_signed': False,
            'has_dkim': False,
            'has_spf': False,
            'authentication_results': []
        }
        
        # Check for encryption/signing
        content_type = msg.get_content_type()
        if 'application/pkcs7-mime' in content_type or 'multipart/encrypted' in content_type:
            security_info['is_encrypted'] = True
        
        if 'multipart/signed' in content_type:
            security_info['is_signed'] = True
        
        # Check headers for authentication
        auth_results = msg.get('Authentication-Results', '')
        if auth_results:
            security_info['authentication_results'] = auth_results.split(';')
            
            if 'dkim=pass' in auth_results:
                security_info['has_dkim'] = True
            if 'spf=pass' in auth_results:
                security_info['has_spf'] = True
        
        return security_info
    
    def _decode_header(self, header_value: str) -> str:
        """Decode email header value"""
        try:
            decoded_parts = decode_header(header_value)
            decoded_string = ""
            
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_string += part.decode(encoding, errors="ignore")
                    else:
                        decoded_string += part.decode('utf-8', errors="ignore")
                else:
                    decoded_string += part
            
            return decoded_string
        except:
            return str(header_value)
    
    def _parse_email_address(self, address_string: str) -> Dict[str, str]:
        """Parse email address string into name and email"""
        if not address_string:
            return {'name': '', 'email': ''}
        
        # Pattern: "Name <email@domain.com>" or just "email@domain.com"
        pattern = r'^(.*?)\s*<([^>]+)>$'
        match = re.match(pattern, address_string.strip())
        
        if match:
            name = match.group(1).strip().strip('"')
            email = match.group(2).strip()
        else:
            name = ""
            email = address_string.strip()
        
        return {
            'name': name or email,
            'email': email
        }
    
    def _parse_email_addresses(self, addresses_string: str) -> List[Dict[str, str]]:
        """Parse multiple email addresses"""
        if not addresses_string:
            return []
        
        # Split by comma and parse each
        addresses = []
        for addr in addresses_string.split(','):
            addr = addr.strip()
            if addr:
                addresses.append(self._parse_email_address(addr))
        
        return addresses
    
    def _calculate_checksum(self, data: bytes) -> str:
        """Calculate checksum for data"""
        return hashlib.sha256(data).hexdigest()
    
    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML to plain text"""
        try:
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', '', html_content)
            # Decode HTML entities
            text = html.unescape(text)
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        except:
            return html_content
    
    def sanitize_content(self, content: str) -> str:
        """Sanitize email content"""
        if not content:
            return content
        
        # Remove suspicious patterns
        for pattern in self.suspicious_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.DOTALL)
        
        # Decode HTML entities
        content = html.unescape(content)
        
        # Clean up extra whitespace
        content = re.sub(r'\s+', ' ', content).strip()
        
        return content
    
    def sanitize_html(self, html_content: str) -> str:
        """Sanitize HTML content"""
        if not html_content:
            return html_content
        
        # Remove dangerous tags and attributes
        dangerous_tags = ['script', 'object', 'embed', 'iframe', 'form', 'input', 'textarea', 'select']
        dangerous_attrs = ['onclick', 'onload', 'onerror', 'onmouseover', 'onfocus', 'onblur']
        
        for tag in dangerous_tags:
            html_content = re.sub(f'<{tag}[^>]*>.*?</{tag}>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
            html_content = re.sub(f'<{tag}[^>]*/?>', '', html_content, flags=re.IGNORECASE)
        
        for attr in dangerous_attrs:
            html_content = re.sub(f'\\s{attr}\\s*=\\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
        
        # Remove javascript: URLs
        html_content = re.sub(r'href\s*=\s*["\']javascript:[^"\']*["\']', 'href="#"', html_content, flags=re.IGNORECASE)
        
        return html_content
    
    def extract_urls(self, content: str) -> List[str]:
        """Extract URLs from content"""
        urls = []
        for pattern in self.url_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            urls.extend(matches)
        return list(set(urls))  # Remove duplicates
    
    def is_suspicious_email(self, parsed_email: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Check if email is suspicious and return reasons"""
        reasons = []
        
        # Check for suspicious content
        body = parsed_email.get('body', '')
        html_content = parsed_email.get('html_content', '')
        
        for pattern in self.suspicious_patterns:
            if re.search(pattern, body, re.IGNORECASE | re.DOTALL):
                reasons.append(f"Suspicious pattern in body: {pattern}")
            if re.search(pattern, html_content, re.IGNORECASE | re.DOTALL):
                reasons.append(f"Suspicious pattern in HTML: {pattern}")
        
        # Check for excessive URLs
        urls = self.extract_urls(body + html_content)
        if len(urls) > 5:
            reasons.append(f"Excessive URLs found: {len(urls)}")
        
        # Check for suspicious sender patterns
        from_info = parsed_email.get('from', {})
        sender_email = from_info.get('email', '').lower()
        
        if not sender_email or '@' not in sender_email:
            reasons.append("Invalid sender email address")
        
        # Check for suspicious domains
        suspicious_domains = ['bit.ly', 'tinyurl.com', 'short.link', 'goo.gl']
        for url in urls:
            for domain in suspicious_domains:
                if domain in url.lower():
                    reasons.append(f"Suspicious URL shortening service: {domain}")
        
        return len(reasons) > 0, reasons

# Global email parser instance
email_parser = EmailParser()
