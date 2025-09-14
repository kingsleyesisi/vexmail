print("Starting app.py")
print("Importing flask")
from flask import Flask, render_template, jsonify, request, Response, stream_template
print("Importing flask_cors")
from flask_cors import CORS
print("Importing decouple")
from decouple import config
print("Importing logging")
import logging
print("Importing json")
import json
print("Importing datetime")
from datetime import datetime, timedelta
print("Importing threading")
import threading
print("Importing time")
import time

# Import our modules
print("Importing models")
from models import db, Email, EmailOperation, EmailAttachment, User, EmailThread, Notification
print("Importing flask_migrate")
from flask_migrate import Migrate
print("Importing imap_manager")
from imap_manager import imap_manager
print("Importing email_parser")
from email_parser import email_parser
print("Importing storage_client")
from storage_client import storage_client
print("Importing email_sync_service")
from email_sync_service import email_sync_service
print("Importing background_tasks")
from background_tasks import task_manager, start_periodic_tasks, sync_emails_task
print("Imports complete")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Database configuration
import os
from pathlib import Path

# Use absolute path for SQLite database
if config('DATABASE_URL', default='').startswith('sqlite:///'):
    db_path = config('DATABASE_URL', default='sqlite:///instance/vexmail.db').replace('sqlite:///', '')
    if not os.path.isabs(db_path):
        # Make it absolute relative to the app directory
        db_path = os.path.join(os.path.dirname(__file__), db_path)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = config('DATABASE_URL', default='sqlite:///instance/vexmail.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = config('SECRET_KEY', default='your-secret-key-here')

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)

# Initialize caching
from flask_caching import Cache
app.config['CACHE_TYPE'] = 'FileSystemCache'
app.config['CACHE_DIR'] = 'cache'
cache = Cache(app)

# Database tables will be created by init_db.py script

# Background task management
def start_imap_idle():
    """Start IMAP IDLE monitoring"""
    try:
        imap_manager.start_idle()
        logger.info("IMAP IDLE monitoring started")
    except Exception as e:
        logger.error(f"Failed to start IMAP IDLE: {e}")

def stop_imap_idle():
    """Stop IMAP IDLE monitoring"""
    try:
        imap_manager.stop_idle()
        logger.info("IMAP IDLE monitoring stopped")
    except Exception as e:
        logger.error(f"Failed to stop IMAP IDLE: {e}")

# Utility functions
def get_emails_from_db(page, per_page, user_id='default'):
    """Fetch emails from database with pagination and caching using sync service"""
    return email_sync_service.get_emails_from_db(page, per_page)

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

