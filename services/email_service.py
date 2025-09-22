"""
Enhanced email service with intelligent caching and real-time updates
"""
import logging
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

from models import db, Email, EmailAttachment, EmailOperation
from imap_manager import imap_manager
from email_parser import email_parser
from storage_client import storage_client
from services.cache_service import cache_service
from services.realtime_service import realtime_service

logger = logging.getLogger(__name__)

class EmailService:
    """Enhanced email service with caching and real-time updates"""
    
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour default TTL
        self.list_cache_ttl = 300  # 5 minutes for email lists
        
    def get_emails_paginated(self, page: int = 1, per_page: int = 20, force_refresh: bool = False) -> Dict[str, Any]:
        """Get emails with intelligent caching"""
        cache_key = f"emails:page:{page}:per_page:{per_page}"
        
        # Try cache first unless force refresh
        if not force_refresh:
            cached_result = cache_service.get(cache_key)
            if cached_result:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_result
        
        try:
            # Fetch from database
            emails_query = Email.query.filter_by(is_deleted=False).order_by(Email.date.desc())
            emails_paginated = emails_query.paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            # Convert to dict format
            emails_list = []
            for email in emails_paginated.items:
                email_dict = self._email_to_dict(email)
                emails_list.append(email_dict)
                
                # Cache individual email
                email_cache_key = f"email:detail:{email.id}"
                cache_service.set(email_cache_key, email_dict, ttl=self.cache_ttl)
            
            result = {
                "pagination": {
                    "total": emails_paginated.total,
                    "pages": emails_paginated.pages,
                    "current_page": emails_paginated.page,
                    "per_page": emails_paginated.per_page,
                    "has_next": emails_paginated.has_next,
                    "has_prev": emails_paginated.has_prev
                },
                "emails": emails_list,
                "cached_at": datetime.utcnow().isoformat()
            }
            
            # Cache the result
            cache_service.set(cache_key, result, ttl=self.list_cache_ttl)
            logger.debug(f"Cached result for {cache_key}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return {
                "pagination": {"total": 0, "pages": 0, "current_page": 1, "per_page": per_page},
                "emails": [],
                "error": str(e)
            }
    
    def get_email_detail(self, email_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Get email detail with caching"""
        cache_key = f"email:detail:{email_id}"
        
        # Try cache first unless force refresh
        if not force_refresh:
            cached_email = cache_service.get(cache_key)
            if cached_email:
                logger.debug(f"Cache hit for email {email_id}")
                return cached_email
        
        try:
            # Fetch from database
            email = Email.query.get(email_id)
            if not email:
                return None
            
            email_dict = self._email_to_dict(email, include_full_content=True)
            
            # Fetch attachments
            attachments = EmailAttachment.query.filter_by(email_id=email_id).all()
            email_dict['attachments'] = [att.to_dict() for att in attachments]
            
            # Cache the result
            cache_service.set(cache_key, email_dict, ttl=self.cache_ttl)
            logger.debug(f"Cached email detail for {email_id}")
            
            return email_dict
            
        except Exception as e:
            logger.error(f"Error fetching email detail {email_id}: {e}")
            return None
    
    def search_emails(self, query: str, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Search emails with caching"""
        cache_key = f"search:{hashlib.md5(query.encode()).hexdigest()}:page:{page}:per_page:{per_page}"
        
        # Try cache first
        cached_result = cache_service.get(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for search: {query}")
            return cached_result
        
        try:
            # Search in database
            emails_query = Email.query.filter(
                Email.is_deleted == False,
                db.or_(
                    Email.subject.contains(query),
                    Email.sender_name.contains(query),
                    Email.sender_email.contains(query),
                    Email.body.contains(query)
                )
            ).order_by(Email.date.desc())
            
            emails_paginated = emails_query.paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            emails_list = [self._email_to_dict(email) for email in emails_paginated.items]
            
            result = {
                "pagination": {
                    "total": emails_paginated.total,
                    "pages": emails_paginated.pages,
                    "current_page": emails_paginated.page,
                    "per_page": emails_paginated.per_page
                },
                "emails": emails_list,
                "query": query,
                "cached_at": datetime.utcnow().isoformat()
            }
            
            # Cache search results for shorter time
            cache_service.set(cache_key, result, ttl=300)  # 5 minutes
            
            return result
            
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return {
                "pagination": {"total": 0, "pages": 0, "current_page": 1, "per_page": per_page},
                "emails": [],
                "query": query,
                "error": str(e)
            }
    
    def sync_emails_from_server(self, limit: int = 50) -> Dict[str, Any]:
        """Sync emails from IMAP server with real-time updates"""
        try:
            logger.info(f"Starting email sync (limit: {limit})")
            
            # Emit sync start event
            realtime_service.emit_sync_status('started', 'Starting email synchronization...', 0)
            
            # Fetch emails from IMAP
            emails = imap_manager.fetch_emails(limit=limit)
            
            if not emails:
                realtime_service.emit_sync_status('completed', 'No new emails found', 100)
                return {
                    'status': 'success',
                    'message': 'No new emails found',
                    'count': 0,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            stored_count = 0
            skipped_count = 0
            total_emails = len(emails)
            
            for i, email_data in enumerate(emails):
                try:
                    # Calculate progress
                    progress = int((i + 1) / total_emails * 100)
                    realtime_service.emit_sync_status('syncing', f'Processing email {i+1} of {total_emails}', progress)
                    
                    email_record = self._store_email_safely(email_data)
                    if email_record:
                        stored_count += 1
                        
                        # Emit real-time event for new email
                        realtime_service.emit_email_received(self._email_to_dict(email_record))
                    else:
                        skipped_count += 1
                        
                except Exception as e:
                    logger.error(f"Error processing email: {e}")
                    skipped_count += 1
                    continue
            
            # Invalidate relevant caches
            self._invalidate_email_caches()
            
            result = {
                'status': 'success',
                'message': f'Processed {total_emails} emails',
                'count': stored_count,
                'skipped': skipped_count,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Emit sync completion event
            realtime_service.emit_sync_status('completed', f'Sync completed: {stored_count} new emails', 100)
            
            logger.info(f"Sync completed: {stored_count} stored, {skipped_count} skipped")
            return result
            
        except Exception as e:
            logger.error(f"Error in email sync: {e}")
            realtime_service.emit_sync_status('error', f'Sync failed: {str(e)}', 0)
            return {
                'status': 'error',
                'message': str(e),
                'count': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def update_email_status(self, email_id: str, updates: Dict[str, Any]) -> bool:
        """Update email status with cache invalidation and real-time updates"""
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
            
            # Invalidate caches
            cache_service.delete(f"email:detail:{email_id}")
            self._invalidate_email_caches()
            
            # Emit real-time update
            realtime_service.emit_email_updated(email_id, updates)
            
            logger.info(f"Updated email {email_id}: {updates}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating email {email_id}: {e}")
            db.session.rollback()
            return False
    
    def delete_email(self, email_id: str) -> bool:
        """Delete email with cache invalidation and real-time updates"""
        try:
            email = Email.query.get(email_id)
            if not email:
                return False
            
            email.is_deleted = True
            email.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Invalidate caches
            cache_service.delete(f"email:detail:{email_id}")
            self._invalidate_email_caches()
            
            # Emit real-time update
            realtime_service.emit_email_deleted(email_id)
            
            logger.info(f"Deleted email {email_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting email {email_id}: {e}")
            db.session.rollback()
            return False
    
    def get_email_stats(self) -> Dict[str, Any]:
        """Get email statistics with caching"""
        cache_key = "email:stats"
        
        cached_stats = cache_service.get(cache_key)
        if cached_stats:
            return cached_stats
        
        try:
            stats = {
                'total': Email.query.count(),
                'unread': Email.query.filter_by(is_read=False, is_deleted=False).count(),
                'deleted': Email.query.filter_by(is_deleted=True).count(),
                'flagged': Email.query.filter_by(is_flagged=True, is_deleted=False).count(),
                'starred': Email.query.filter_by(is_starred=True, is_deleted=False).count(),
                'with_attachments': Email.query.filter(Email.attachment_count > 0, Email.is_deleted == False).count(),
                'last_updated': datetime.utcnow().isoformat()
            }
            
            # Cache for 5 minutes
            cache_service.set(cache_key, stats, ttl=300)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting email stats: {e}")
            return {}
    
    def _email_to_dict(self, email: Email, include_full_content: bool = False) -> Dict[str, Any]:
        """Convert email model to dictionary"""
        email_dict = {
            'id': email.id,
            'subject': email.subject or '(No Subject)',
            'sender_name': email.sender_name,
            'sender_email': email.sender_email,
            'recipient': email.recipient,
            'date': email.date.strftime("%b %d, %Y %I:%M %p") if email.date else '',
            'date_iso': email.date.isoformat() if email.date else '',
            'is_read': email.is_read,
            'is_flagged': email.is_flagged,
            'is_starred': email.is_starred,
            'priority': email.priority,
            'size': email.size,
            'attachment_count': email.attachment_count,
            'thread_id': email.thread_id,
            'is_suspicious': email.is_suspicious,
            'created_at': email.created_at.isoformat() if email.created_at else None
        }
        
        if include_full_content:
            email_dict.update({
                'body': email.body,
                'html_content': email.html_content,
                'text_content': email.text_content,
                'cc': email.get_cc_list(),
                'bcc': email.get_bcc_list(),
                'suspicious_reasons': email.get_suspicious_reasons()
            })
        else:
            # Include preview for list view
            preview_text = email.text_content or email.body or ''
            email_dict['preview'] = preview_text[:150] + "..." if len(preview_text) > 150 else preview_text
        
        return email_dict
    
    def _store_email_safely(self, email_data: Dict) -> Optional[Email]:
        """Store email with duplicate prevention"""
        try:
            # Generate unique email ID
            email_id = self._generate_email_id(
                email_data.get('message_id', ''), 
                email_data.get('uid', '')
            )
            
            # Check if email already exists
            if Email.query.get(email_id):
                logger.debug(f"Email {email_id} already exists, skipping")
                return Email.query.get(email_id)
            
            # Parse email content
            parsed_email = email_parser.parse_email(email_data.get('raw_content', ''))
            if not parsed_email:
                logger.error("Failed to parse email content")
                return None
            
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
                thread_id=parsed_email.get('thread_id', ''),
                attachment_count=len(parsed_email.get('attachments', [])),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                synced_at=datetime.utcnow()
            )
            
            # Save to database
            try:
                db.session.add(email_record)
                db.session.commit()
                logger.info(f"Successfully stored email {email_id}")
                return email_record
                
            except IntegrityError:
                db.session.rollback()
                logger.warning(f"Email {email_id} already exists (integrity error)")
                return Email.query.get(email_id)
                
        except Exception as e:
            logger.error(f"Error storing email: {e}")
            db.session.rollback()
            return None
    
    def _generate_email_id(self, message_id: str, uid: str) -> str:
        """Generate a unique email ID"""
        if message_id:
            return hashlib.md5(message_id.encode()).hexdigest()
        else:
            return hashlib.md5(f"{uid}_{datetime.utcnow().timestamp()}".encode()).hexdigest()
    
    def _invalidate_email_caches(self):
        """Invalidate email-related caches"""
        cache_service.clear("emails:")
        cache_service.clear("search:")
        cache_service.delete("email:stats")

# Global email service instance
email_service = EmailService()