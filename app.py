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
print("Importing services")
from services.email_service import email_service
from services.cache_service import cache_service
from services.realtime_service import realtime_service
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

# Real-time client management
@app.before_request
def before_request():
    """Register client for real-time updates"""
    client_id = request.headers.get('X-Client-ID')
    if not client_id and request.endpoint and 'api' in request.endpoint:
        client_id = realtime_service.register_client()
        g.client_id = client_id

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
    force_refresh = request.args.get('force_refresh', False, type=bool)
    
    result = email_service.get_emails_paginated(page, per_page, force_refresh)
    return jsonify(result)

@app.route('/api/emails/search')
def api_search_emails():
    """Search emails endpoint"""
    try:
        query = request.args.get('q', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        if not query:
            return jsonify({"error": "Search query is required"}), 400
        
        result = email_service.search_emails(query, page, per_page)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({"error": "Search failed"}), 500

@app.route('/api/email/<email_id>')
def api_email_detail(email_id):
    """API endpoint to get specific email details"""
    try:
        force_refresh = request.args.get('force_refresh', False, type=bool)
        email_data = email_service.get_email_detail(email_id, force_refresh)
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
        success = email_service.update_email_status(email_id, {'is_read': True})
        if success:
            return jsonify({"success": True, "message": "Email marked as read"})
        else:
            return jsonify({"error": "Email not found"}), 404
        
    except Exception as e:
        logger.error(f"Error marking email as read: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/emails/<email_id>/unread', methods=['POST'])
def mark_as_unread(email_id):
    """Mark email as unread"""
    try:
        success = email_service.update_email_status(email_id, {'is_read': False})
        if success:
            return jsonify({"success": True, "message": "Email marked as unread"})
        else:
            return jsonify({"error": "Email not found"}), 404
        
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
        
        new_flag_status = not email.is_flagged
        success = email_service.update_email_status(email_id, {'is_flagged': new_flag_status})
        if success:
            return jsonify({"success": True, "is_flagged": new_flag_status})
        else:
            return jsonify({"error": "Email not found"}), 404
        
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
        
        new_star_status = not email.is_starred
        success = email_service.update_email_status(email_id, {'is_starred': new_star_status})
        if success:
            return jsonify({"success": True, "is_starred": new_star_status})
        else:
            return jsonify({"error": "Email not found"}), 404
        
    except Exception as e:
        logger.error(f"Error starring email: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/emails/<email_id>', methods=['DELETE'])
def delete_email(email_id):
    """Delete email"""
    try:
        success = email_service.delete_email(email_id)
        if success:
            return jsonify({"success": True, "message": "Email deleted"})
        else:
            return jsonify({"error": "Email not found"}), 404
        
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

@app.route('/api/sync', methods=['POST'])
def trigger_sync():
    """Trigger email synchronization"""
    try:
        limit = request.json.get('limit', 50) if request.json else 50
        result = email_service.sync_emails_from_server(limit)
        return jsonify({"success": True, "result": result})
        
    except Exception as e:
        logger.error(f"Error triggering sync: {e}")
        return jsonify({"error": "Failed to start sync"}), 500

# Real-time Events
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
    """Get real-time events for a client (long-polling)"""
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

# System Status and Health
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
        
        # Test cache
        try:
            cache_service.set('health_check', 'ok', ttl=60)
            if cache_service.get('health_check') != 'ok':
                status['cache'] = 'disconnected'
        except:
            status['cache'] = 'disconnected'
        
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
        
        # Test real-time service
        try:
            realtime_stats = realtime_service.get_stats()
            status['realtime'] = 'connected'
            status['realtime_clients'] = realtime_stats['connected_clients']
        except:
            status['realtime'] = 'disconnected'
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({"error": "Failed to get status"}), 500

@app.route('/api/stats')
def system_stats():
    """Get system statistics"""
    try:
        email_stats = email_service.get_email_stats()
        cache_stats = cache_service.get_stats()
        realtime_stats = realtime_service.get_stats()
        
        stats = {
            'emails': email_stats,
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
            'cache': cache_stats,
            'realtime': realtime_stats,
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

if __name__ == '__main__':
    logger.info("Starting VexMail application...")
    
    # Start IMAP IDLE monitoring in background
    def start_imap_monitoring():
        try:
            imap_manager.start_idle()
            logger.info("IMAP IDLE monitoring started")
        except Exception as e:
            logger.error(f"Failed to start IMAP monitoring: {e}")
    
    imap_thread = threading.Thread(target=start_imap_monitoring, daemon=True)
    imap_thread.start()
    
    # Run the Flask development server
    app.run(host='0.0.0.0', port=5000, debug=True)