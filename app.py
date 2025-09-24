print("Starting app.py")
from flask import Flask, render_template, jsonify, request, Response, stream_template
from flask_cors import CORS
from decouple import config
import logging
import json
from datetime import datetime, timedelta
import threading
import time

# Import application modules
from models import db, Email, EmailAttachment, EmailLabel, init_system_labels
from flask_migrate import Migrate
from imap_manager import imap_manager
from email_parser import email_parser
from storage_client import storage_client
from services.email_service import email_service
from services.cache_service import cache_service
from services.realtime_service import realtime_service

# Configure application logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)
CORS(app)

# Application configuration
app.config['SQLALCHEMY_DATABASE_URI'] = config('DATABASE_URL', default='sqlite:///instance/vexmail.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = config('SECRET_KEY', default='your-secret-key-here')

# Initialize database
db.init_app(app)
migrate = Migrate(app, db)

# Initialize system labels on first run
with app.app_context():
    db.create_all()
    init_system_labels()

# Routes
@app.route('/')
def index():
    """Gmail-style main interface"""
    return render_template('index.html')

# Email API endpoints
@app.route('/api/emails/<label>')
def get_emails_by_label(label='inbox'):
    """Get emails for specific label (inbox, sent, starred, etc.)"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    result = email_service.get_inbox_emails(page, per_page, label)
    return jsonify(result)

@app.route('/api/emails')
def get_inbox_emails():
    """Get inbox emails (default)"""
    return get_emails_by_label('inbox')

@app.route('/api/search')
def search_emails():
    """Gmail-style email search with operators"""
    try:
        query = request.args.get('q', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        
        if not query:
            return jsonify({"error": "Search query is required"}), 400
        
        result = email_service.search_emails(query, page, per_page)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({"error": "Search failed"}), 500

@app.route('/api/emails/<email_id>')
def get_email_detail(email_id):
    """Get detailed email content"""
    try:
        email_data = email_service.get_email_detail(email_id)
        if email_data:
            return jsonify(email_data)
        return jsonify({"error": "Email not found"}), 404
        
    except Exception as e:
        logger.error(f"Error fetching email detail: {e}")
        return jsonify({"error": "Failed to fetch email"}), 500

@app.route('/api/attachments/<attachment_id>/download')
def download_attachment(attachment_id):
    """Download attachment"""
    try:
        attachment = EmailAttachment.query.get(attachment_id)
        if not attachment:
            return jsonify({"error": "Attachment not found"}), 404
        
        if not attachment.is_safe:
            return jsonify({"error": "Attachment is not safe to download"}), 403
        
        # Download from storage
        file_data = storage_client.download_attachment(attachment.storage_path)
        
        from flask import send_file
        import io
        
        file_obj = io.BytesIO(file_data)
        return send_file(
            file_obj,
            as_attachment=True,
            download_name=attachment.filename,
            mimetype=attachment.content_type
        )
        
    except Exception as e:
        logger.error(f"Error downloading attachment: {e}")
        return jsonify({"error": "Failed to download attachment"}), 500

# Email action endpoints
@app.route('/api/emails/<email_id>/actions', methods=['POST'])
def update_email_status(email_id):
    """Update email status (read, starred, important, etc.)"""
    try:
        data = request.get_json()
        action = data.get('action')
        value = data.get('value', True)
        
        # Map actions to model fields
        action_map = {
            'read': 'is_read',
            'star': 'is_starred',
            'important': 'is_important',
            'archive': 'is_archived'
        }
        
        if action not in action_map:
            return jsonify({"error": "Invalid action"}), 400
        
        updates = {action_map[action]: value}
        success = email_service.update_email_status(email_id, updates)
        
        if success:
            return jsonify({"success": True, "action": action, "value": value})
        else:
            return jsonify({"error": "Email not found"}), 404
        
    except Exception as e:
        logger.error(f"Error updating email status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/emails/batch-actions', methods=['POST'])
def batch_email_actions():
    """Perform batch actions on multiple emails"""
    try:
        data = request.get_json()
        email_ids = data.get('email_ids', [])
        action = data.get('action')
        label = data.get('label')
        
        if not email_ids or not action:
            return jsonify({"error": "Missing email_ids or action"}), 400
        
        if action == 'move_to_label' and label:
            success = email_service.move_to_label(email_ids, label)
        else:
            # Handle other batch actions
            success = False
            for email_id in email_ids:
                if action == 'delete':
                    success = email_service.update_email_status(email_id, {'is_deleted': True})
                elif action == 'archive':
                    success = email_service.update_email_status(email_id, {'is_archived': True})
                elif action == 'mark_read':
                    success = email_service.update_email_status(email_id, {'is_read': True})
                elif action == 'mark_unread':
                    success = email_service.update_email_status(email_id, {'is_read': False})
        
        if success:
            return jsonify({"success": True, "message": f"Batch {action} completed", "count": len(email_ids)})
        else:
            return jsonify({"error": "Batch action failed"}), 500
        
    except Exception as e:
        logger.error(f"Error in batch action: {e}")
        return jsonify({"error": str(e)}), 500

# Label management
@app.route('/api/labels')
def get_labels():
    """Get all email labels with counts"""
    try:
        labels = email_service.get_labels()
        return jsonify({"labels": labels})
        
    except Exception as e:
        logger.error(f"Error fetching labels: {e}")
        return jsonify({"error": str(e)}), 500

# Email synchronization
@app.route('/api/sync', methods=['POST'])
def sync_emails():
    """Trigger email synchronization"""
    try:
        limit = request.json.get('limit', 50) if request.json else 50
        result = email_service.sync_emails_from_server(limit)
        return jsonify({"success": True, "result": result})
        
    except Exception as e:
        logger.error(f"Error triggering sync: {e}")
        return jsonify({"error": "Failed to start sync"}), 500

# Real-time event endpoints
@app.route('/api/realtime/register', methods=['POST'])
def register_realtime_client():
    """Register client for real-time updates"""
    try:
        client_id = realtime_service.register_client()
        return jsonify({"client_id": client_id, "success": True})
    except Exception as e:
        logger.error(f"Error registering client: {e}")
        return jsonify({"error": "Failed to register client"}), 500

@app.route('/api/realtime/events/<client_id>')
def get_realtime_events(client_id):
    """Long-polling endpoint for real-time events"""
    try:
        timeout = request.args.get('timeout', 30, type=int)
        event = realtime_service.get_client_events(client_id, timeout)
        
        if event:
            return jsonify(event)
        else:
            return jsonify({"error": "Client not found"}), 404
            
    except Exception as e:
        logger.error(f"Error getting events for client {client_id}: {e}")
        return jsonify({"error": "Failed to get events"}), 500

# System monitoring endpoints
@app.route('/api/status')
def system_status():
    """Get system status"""
    try:
        status = {
            'database': 'connected',
            'cache': 'connected',
            'storage': 'connected',
            'imap': 'connected',
            'realtime': 'connected',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Test database connection
        try:
            Email.query.count()
        except:
            status['database'] = 'disconnected'
        
        # Test cache service
        try:
            cache_service.set('health_check', 'ok', ttl=60)
            if cache_service.get('health_check') != 'ok':
                status['cache'] = 'disconnected'
        except:
            status['cache'] = 'disconnected'
        
        # Test IMAP connection
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
        # Get email counts
        email_stats = {
            'total': Email.query.count(),
            'unread': Email.query.filter_by(is_read=False, is_deleted=False).count(),
            'starred': Email.query.filter_by(is_starred=True, is_deleted=False).count(),
            'important': Email.query.filter_by(is_important=True, is_deleted=False).count(),
            'with_attachments': Email.query.filter_by(has_attachments=True, is_deleted=False).count()
        }
        
        cache_stats = cache_service.get_stats()
        realtime_stats = realtime_service.get_stats()
        storage_stats = storage_client.get_storage_stats()
        
        stats = {
            'emails': email_stats,
            'attachments': {
                'total': EmailAttachment.query.count()
            },
            'storage': storage_stats,
            'cache': cache_stats,
            'realtime': realtime_stats,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return jsonify({"error": "Failed to get stats"}), 500

# Error handling
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({"error": "Internal server error"}), 500

# Background email monitoring
def start_background_services():
    """Start background services for email monitoring"""
    def imap_monitoring():
        try:
            imap_manager.start_idle()
            logger.info("IMAP IDLE monitoring started")
        except Exception as e:
            logger.error(f"Failed to start IMAP monitoring: {e}")
    
    # Start IMAP monitoring in background thread
    imap_thread = threading.Thread(target=imap_monitoring, daemon=True)
    imap_thread.start()

if __name__ == '__main__':
    logger.info("Starting VexMail application...")
    
    # Start background services
    start_background_services()
    
    # Run Flask application
    app.run(host='0.0.0.0', port=5000, debug=True)