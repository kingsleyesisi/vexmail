"""
Background tasks for email processing
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

from celery_config import celery_app
from redis_client import redis_client
from imap_manager import imap_manager
from email_parser import email_parser
from models import db, Email, EmailOperation
from flask import Flask

logger = logging.getLogger(__name__)

# Import the main app configuration
from app import app

flask_app = app

@celery_app.task(bind=True, name='vexmail.tasks.process_new_email')
def process_new_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process a new email from IMAP"""
    try:
        with flask_app.app_context():
            # Parse email content
            parsed_email = email_parser.parse_email(email_data['raw_content'])
            
            if not parsed_email:
                raise Exception("Failed to parse email")
            
            # Check if email is suspicious
            is_suspicious, reasons = email_parser.is_suspicious_email(parsed_email)
            
            # Save to database
            email_record = Email(
                id=parsed_email['id'],
                uid_validity=email_data.get('uid_validity', str(int(datetime.utcnow().timestamp()))),
                subject=parsed_email['subject'],
                sender_name=parsed_email['from']['name'],
                sender_email=parsed_email['from']['email'],
                body=parsed_email['body'],
                date=datetime.fromisoformat(parsed_email['date']),
                is_read=email_data.get('is_read', False),
                is_deleted=False,
                thread_id=parsed_email.get('thread_id', ''),
                message_id=parsed_email.get('message_id', ''),
                priority=parsed_email.get('priority', 'normal'),
                size=parsed_email.get('size', 0),
                is_suspicious=is_suspicious,
                suspicious_reasons=json.dumps(reasons) if reasons else None,
                raw_headers=json.dumps(parsed_email.get('raw_headers', {})),
                html_content=parsed_email.get('html_content', ''),
                attachments_info=json.dumps(parsed_email.get('attachments', []))
            )
            
            db.session.add(email_record)
            db.session.commit()
            
            # Cache email in Redis
            redis_client.cache_email_detail(parsed_email['id'], {
                'id': email_record.id,
                'subject': email_record.subject,
                'from': email_record.sender_name,
                'email': email_record.sender_email,
                'body': email_record.body,
                'date': email_record.date.isoformat(),
                'is_read': email_record.is_read,
                'preview': email_record.body[:150] + "..." if len(email_record.body) > 150 else email_record.body
            })
            
            # Invalidate email list cache
            redis_client.invalidate_email_cache('default')
            
            # Process attachments if any
            if parsed_email.get('attachments'):
                process_attachments.delay(parsed_email['id'], parsed_email['attachments'])
            
            # Send notification
            send_notification.delay('new_email', {
                'email_id': parsed_email['id'],
                'subject': parsed_email['subject'],
                'from': parsed_email['from']['name']
            })
            
            # Publish event
            redis_client.publish_email_event('email_received', {
                'email_id': parsed_email['id'],
                'subject': parsed_email['subject'],
                'from': parsed_email['from']['name'],
                'timestamp': datetime.utcnow().isoformat()
            })
            
            logger.info(f"Successfully processed email {parsed_email['id']}")
            
            return {
                'status': 'success',
                'email_id': parsed_email['id'],
                'processed_at': datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error processing email: {e}")
        # Update task state
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise

@celery_app.task(bind=True, name='vexmail.tasks.sync_emails')
def sync_emails(self, limit: int = 50) -> Dict[str, Any]:
    """Sync emails from IMAP server"""
    try:
        with flask_app.app_context():
            # Fetch emails from IMAP
            emails = imap_manager.fetch_emails(limit=limit)
            
            if not emails:
                return {'status': 'success', 'message': 'No new emails found', 'count': 0}
            
            processed_count = 0
            
            for email_data in emails:
                try:
                    # Check if email already exists
                    existing = Email.query.get(email_data['id'])
                    if existing:
                        continue
                    
                    # Process new email
                    result = process_new_email.delay(email_data)
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing email {email_data.get('id', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Synced {processed_count} new emails")
            
            return {
                'status': 'success',
                'count': processed_count,
                'processed_at': datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error syncing emails: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise

@celery_app.task(bind=True, name='vexmail.tasks.process_attachments')
def process_attachments(self, email_id: str, attachments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process email attachments"""
    try:
        processed_attachments = []
        
        for attachment in attachments:
            try:
                # Here you would typically:
                # 1. Download attachment content
                # 2. Scan for viruses/malware
                # 3. Store in S3/MinIO
                # 4. Update database with storage info
                
                processed_attachment = {
                    'filename': attachment['filename'],
                    'size': attachment['size'],
                    'content_type': attachment['content_type'],
                    'checksum': attachment['checksum'],
                    'stored_at': datetime.utcnow().isoformat(),
                    'storage_path': f"attachments/{email_id}/{attachment['filename']}"
                }
                
                processed_attachments.append(processed_attachment)
                
            except Exception as e:
                logger.error(f"Error processing attachment {attachment.get('filename', 'unknown')}: {e}")
                continue
        
        logger.info(f"Processed {len(processed_attachments)} attachments for email {email_id}")
        
        return {
            'status': 'success',
            'email_id': email_id,
            'attachments': processed_attachments,
            'processed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing attachments for email {email_id}: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise

@celery_app.task(bind=True, name='vexmail.tasks.process_pending_operations')
def process_pending_operations(self) -> Dict[str, Any]:
    """Process pending email operations"""
    try:
        with flask_app.app_context():
            # Get pending operations
            pending_ops = EmailOperation.query.filter_by(status='pending').all()
            
            processed_count = 0
            failed_count = 0
            
            for operation in pending_ops:
                try:
                    # Check retry limit
                    if operation.retry_count >= operation.max_retries:
                        operation.status = 'failed'
                        db.session.commit()
                        failed_count += 1
                        continue
                    
                    # Execute IMAP operation
                    success = imap_manager.execute_operation(
                        operation.operation_type,
                        operation.email_uid
                    )
                    
                    if success:
                        operation.status = 'success'
                        processed_count += 1
                    else:
                        operation.retry_count += 1
                        operation.last_retry = datetime.utcnow()
                    
                    db.session.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing operation {operation.id}: {e}")
                    operation.retry_count += 1
                    operation.last_retry = datetime.utcnow()
                    db.session.commit()
                    continue
            
            logger.info(f"Processed {processed_count} operations, {failed_count} failed")
            
            return {
                'status': 'success',
                'processed': processed_count,
                'failed': failed_count,
                'processed_at': datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error processing pending operations: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise

@celery_app.task(bind=True, name='vexmail.tasks.send_notification')
def send_notification(self, notification_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Send notification to users"""
    try:
        # Here you would typically:
        # 1. Send push notification
        # 2. Send email notification
        # 3. Update in-app notifications
        # 4. Send webhook if configured
        
        notification = {
            'type': notification_type,
            'data': data,
            'timestamp': datetime.utcnow().isoformat(),
            'id': f"notif_{datetime.utcnow().timestamp()}"
        }
        
        # Publish notification event
        redis_client.publish('notifications', json.dumps(notification))
        
        logger.info(f"Sent notification: {notification_type}")
        
        return {
            'status': 'success',
            'notification': notification
        }
        
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise

@celery_app.task(bind=True, name='vexmail.tasks.periodic_email_sync')
def periodic_email_sync(self) -> Dict[str, Any]:
    """Periodic email synchronization"""
    try:
        # Start email sync task
        result = sync_emails.delay(limit=100)
        
        logger.info("Started periodic email sync")
        
        return {
            'status': 'success',
            'sync_task_id': result.id,
            'started_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting periodic sync: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise

@celery_app.task(bind=True, name='vexmail.tasks.cleanup_failed_tasks')
def cleanup_failed_tasks(self) -> Dict[str, Any]:
    """Clean up old failed tasks and operations"""
    try:
        with flask_app.app_context():
            # Clean up old failed operations (older than 7 days)
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            
            old_operations = EmailOperation.query.filter(
                EmailOperation.status == 'failed',
                EmailOperation.created_at < cutoff_date
            ).all()
            
            for operation in old_operations:
                db.session.delete(operation)
            
            db.session.commit()
            
            logger.info(f"Cleaned up {len(old_operations)} old failed operations")
            
            return {
                'status': 'success',
                'cleaned_operations': len(old_operations),
                'cleaned_at': datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error cleaning up failed tasks: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise

@celery_app.task(bind=True, name='vexmail.tasks.cleanup_tasks')
def cleanup_tasks(self) -> Dict[str, Any]:
    """General cleanup tasks"""
    try:
        # Clean up Redis cache (remove old entries)
        # Clean up temporary files
        # Clean up old logs
        
        logger.info("Completed general cleanup tasks")
        
        return {
            'status': 'success',
            'cleaned_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup tasks: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise

# Task monitoring and management
@celery_app.task
def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get status of a specific task"""
    try:
        result = celery_app.AsyncResult(task_id)
        return {
            'task_id': task_id,
            'status': result.status,
            'result': result.result,
            'info': result.info
        }
    except Exception as e:
        logger.error(f"Error getting task status for {task_id}: {e}")
        return {
            'task_id': task_id,
            'status': 'ERROR',
            'error': str(e)
        }

@celery_app.task
def cancel_task(task_id: str) -> Dict[str, Any]:
    """Cancel a running task"""
    try:
        celery_app.control.revoke(task_id, terminate=True)
        return {
            'task_id': task_id,
            'status': 'CANCELLED',
            'cancelled_at': datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}")
        return {
            'task_id': task_id,
            'status': 'ERROR',
            'error': str(e)
        }
