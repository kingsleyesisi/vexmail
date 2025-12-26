"""
Simple Gmail-like Email Client
A beginner-friendly email receiving application with real-time updates
"""

import sqlite3
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import os
from datetime import datetime
import imaplib
import email
from email.header import decode_header
import logging
from dotenv import load_dotenv
import threading
import time

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder='.')
CORS(app)

# SQLite Configuration
# Using /tmp for Vercel serverless functions as it's the only writable directory
if os.environ.get('VERCEL'):
    DB_PATH = os.path.join('/tmp', 'vexmail.db')
else:
    DB_PATH = os.path.join('instance', 'vexmail.db')
    os.makedirs('instance', exist_ok=True)

def get_db_connection():
    """Get a connection to the SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the SQLite database with the required table"""
    print(f"[Vexmail] Initializing database at {DB_PATH}...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if table exists and has the right schema
    try:
        cursor.execute("SELECT email_id FROM emails LIMIT 1")
    except sqlite3.OperationalError:
        # Table doesn't exist or doesn't have email_id
        print("[Vexmail] Table missing or schema outdated. Recreating...")
        cursor.execute("DROP TABLE IF EXISTS emails")
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id TEXT UNIQUE NOT NULL,
                subject TEXT,
                sender TEXT,
                date TEXT,
                body TEXT,
                is_read BOOLEAN DEFAULT 0,
                is_starred BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    conn.commit()
    conn.close()
    print("[Vexmail] Database initialized.")

# Initialize DB on import for Vercel
init_db()

# Vexmail configuration
IMAP_SERVER = os.getenv('IMAP_SERVER', 'imap.gmail.com')
EMAIL_USER = os.getenv('EMAIL_USER', '')
EMAIL_PASS = os.getenv('EMAIL_PASS', '')

# Vexmail Global State
last_sync_time = None
sync_lock = threading.Lock()

def connect_to_imap():
    """Connect to IMAP server and return connection"""
    print(f"\n[Vexmail] Connecting to {IMAP_SERVER}...")
    try:
        if not EMAIL_USER or not EMAIL_PASS:
            print("[Vexmail] Error: Email credentials missing!")
            return None
            
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
    """Fetch emails from IMAP server using UIDs"""
    mail = connect_to_imap()
    if not mail:
        return {"error": "Could not connect to email server."}

    try:
        # Use UIDs instead of sequence numbers
        status, messages = mail.uid('search', None, 'ALL')
        email_ids = messages[0].split()
        
        # Get latest emails (UIDs are always increasing)
        email_ids = email_ids[-limit:]
        emails = []

        for email_id in reversed(email_ids):
            try:
                # Fetch using UID
                status, msg_data = mail.uid('fetch', email_id, '(RFC822)')

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject = decode_email_header(msg['subject'])
                        sender = decode_email_header(msg['from'])
                        date = msg['date']

                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        body = payload.decode('utf-8', errors='ignore')
                                    break
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                body = payload.decode('utf-8', errors='ignore')

                        email_data = {
                            'email_id': email_id.decode(),
                            'subject': subject or '(No Subject)',
                            'sender': sender,
                            'date': date,
                            'body': body[:5000],
                            'is_read': 0,
                            'is_starred': 0,
                            'created_at': datetime.now().isoformat()
                        }
                        emails.append(email_data)

            except Exception as e:
                continue

        mail.close()
        mail.logout()
        return emails

    except Exception as e:
        return {"error": str(e)}

def sync_emails_internal(limit=50):
    """Internal sync logic"""
    global last_sync_time
    with sync_lock:
        emails = fetch_emails_from_server(limit=limit)
        if isinstance(emails, dict) and 'error' in emails:
            return 0, emails['error']

        new_count = 0
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for email_data in emails:
            try:
                # We can now rely on email_id being a unique UID
                cursor.execute('INSERT OR IGNORE INTO emails (email_id, subject, sender, date, body, is_read, is_starred, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (email_data['email_id'], email_data['subject'], email_data['sender'], email_data['date'], email_data['body'], email_data['is_read'], email_data['is_starred'], email_data['created_at']))
                if cursor.rowcount > 0:
                    new_count += 1
            except:
                continue
        
        conn.commit()
        conn.close()
        last_sync_time = datetime.now()
        return new_count, None

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/emails')
def get_emails():
    """Get all emails from SQLite"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Sort by UID (email_id) DESC to ensure strictly latest emails first
        cursor.execute('SELECT * FROM emails ORDER BY CAST(email_id AS INTEGER) DESC LIMIT 50')
        rows = cursor.fetchall()
        emails = [dict(row) for row in rows]
        conn.close()
        
        return jsonify({
            'success': True,
            'emails': emails,
            'count': len(emails),
            'last_sync': last_sync_time.isoformat() if last_sync_time else None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/emails/<int:email_db_id>')
def get_email(email_db_id):
    """Get single email by ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM emails WHERE id = ?', (email_db_id,))
        row = cursor.fetchone()
        
        if row:
            # Mark as read
            cursor.execute('UPDATE emails SET is_read = 1 WHERE id = ?', (email_db_id,))
            conn.commit()
            email_data = dict(row)
            conn.close()
            return jsonify({'success': True, 'email': email_data})
        else:
            conn.close()
            return jsonify({'success': False, 'error': 'Email not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sync', methods=['POST', 'GET'])
def sync_emails():
    """Manual sync or Cron trigger"""
    # Simple check for cron (optional)
    if request.method == 'GET' and not request.headers.get('Authorization'):
        # In production, you'd check for a secret token
        pass

    new_count, error = sync_emails_internal()
    if error:
        return jsonify({'success': False, 'error': error}), 500

    return jsonify({'success': True, 'message': f'Synced {new_count} new emails', 'new_count': new_count})

@app.route('/api/emails/<int:email_db_id>/star', methods=['POST'])
def toggle_star(email_db_id):
    """Toggle star status"""
    try:
        data = request.get_json()
        is_starred = 1 if data.get('is_starred', False) else 0
        conn = get_db_connection()
        conn.execute('UPDATE emails SET is_starred = ? WHERE id = ?', (is_starred, email_db_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'is_starred': bool(is_starred)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/emails/<int:email_db_id>/read', methods=['POST'])
def toggle_read(email_db_id):
    """Toggle read status"""
    try:
        data = request.get_json()
        is_read = 1 if data.get('is_read', False) else 0
        conn = get_db_connection()
        conn.execute('UPDATE emails SET is_read = ? WHERE id = ?', (is_read, email_db_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'is_read': bool(is_read)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Get statistics"""
    try:
        conn = get_db_connection()
        total = conn.execute('SELECT COUNT(*) FROM emails').fetchone()[0]
        unread = conn.execute('SELECT COUNT(*) FROM emails WHERE is_read = 0').fetchone()[0]
        starred = conn.execute('SELECT COUNT(*) FROM emails WHERE is_starred = 1').fetchone()[0]
        conn.close()

        return jsonify({
            'success': True,
            'stats': {
                'total': total,
                'unread': unread,
                'starred': starred,
                'last_sync': last_sync_time.isoformat() if last_sync_time else None,
                'account': EMAIL_USER
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    """Health check"""
    return jsonify({
        'success': True,
        'status': 'healthy'
    })

if __name__ == '__main__':
    # When running locally
    app.run(host='0.0.0.0', port=5000, debug=True)  # Run the app