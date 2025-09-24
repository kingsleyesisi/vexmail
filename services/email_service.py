"""
Gmail-style Email Service
Handles email operations, caching, and real-time updates
"""
import logging
import hashlib
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, desc
from sqlalchemy.exc import IntegrityError

from models import db, Email, EmailThread, EmailAttachment, EmailLabel
from services.cache_service import cache_service
from services.realtime_service import realtime_service
from imap_manager import imap_manager
from email_parser import email_parser

logger = logging.getLogger(__name__)

class EmailService:
    """Gmail-style email service with intelligent caching and threading"""
    
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour for email details
        self.list_cache_ttl = 300  # 5 minutes for email lists
        
    def get_inbox_emails(self, page: int = 1, per_page: int = 50, label: str = 'inbox') -> Dict[str, Any]:
        """Get inbox emails with Gmail-style threading and caching"""
        cache_key = f"emails:inbox:{label}:page:{page}:per_page:{per_page}"
        
        # Try cache first
        cached_result = cache_service.get(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for inbox emails: {label}")
            return cached_result
        
        try:
            # Build query based on label
            query = self._build_email_query(label)
            
            # Apply pagination
            emails_paginated = query.paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            # Group emails by thread
            threaded_emails = self._group_emails_by_thread(emails_paginated.items)
            
            result = {
                'emails': threaded_emails,
                'pagination': {
                    'total': emails_paginated.total,
                    'pages': emails_paginated.pages,
                    'current_page': page,
                    'per_page': per_page,
                    'has_next': emails_paginated.has_next,
                    'has_prev': emails_paginated.has_prev
                },
                'label': label,
                'cached_at': datetime.utcnow().isoformat()
            }
            
            # Cache the result
            cache_service.set(cache_key, result, ttl=self.list_cache_ttl)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching inbox emails: {e}")
            return self._empty_result(page, per_page, label)
    
    def get_email_detail(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed email content with attachments"""
        cache_key = f"email:detail:{email_id}"
        
        # Try cache first
        cached_email = cache_service.get(cache_key)
        if cached_email:
            return cached_email
        
        try:
            email = Email.query.get(email_id)
            if not email:
                return None
            
            # Get email details with content
            email_data = email.to_dict(include_content=True)
            
            # Get attachments
            attachments = EmailAttachment.query.filter_by(email_id=email_id).all()
            email_data['attachments'] = [att.to_dict() for att in attachments]
            
            # Get thread emails if part of conversation
            if email.thread_id:
                thread_emails = self._get_thread_emails(email.thread_id, exclude_id=email_id)
                email_data['thread_emails'] = thread_emails
            
            # Cache the result
            cache_service.set(cache_key, email_data, ttl=self.cache_ttl)
            
            return email_data
            
        except Exception as e:
            logger.error(f"Error fetching email detail {email_id}: {e}")
            return None
    
    def search_emails(self, query: str, page: int = 1, per_page: int = 25) -> Dict[str, Any]:
        """Search emails with Gmail-style search operators"""
        cache_key = f"search:{hashlib.md5(query.encode()).hexdigest()}:page:{page}"
        
        # Try cache first
        cached_result = cache_service.get(cache_key)
        if cached_result:
            return cached_result
        
        try:
            # Parse search query for Gmail-style operators
            search_filters = self._parse_search_query(query)
            
            # Build search query
            email_query = self._build_search_query(search_filters)
            
            # Apply pagination
            emails_paginated = email_query.paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            # Convert to dict format
            emails_list = [email.to_dict() for email in emails_paginated.items]
            
            result = {
                'emails': emails_list,
                'pagination': {
                    'total': emails_paginated.total,
                    'pages': emails_paginated.pages,
                    'current_page': page,
                    'per_page': per_page
                },
                'query': query,
                'filters': search_filters,
                'cached_at': datetime.utcnow().isoformat()
            }
            
            # Cache search results for shorter time
            cache_service.set(cache_key, result, ttl=300)  # 5 minutes
            
            return result
            
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return self._empty_search_result(query, page, per_page)
    
    def sync_emails_from_server(self, limit: int = 50) -> Dict[str, Any]:
        """Sync emails from IMAP server with real-time notifications"""
        try:
            logger.info(f"Starting email sync (limit: {limit})")
            
            # Notify clients that sync is starting
            realtime_service.emit_sync_status('started', 'Syncing emails...', 0)
            
            # Fetch emails from IMAP
            raw_emails = imap_manager.fetch_emails(limit=limit)
            
            if not raw_emails:
                realtime_service.emit_sync_status('completed', 'No new emails', 100)
                return {'status': 'success', 'message': 'No new emails', 'count': 0}
            
            processed_count = 0
            new_count = 0
            
            for i, raw_email in enumerate(raw_emails):
                try:
                    # Update progress
                    progress = int((i + 1) / len(raw_emails) * 100)
                    realtime_service.emit_sync_status('syncing', f'Processing email {i+1}/{len(raw_emails)}', progress)
                    
                    # Process and store email
                    email = self._process_raw_email(raw_email)
                    if email:
                        processed_count += 1
                        if self._is_new_email(email):
                            new_count += 1
                            # Notify clients of new email
                            realtime_service.emit_email_received(email.to_dict())
                    
                except Exception as e:
                    logger.error(f"Error processing email {i}: {e}")
                    continue
            
            # Clear relevant caches
            self._invalidate_email_caches()
            
            # Notify completion
            realtime_service.emit_sync_status('completed', f'Synced {new_count} new emails', 100)
            
            return {
                'status': 'success',
                'message': f'Processed {processed_count} emails, {new_count} new',
                'count': new_count,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error syncing emails: {e}")
            realtime_service.emit_sync_status('error', f'Sync failed: {str(e)}', 0)
            return {'status': 'error', 'message': str(e), 'count': 0}
    
    def update_email_status(self, email_id: str, updates: Dict[str, Any]) -> bool:
        """Update email status (read, starred, etc.) with real-time updates"""
        try:
            email = Email.query.get(email_id)
            if not email:
                return False
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(email, key):
                    setattr(email, key, value)
            
            email.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Update thread status if needed
            if email.thread_id:
                self._update_thread_status(email.thread_id)
            
            # Clear caches
            cache_service.delete(f"email:detail:{email_id}")
            self._invalidate_email_caches()
            
            # Notify clients
            realtime_service.emit_email_updated(email_id, updates)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating email {email_id}: {e}")
            db.session.rollback()
            return False
    
    def move_to_label(self, email_ids: List[str], label: str) -> bool:
        """Move emails to a specific label (Gmail-style)"""
        try:
            for email_id in email_ids:
                email = Email.query.get(email_id)
                if email:
                    # Remove from current location
                    if label == 'trash':
                        email.is_deleted = True
                    elif label == 'spam':
                        email.is_spam = True
                    elif label == 'archive':
                        email.is_archived = True
                    else:
                        # Add to custom label
                        email.add_label(label)
                    
                    email.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # Clear caches and notify
            self._invalidate_email_caches()
            realtime_service.emit_emails_moved(email_ids, label)
            
            return True
            
        except Exception as e:
            logger.error(f"Error moving emails to {label}: {e}")
            db.session.rollback()
            return False
    
    def get_labels(self) -> List[Dict[str, Any]]:
        """Get all email labels with counts"""
        cache_key = "email:labels"
        
        cached_labels = cache_service.get(cache_key)
        if cached_labels:
            return cached_labels
        
        try:
            labels = EmailLabel.query.all()
            labels_data = []
            
            for label in labels:
                # Count emails for this label
                if label.is_system:
                    count = self._get_system_label_count(label.name)
                else:
                    count = self._get_custom_label_count(label.name)
                
                label_data = label.to_dict()
                label_data['email_count'] = count
                labels_data.append(label_data)
            
            # Cache for 5 minutes
            cache_service.set(cache_key, labels_data, ttl=300)
            
            return labels_data
            
        except Exception as e:
            logger.error(f"Error fetching labels: {e}")
            return []
    
    def _build_email_query(self, label: str):
        """Build SQLAlchemy query for specific label"""
        base_query = Email.query.filter_by(is_deleted=False)
        
        if label == 'inbox':
            return base_query.filter_by(is_archived=False, is_spam=False).order_by(desc(Email.date_received))
        elif label == 'starred':
            return base_query.filter_by(is_starred=True, is_archived=False).order_by(desc(Email.date_received))
        elif label == 'important':
            return base_query.filter_by(is_important=True, is_archived=False).order_by(desc(Email.date_received))
        elif label == 'sent':
            # This would need to be implemented based on your sent email storage
            return base_query.filter_by(is_archived=False).order_by(desc(Email.date_received))
        elif label == 'drafts':
            # This would need to be implemented for draft emails
            return base_query.filter_by(is_archived=False).order_by(desc(Email.date_received))
        elif label == 'archive':
            return base_query.filter_by(is_archived=True).order_by(desc(Email.date_received))
        elif label == 'spam':
            return base_query.filter_by(is_spam=True).order_by(desc(Email.date_received))
        elif label == 'trash':
            return base_query.filter_by(is_deleted=True).order_by(desc(Email.date_received))
        else:
            # Custom label
            return base_query.filter(Email.labels.contains(f'"{label}"')).order_by(desc(Email.date_received))
    
    def _group_emails_by_thread(self, emails: List[Email]) -> List[Dict[str, Any]]:
        """Group emails by thread for Gmail-style conversation view"""
        threads = {}
        
        for email in emails:
            thread_id = email.thread_id or email.id
            
            if thread_id not in threads:
                threads[thread_id] = {
                    'thread_id': thread_id,
                    'emails': [],
                    'latest_date': email.date_received,
                    'has_unread': False,
                    'is_starred': False,
                    'participants': set()
                }
            
            thread = threads[thread_id]
            thread['emails'].append(email.to_dict())
            
            # Update thread metadata
            if email.date_received and email.date_received > thread['latest_date']:
                thread['latest_date'] = email.date_received
            
            if not email.is_read:
                thread['has_unread'] = True
            
            if email.is_starred:
                thread['is_starred'] = True
            
            # Add participants
            thread['participants'].add(email.sender_email)
            thread['participants'].update(email.get_recipients())
        
        # Convert to list and sort by latest date
        threaded_list = []
        for thread in threads.values():
            thread['participants'] = list(thread['participants'])
            thread['email_count'] = len(thread['emails'])
            
            # Use the latest email as the main email for display
            thread['main_email'] = max(thread['emails'], key=lambda x: x['date_received'] or '')
            
            threaded_list.append(thread)
        
        # Sort by latest email date
        threaded_list.sort(key=lambda x: x['latest_date'], reverse=True)
        
        return threaded_list
    
    def _parse_search_query(self, query: str) -> Dict[str, Any]:
        """Parse Gmail-style search query (from:user@example.com, has:attachment, etc.)"""
        filters = {
            'text': [],
            'from': None,
            'to': None,
            'subject': None,
            'has_attachment': False,
            'is_unread': False,
            'is_starred': False,
            'label': None,
            'date_after': None,
            'date_before': None
        }
        
        # Gmail-style search operators
        operators = {
            'from:': 'from',
            'to:': 'to',
            'subject:': 'subject',
            'has:attachment': 'has_attachment',
            'is:unread': 'is_unread',
            'is:starred': 'is_starred',
            'label:': 'label',
            'after:': 'date_after',
            'before:': 'date_before'
        }
        
        # Split query into parts
        parts = query.split()
        
        for part in parts:
            matched = False
            
            for operator, filter_key in operators.items():
                if part.startswith(operator):
                    if operator in ['has:attachment', 'is:unread', 'is:starred']:
                        filters[filter_key] = True
                    else:
                        value = part[len(operator):]
                        filters[filter_key] = value
                    matched = True
                    break
            
            if not matched:
                # Regular text search
                filters['text'].append(part)
        
        filters['text'] = ' '.join(filters['text'])
        return filters
    
    def _build_search_query(self, filters: Dict[str, Any]):
        """Build SQLAlchemy query from search filters"""
        query = Email.query.filter_by(is_deleted=False)
        
        # Text search in subject and content
        if filters['text']:
            text_filter = or_(
                Email.subject.contains(filters['text']),
                Email.text_content.contains(filters['text']),
                Email.html_content.contains(filters['text'])
            )
            query = query.filter(text_filter)
        
        # From filter
        if filters['from']:
            query = query.filter(Email.sender_email.contains(filters['from']))
        
        # Subject filter
        if filters['subject']:
            query = query.filter(Email.subject.contains(filters['subject']))
        
        # Attachment filter
        if filters['has_attachment']:
            query = query.filter(Email.has_attachments == True)
        
        # Status filters
        if filters['is_unread']:
            query = query.filter(Email.is_read == False)
        
        if filters['is_starred']:
            query = query.filter(Email.is_starred == True)
        
        # Label filter
        if filters['label']:
            query = query.filter(Email.labels.contains(f'"{filters["label"]}"'))
        
        return query.order_by(desc(Email.date_received))
    
    def _process_raw_email(self, raw_email_data: Dict[str, Any]) -> Optional[Email]:
        """Process raw email data from IMAP into Email model"""
        try:
            # Parse email content
            parsed_email = email_parser.parse_email(raw_email_data.get('raw_content', b''))
            if not parsed_email:
                return None
            
            # Generate email ID
            email_id = self._generate_email_id(parsed_email.get('message_id', ''))
            
            # Check if email already exists
            existing_email = Email.query.get(email_id)
            if existing_email:
                return existing_email
            
            # Create new email
            email = Email(
                id=email_id,
                message_id=parsed_email.get('message_id', ''),
                thread_id=self._generate_thread_id(parsed_email),
                subject=parsed_email.get('subject', ''),
                sender_name=parsed_email.get('from', {}).get('name', ''),
                sender_email=parsed_email.get('from', {}).get('email', ''),
                recipient_emails=json.dumps([r.get('email', '') for r in parsed_email.get('to', [])]),
                cc_emails=json.dumps([r.get('email', '') for r in parsed_email.get('cc', [])]),
                html_content=parsed_email.get('html_content', ''),
                text_content=parsed_email.get('text_content', ''),
                date_received=datetime.fromisoformat(parsed_email.get('date', datetime.utcnow().isoformat())),
                size_bytes=parsed_email.get('size', 0),
                has_attachments=len(parsed_email.get('attachments', [])) > 0,
                attachment_count=len(parsed_email.get('attachments', [])),
                category=self._categorize_email(parsed_email)
            )
            
            db.session.add(email)
            db.session.commit()
            
            # Process attachments
            if parsed_email.get('attachments'):
                self._process_attachments(email, parsed_email['attachments'])
            
            # Update or create thread
            self._update_email_thread(email)
            
            return email
            
        except Exception as e:
            logger.error(f"Error processing raw email: {e}")
            db.session.rollback()
            return None
    
    def _generate_thread_id(self, parsed_email: Dict[str, Any]) -> str:
        """Generate thread ID for email conversation grouping"""
        # Use In-Reply-To or References headers for threading
        in_reply_to = parsed_email.get('in_reply_to', '')
        references = parsed_email.get('references', [])
        
        if in_reply_to:
            return hashlib.md5(in_reply_to.encode()).hexdigest()
        
        if references:
            return hashlib.md5(references[0].encode()).hexdigest()
        
        # Fallback to subject-based threading
        subject = parsed_email.get('subject', '')
        normalized_subject = re.sub(r'^(Re:|Fwd?:)\s*', '', subject, flags=re.IGNORECASE).strip()
        
        return hashlib.md5(normalized_subject.encode()).hexdigest()
    
    def _categorize_email(self, parsed_email: Dict[str, Any]) -> str:
        """Categorize email (primary, social, promotions, updates)"""
        sender_email = parsed_email.get('from', {}).get('email', '').lower()
        subject = parsed_email.get('subject', '').lower()
        
        # Social category
        social_domains = ['facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com']
        if any(domain in sender_email for domain in social_domains):
            return 'social'
        
        # Promotions category
        promo_keywords = ['sale', 'discount', 'offer', 'deal', 'promotion', 'coupon']
        if any(keyword in subject for keyword in promo_keywords):
            return 'promotions'
        
        # Updates category
        update_keywords = ['newsletter', 'update', 'notification', 'alert']
        if any(keyword in subject for keyword in update_keywords):
            return 'updates'
        
        return 'primary'
    
    def _get_system_label_count(self, label_name: str) -> int:
        """Get count of emails for system labels"""
        if label_name == 'inbox':
            return Email.query.filter_by(is_deleted=False, is_archived=False, is_spam=False).count()
        elif label_name == 'starred':
            return Email.query.filter_by(is_starred=True, is_deleted=False).count()
        elif label_name == 'important':
            return Email.query.filter_by(is_important=True, is_deleted=False).count()
        elif label_name == 'spam':
            return Email.query.filter_by(is_spam=True).count()
        elif label_name == 'trash':
            return Email.query.filter_by(is_deleted=True).count()
        else:
            return 0
    
    def _get_custom_label_count(self, label_name: str) -> int:
        """Get count of emails for custom labels"""
        return Email.query.filter(Email.labels.contains(f'"{label_name}"')).count()
    
    def _invalidate_email_caches(self):
        """Clear email-related caches"""
        cache_service.clear("emails:")
        cache_service.clear("search:")
        cache_service.delete("email:labels")
    
    def _empty_result(self, page: int, per_page: int, label: str) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            'emails': [],
            'pagination': {
                'total': 0, 'pages': 0, 'current_page': page, 'per_page': per_page,
                'has_next': False, 'has_prev': False
            },
            'label': label,
            'error': 'Failed to fetch emails'
        }
    
    def _empty_search_result(self, query: str, page: int, per_page: int) -> Dict[str, Any]:
        """Return empty search result structure"""
        return {
            'emails': [],
            'pagination': {
                'total': 0, 'pages': 0, 'current_page': page, 'per_page': per_page
            },
            'query': query,
            'error': 'Search failed'
        }
    
    def _generate_email_id(self, message_id: str) -> str:
        """Generate unique email ID"""
        if message_id:
            return hashlib.md5(message_id.encode()).hexdigest()
        return str(uuid.uuid4())
    
    def _is_new_email(self, email: Email) -> bool:
        """Check if this is a newly created email"""
        return (datetime.utcnow() - email.created_at).total_seconds() < 60
    
    def _get_thread_emails(self, thread_id: str, exclude_id: str = None) -> List[Dict[str, Any]]:
        """Get all emails in a thread"""
        query = Email.query.filter_by(thread_id=thread_id, is_deleted=False)
        if exclude_id:
            query = query.filter(Email.id != exclude_id)
        
        emails = query.order_by(Email.date_received).all()
        return [email.to_dict() for email in emails]
    
    def _update_thread_status(self, thread_id: str):
        """Update thread status based on emails in thread"""
        thread = EmailThread.query.get(thread_id)
        if not thread:
            return
        
        # Get all emails in thread
        emails = Email.query.filter_by(thread_id=thread_id, is_deleted=False).all()
        
        # Update thread metadata
        thread.email_count = len(emails)
        thread.has_unread = any(not email.is_read for email in emails)
        thread.is_starred = any(email.is_starred for email in emails)
        
        if emails:
            thread.last_email_date = max(email.date_received for email in emails if email.date_received)
        
        db.session.commit()
    
    def _update_email_thread(self, email: Email):
        """Update or create email thread"""
        thread = EmailThread.query.get(email.thread_id)
        
        if not thread:
            # Create new thread
            thread = EmailThread(
                id=email.thread_id,
                subject_hash=hashlib.md5(email.subject.encode()).hexdigest(),
                email_count=1,
                last_email_date=email.date_received,
                has_unread=not email.is_read,
                is_starred=email.is_starred
            )
            db.session.add(thread)
        else:
            # Update existing thread
            thread.email_count += 1
            if email.date_received and email.date_received > thread.last_email_date:
                thread.last_email_date = email.date_received
            if not email.is_read:
                thread.has_unread = True
            if email.is_starred:
                thread.is_starred = True
        
        # Add participants
        thread.add_participant(email.sender_email)
        for recipient in email.get_recipients():
            thread.add_participant(recipient)
        
        db.session.commit()
    
    def _process_attachments(self, email: Email, attachments_data: List[Dict[str, Any]]):
        """Process and store email attachments"""
        try:
            for attachment_data in attachments_data:
                # Create attachment record
                attachment = EmailAttachment(
                    email_id=email.id,
                    filename=attachment_data.get('filename', 'unknown'),
                    content_type=attachment_data.get('content_type', 'application/octet-stream'),
                    size_bytes=attachment_data.get('size', 0),
                    checksum=attachment_data.get('checksum', '')
                )
                
                # Store attachment file using storage client
                if attachment_data.get('content'):
                    import base64
                    content = base64.b64decode(attachment_data['content'])
                    storage_result = storage_client.upload_attachment(
                        email_id=email.id,
                        filename=attachment.filename,
                        content=content,
                        content_type=attachment.content_type,
                        attachment_id=attachment.id
                    )
                    attachment.storage_path = storage_result.get('object_key', '')
                
                db.session.add(attachment)
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error processing attachments: {e}")
            db.session.rollback()

# Global email service instance
email_service = EmailService()