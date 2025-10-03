"""
Simple Gmail-like Email Client
A beginner-friendly email receiving application with real-time updates
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from supabase import create_client, Client
import os
from datetime import datetime
import imaplib
import email
from email.header import decode_header
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize Supabase client
SUPABASE_URL = os.getenv('VITE_SUPABASE_URL')
SUPABASE_KEY = os.getenv('VITE_SUPABASE_SUPABASE_ANON_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Email configuration
IMAP_SERVER = os.getenv('IMAP_SERVER', 'imap.gmail.com')
EMAIL_USER = os.getenv('EMAIL_USER', '')
EMAIL_PASS = os.getenv('EMAIL_PASS', '')


def connect_to_imap():
    """Connect to IMAP server and return connection"""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select('inbox')
        return mail
    except Exception as e:
        logger.error(f"Failed to connect to IMAP: {e}")
        return None


def decode_email_header(header):
    """Decode email header to readable text"""
    if header is None:
        return ""

    decoded_parts = decode_header(header)
    decoded_string = ""

    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            try:
                decoded_string += part.decode(encoding or 'utf-8', errors='ignore')
            except:
                decoded_string += part.decode('utf-8', errors='ignore')
        else:
            decoded_string += str(part)

    return decoded_string


def fetch_emails_from_server(limit=50):
    """Fetch emails from IMAP server"""
    mail = connect_to_imap()
    if not mail:
        return {"error": "Could not connect to email server"}

    try:
        # Search for all emails
        status, messages = mail.search(None, 'ALL')
        email_ids = messages[0].split()

        # Get latest emails
        email_ids = email_ids[-limit:]
        emails = []

        for email_id in reversed(email_ids):
            try:
                # Fetch email
                status, msg_data = mail.fetch(email_id, '(RFC822)')

                # Parse email
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        # Extract email details
                        subject = decode_email_header(msg['subject'])
                        sender = decode_email_header(msg['from'])
                        date = msg['date']

                        # Get email body
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

                        # Create email object
                        email_data = {
                            'email_id': email_id.decode(),
                            'subject': subject or '(No Subject)',
                            'sender': sender,
                            'date': date,
                            'body': body[:500],  # First 500 characters
                            'is_read': False,
                            'is_starred': False,
                            'created_at': datetime.now().isoformat()
                        }

                        emails.append(email_data)

            except Exception as e:
                logger.error(f"Error processing email: {e}")
                continue

        mail.close()
        mail.logout()

        return emails

    except Exception as e:
        logger.error(f"Error fetching emails: {e}")
        return {"error": str(e)}


@app.route('/')
def index():
    """Main page"""
    return render_template('simple_index.html')


@app.route('/api/emails')
def get_emails():
    """Get all emails from Supabase"""
    try:
        response = supabase.table('emails').select('*').order('created_at', desc=True).limit(50).execute()
        return jsonify({
            'success': True,
            'emails': response.data,
            'count': len(response.data)
        })
    except Exception as e:
        logger.error(f"Error fetching emails: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/emails/<email_id>')
def get_email(email_id):
    """Get single email by ID"""
    try:
        response = supabase.table('emails').select('*').eq('id', email_id).single().execute()

        # Mark as read
        supabase.table('emails').update({'is_read': True}).eq('id', email_id).execute()

        return jsonify({
            'success': True,
            'email': response.data
        })
    except Exception as e:
        logger.error(f"Error fetching email: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sync', methods=['POST'])
def sync_emails():
    """Sync emails from IMAP to Supabase"""
    try:
        # Fetch emails from server
        emails = fetch_emails_from_server(limit=50)

        if isinstance(emails, dict) and 'error' in emails:
            return jsonify({'success': False, 'error': emails['error']}), 500

        # Store in Supabase
        new_count = 0
        for email_data in emails:
            try:
                # Check if email already exists
                existing = supabase.table('emails').select('id').eq('email_id', email_data['email_id']).execute()

                if not existing.data:
                    supabase.table('emails').insert(email_data).execute()
                    new_count += 1
            except Exception as e:
                logger.error(f"Error storing email: {e}")
                continue

        return jsonify({
            'success': True,
            'message': f'Synced {new_count} new emails',
            'new_count': new_count
        })

    except Exception as e:
        logger.error(f"Error syncing emails: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/emails/<email_id>/star', methods=['POST'])
def toggle_star(email_id):
    """Toggle star status of email"""
    try:
        data = request.get_json()
        is_starred = data.get('is_starred', False)

        supabase.table('emails').update({'is_starred': is_starred}).eq('id', email_id).execute()

        return jsonify({'success': True, 'is_starred': is_starred})
    except Exception as e:
        logger.error(f"Error toggling star: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/emails/<email_id>/read', methods=['POST'])
def toggle_read(email_id):
    """Toggle read status of email"""
    try:
        data = request.get_json()
        is_read = data.get('is_read', False)

        supabase.table('emails').update({'is_read': is_read}).eq('id', email_id).execute()

        return jsonify({'success': True, 'is_read': is_read})
    except Exception as e:
        logger.error(f"Error toggling read: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stats')
def get_stats():
    """Get email statistics"""
    try:
        # Get total count
        all_emails = supabase.table('emails').select('id', count='exact').execute()

        # Get unread count
        unread = supabase.table('emails').select('id', count='exact').eq('is_read', False).execute()

        # Get starred count
        starred = supabase.table('emails').select('id', count='exact').eq('is_starred', True).execute()

        return jsonify({
            'success': True,
            'stats': {
                'total': all_emails.count if hasattr(all_emails, 'count') else 0,
                'unread': unread.count if hasattr(unread, 'count') else 0,
                'starred': starred.count if hasattr(starred, 'count') else 0
            }
        })
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


if __name__ == '__main__':
    logger.info("Starting Simple Email Client...")
    logger.info(f"Supabase URL: {SUPABASE_URL}")

    if not EMAIL_USER or not EMAIL_PASS:
        logger.warning("Email credentials not configured. Sync will not work.")

    app.run(host='0.0.0.0', port=5000, debug=True)