# API Routes
@app.route('/api/emails')
def api_emails():
    """API endpoint to get emails with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    user_id = request.args.get('user_id', 'default')
    
    result = get_emails_from_db(page, per_page, user_id)
    return jsonify(result)

@app.route('/api/emails/all')
def api_all_emails():
    """API endpoint to get all emails (for backward compatibility)"""
    result = get_emails_from_db(1, 1000)
    return jsonify(result["emails"])

@app.route('/api/emails/search')
def api_search_emails():
    """Search emails endpoint"""
    try:
        query = request.args.get('q', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        if not query:
            return jsonify({"error": "Search query is required"}), 400
        
        # Search in database
        emails = Email.query.filter(
            Email.is_deleted == False,
            db.or_(
                Email.subject.contains(query),
                Email.sender_name.contains(query),
                Email.sender_email.contains(query),
                Email.body.contains(query)
            )
        ).order_by(Email.date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        result = {
            "pagination": {
                "total": emails.total,
                "pages": emails.pages,
                "current_page": emails.page,
                "per_page": emails.per_page
            },
            "emails": [email.to_dict() for email in emails.items],
            "query": query
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({"error": "Search failed"}), 500

@app.route('/api/email/<email_id>')
def api_email_detail(email_id):
    """API endpoint to get specific email details"""
    try:
        email_data = email_sync_service.get_email_detail(email_id)
        if email_data:
            return jsonify(email_data)
        return jsonify({"error": "Email not found"}), 404
        
    except Exception as e:
        logger.error(f"Error fetching email detail: {e}")
        return jsonify({"error": "Failed to fetch email"}), 500

@app.route('/api/email/<email_id>/attachments')
def api_email_attachments(email_id):
    """Get email attachments"""
    try:
        email = Email.query.get(email_id)
        if not email:
            return jsonify({"error": "Email not found"}), 404
        
        attachments = EmailAttachment.query.filter_by(email_id=email_id).all()
        
        return jsonify({
            "email_id": email_id,
            "attachments": [attachment.to_dict() for attachment in attachments]
        })
        
    except Exception as e:
        logger.error(f"Error fetching attachments: {e}")
        return jsonify({"error": "Failed to fetch attachments"}), 500

@app.route('/api/attachment/<attachment_id>/download')
def api_download_attachment(attachment_id):
    """Download attachment"""
    try:
        attachment = EmailAttachment.query.get(attachment_id)
        if not attachment:
            return jsonify({"error": "Attachment not found"}), 404
        
        if not attachment.is_safe:
            return jsonify({"error": "Attachment is not safe to download"}), 403
        
        # For local storage, serve the file directly
        try:
            file_data = storage_client.download_attachment(attachment.storage_path)
            
            from flask import send_file
            import io
            
            # Create a file-like object from the bytes
            file_obj = io.BytesIO(file_data)
            
            return send_file(
                file_obj,
                as_attachment=True,
                download_name=attachment.filename,
                mimetype=attachment.content_type
            )
            
        except FileNotFoundError:
            return jsonify({"error": "Attachment file not found"}), 404
        
    except Exception as e:
        logger.error(f"Error downloading attachment: {e}")
        return jsonify({"error": "Failed to download attachment"}), 500

# Email Operations
@app.route('/api/emails/<email_id>/read', methods=['POST'])
def mark_as_read(email_id):
    """Mark email as read"""
    try:
        email = Email.query.get(email_id)
        if not email:
            return jsonify({"error": "Email not found"}), 404
        
        # Optimistic update
        email.is_read = True
        db.session.commit()
        
        # Queue IMAP operation
        operation = EmailOperation(
            email_uid=email_id,
            operation_type='read'
        )
        db.session.add(operation)
        db.session.commit()
        
        # Invalidate cache
        cache.delete(f"email:{email_id}")
        
        # Publish event (dummy)
        # redis_client.publish_email_event('email_read', {
        #     'email_id': email_id,
        #     'timestamp': datetime.utcnow().isoformat()
        # })
        
        return jsonify({"success": True, "email": {
            "id": email.id,
            "is_read": email.is_read
        }})
        
    except Exception as e:
        logger.error(f"Error marking email as read: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/emails/<email_id>/unread', methods=['POST'])
def mark_as_unread(email_id):
    """Mark email as unread"""
    try:
        email = Email.query.get(email_id)
        if not email:
            return jsonify({"error": "Email not found"}), 404
        
        # Optimistic update
        email.is_read = False
        db.session.commit()
        
        # Queue IMAP operation
        operation = EmailOperation(
            email_uid=email_id,
            operation_type='unread'
        )
        db.session.add(operation)
        db.session.commit()
        
        # Invalidate cache
        cache.delete(f"email:{email_id}")
        
        # Publish event (dummy)
        # redis_client.publish_email_event('email_unread', {
        #     'email_id': email_id,
        #     'timestamp': datetime.utcnow().isoformat()
        # })
        
        return jsonify({"success": True, "email": {
            "id": email.id,
            "is_read": email.is_read
        }})
        
    except Exception as e:
        logger.error(f"Error marking email as unread: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/emails/<email_id>/flag', methods=['POST'])
def flag_email(email_id):
    """Flag/unflag email"""
    try:
        email = Email.query.get(email_id)
        if not email:
            return jsonify({"error": "Email not found"}), 404
        
        # Toggle flag status
        email.is_flagged = not email.is_flagged
        db.session.commit()
        
        # Queue IMAP operation
        operation = EmailOperation(
            email_uid=email_id,
            operation_type='flag' if email.is_flagged else 'unflag'
        )
        db.session.add(operation)
        db.session.commit()
        
        # Invalidate cache
        cache.delete(f"email:{email_id}")
        
        return jsonify({"success": True, "email": {
            "id": email.id,
            "is_flagged": email.is_flagged
        }})
        
    except Exception as e:
        logger.error(f"Error flagging email: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/emails/<email_id>/star', methods=['POST'])
def star_email(email_id):
    """Star/unstar email"""
    try:
        email = Email.query.get(email_id)
        if not email:
            return jsonify({"error": "Email not found"}), 404
        
        # Toggle star status
        email.is_starred = not email.is_starred
        db.session.commit()
        
        # Invalidate cache
        cache.delete(f"email:{email_id}")
        
        return jsonify({"success": True, "email": {
            "id": email.id,
            "is_starred": email.is_starred
        }})
        
    except Exception as e:
        logger.error(f"Error starring email: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/emails/<email_id>', methods=['DELETE'])
def delete_email(email_id):
    """Delete email"""
    try:
        email = Email.query.get(email_id)
        if not email:
            return jsonify({"error": "Email not found"}), 404
        
        # Optimistic update
        email.is_deleted = True
        db.session.commit()
        
        # Queue IMAP operation
        operation = EmailOperation(
            email_uid=email_id,
            operation_type='delete'
        )
        db.session.add(operation)
        db.session.commit()
        
        # Invalidate cache
        cache.delete(f"email:{email_id}")
        
        # Publish event (dummy)
        # redis_client.publish_email_event('email_deleted', {
        #     'email_id': email_id,
        #     'timestamp': datetime.utcnow().isoformat()
        # })
        
        return jsonify({"success": True, "message": "Email deleted"})
        
    except Exception as e:
        logger.error(f"Error deleting email: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/emails/batch', methods=['POST'])
def batch_operations():
    """Batch operations on emails"""
    try:
        data = request.get_json()
        operation = data.get('operation')
        uids = data.get('uids', [])
        
        if operation not in ['read', 'unread', 'delete', 'flag', 'unflag']:
            return jsonify({"error": "Invalid operation"}), 400
        
        if not uids:
            return jsonify({"error": "No emails specified"}), 400
        
        updated_emails = []
        
        for uid in uids:
            email = Email.query.get(uid)
            if email:
                if operation == 'read':
                    email.is_read = True
                elif operation == 'unread':
                    email.is_read = False
                elif operation == 'delete':
                    email.is_deleted = True
                elif operation == 'flag':
                    email.is_flagged = True
                elif operation == 'unflag':
                    email.is_flagged = False
                
                # Queue IMAP operation
                op = EmailOperation(
                    email_uid=uid,
                    operation_type=operation
                )
                db.session.add(op)
                updated_emails.append(uid)
        
        db.session.commit()
        
        # Invalidate cache for all updated emails
        for uid in updated_emails:
            cache.delete(f"email:{uid}")
        
        # Publish event (dummy)
        # redis_client.publish_email_event('batch_operation', {
        #     'operation': operation,
        #     'email_ids': updated_emails,
        #     'timestamp': datetime.utcnow().isoformat()
        # })
        
        return jsonify({
            "success": True, 
            "message": f"Batch {operation} operation queued",
            "updated_count": len(updated_emails)
        })
        
    except Exception as e:
        logger.error(f"Error in batch operation: {e}")
        return jsonify({"error": str(e)}), 500

# Webhook and Sync Endpoints
from flask import current_app

@app.route('/api/sync', methods=['POST'])
def trigger_sync():
    """Trigger email synchronization"""
    try:
        task_manager.add_task(sync_emails_task, current_app._get_current_object(), limit=100)
        return jsonify({"success": True, "message": "Email sync triggered"})
        
    except Exception as e:
        logger.error(f"Error triggering sync: {e}")
        return jsonify({"error": "Failed to start sync"}), 500


# Server-Sent Events for real-time updates
@app.route('/api/events/long-poll')
def long_poll_events():
    """Long-polling endpoint for real-time updates"""
    try:
        event = imap_manager.get_new_email_event(timeout=30)
        if event:
            return jsonify(event)
        else:
            return jsonify({}), 204 # No Content
    except Exception as e:
        logger.error(f"Long-polling error: {e}")
        return jsonify({"error": "Long-polling failed"}), 500


# System Status and Health
@app.route('/api/status')
def system_status():
    """Get system status"""
    try:
        status = {
            'database': 'connected',
            'redis': 'connected',
            'storage': 'connected',
            'imap': 'connected',
            'celery': 'connected',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Test Redis (removed)
        status['redis'] = 'removed'
        
        # Test database
        try:
            Email.query.count()
        except:
            status['database'] = 'disconnected'
        
        # Test storage
        try:
            storage_client.get_storage_stats()
        except:
            status['storage'] = 'disconnected'
        
        # Test IMAP
        try:
            with imap_manager.connection_pool.get_connection() as conn:
                if not conn.is_connected():
                    status['imap'] = 'disconnected'
        except:
            status['imap'] = 'disconnected'
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({"error": "Failed to get status"}), 500

@app.route('/api/stats')
def system_stats():
    """Get system statistics"""
    try:
        stats = {
            'emails': {
                'total': Email.query.count(),
                'unread': Email.query.filter_by(is_read=False, is_deleted=False).count(),
                'deleted': Email.query.filter_by(is_deleted=True).count(),
                'flagged': Email.query.filter_by(is_flagged=True, is_deleted=False).count(),
                'starred': Email.query.filter_by(is_starred=True, is_deleted=False).count()
            },
            'operations': {
                'pending': EmailOperation.query.filter_by(status='pending').count(),
                'failed': EmailOperation.query.filter_by(status='failed').count(),
                'success': EmailOperation.query.filter_by(status='success').count()
            },
            'attachments': {
                'total': EmailAttachment.query.count(),
                'scanned': EmailAttachment.query.filter_by(is_scanned=True).count(),
                'unsafe': EmailAttachment.query.filter_by(is_safe=False).count()
            },
            'storage': storage_client.get_storage_stats(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return jsonify({"error": "Failed to get stats"}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({"error": "Internal server error"}), 500

# Application startup
def startup():
    """Initialize application on startup"""
    try:
        # Start IMAP IDLE monitoring
        start_imap_idle()
        
        # Run initial email sync in a background thread
        logger.info("Running initial email sync in background...")
        sync_thread = threading.Thread(target=email_sync_service.sync_emails, kwargs={'limit': 50})
        sync_thread.start()
        
        logger.info("VexMail application started successfully")
        
    except Exception as e:
        logger.error(f"Startup error: {e}")

# Initialize startup when app starts
with app.app_context():
    startup()

@app.teardown_appcontext
def shutdown_session(exception=None):
    """Clean up on shutdown"""
    try:
        stop_imap_idle()
        logger.info("VexMail application shutdown complete")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

if __name__ == '__main__':
    # Start periodic tasks
    start_periodic_tasks(app)
    # Run the Flask development server
    app.run(host='0.0.0.0', port=5000, debug=True)