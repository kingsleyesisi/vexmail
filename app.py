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
DB_PATH = os.path.join('instance', 'vexmail.db')
os.makedirs('instance', exist_ok=True)

def get_db_connection():
    """Get a connection to the SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the SQLite database with the required table"""
    print(f"[Vexmail] Initializing local database at {DB_PATH}...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if table exists and has the right schema
    try:
        cursor.execute("SELECT email_id FROM emails LIMIT 1")
    except sqlite3.OperationalError:
        # Table doesn't exist or doesn't have email_id
        print("[Vexmail] Existing table schema is outdated or missing. Recreating...")
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
    print("[Vexmail] Database initialized successfully.")

# Vexmail configuration
IMAP_SERVER = os.getenv('IMAP_SERVER', 'imap.gmail.com')
EMAIL_USER = os.getenv('EMAIL_USER', '')
EMAIL_PASS = os.getenv('EMAIL_PASS', '')

# Vexmail Global State
last_sync_time = None
sync_lock = threading.Lock()

def connect_to_imap():
    """Connect to IMAP server and return connection"""
    print(f"\n[Vexmail] Attempting to connect to {IMAP_SERVER}...")
    try:
        if not EMAIL_USER or not EMAIL_PASS:
            print("[Vexmail] ERROR: Email credentials missing in .env file!")
            return None
            
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        print(f"[Vexmail] Connected. Logging in as {EMAIL_USER}...")
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select('inbox')
        print("[Vexmail] Successfully authenticated and selected inbox.")
        return mail
    except Exception as e:
        print(f"[Vexmail] FAILED to connect: {str(e)}")
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
        return {"error": "Could not connect to email server. Please check your credentials."}

    try:
        print("[Vexmail] Searching for emails...")
        status, messages = mail.search(None, 'ALL')
        email_ids = messages[0].split()
        
        total_count = len(email_ids)
        print(f"[Vexmail] Found {total_count} total emails. Fetching latest {limit}...")

        # Get latest emails
        email_ids = email_ids[-limit:]
        emails = []

        for idx, email_id in enumerate(reversed(email_ids)):
            try:
                print(f"[Vexmail] [{idx+1}/{len(email_ids)}] Fetching email ID: {email_id.decode()}...")
                status, msg_data = mail.fetch(email_id, '(RFC822)')

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject = decode_email_header(msg['subject'])
                        sender = decode_email_header(msg['from'])
                        date = msg['date']

                        print(f"[Vexmail]   - Subject: {subject[:50]}...")

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
                print(f"[Vexmail] Error processing email {email_id.decode()}: {e}")
                continue

        print(f"[Vexmail] Successfully fetched {len(emails)} emails.")
        mail.close()
        mail.logout()
        return emails

    except Exception as e:
        print(f"[Vexmail] CRITICAL Error fetching emails: {e}")
        return {"error": str(e)}

def background_sync_worker():
    """Background worker to sync emails periodically"""
    global last_sync_time
    print("[Vexmail] Background sync worker started.")
    while True:
        try:
            print("\n[Vexmail] Background sync triggered...")
            sync_emails_internal()
            last_sync_time = datetime.now()
            print(f"[Vexmail] Background sync completed at {last_sync_time.strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"[Vexmail] Background sync error: {e}")
        time.sleep(600)

def sync_emails_internal(limit=50):
    """Internal sync logic shared by background and manual sync"""
    with sync_lock:
        emails = fetch_emails_from_server(limit=limit)
        if isinstance(emails, dict) and 'error' in emails:
            return 0, emails['error']

        new_count = 0
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print(f"[Vexmail] Saving {len(emails)} emails to local database...")
        for email_data in emails:
            try:
                cursor.execute('INSERT OR IGNORE INTO emails (email_id, subject, sender, date, body, is_read, is_starred, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (email_data['email_id'], email_data['subject'], email_data['sender'], email_data['date'], email_data['body'], email_data['is_read'], email_data['is_starred'], email_data['created_at']))
                if cursor.rowcount > 0:
                    new_count += 1
            except Exception as e:
                print(f"[Vexmail] Error saving email {email_data.get('email_id')}: {e}")
                continue
        
        conn.commit()
        conn.close()
        return new_count, None

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/emails')
def get_emails():
    """Get all emails from SQLite"""
    print("[Vexmail] API: Fetching all emails...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM emails ORDER BY created_at DESC LIMIT 50')
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
        print(f"[Vexmail] API ERROR (get_emails): {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/emails/<int:email_db_id>')
def get_email(email_db_id):
    """Get single email by ID"""
    print(f"[Vexmail] API: Fetching email detail for ID: {email_db_id}")
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
        print(f"[Vexmail] API ERROR (get_email): {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sync', methods=['POST'])
def sync_emails():
    """Manual sync with throttling"""
    global last_sync_time
    print("[Vexmail] API: Manual sync requested.")
    
    if last_sync_time and (datetime.now() - last_sync_time).total_seconds() < 60:
        print("[Vexmail] Manual sync throttled.")
        return jsonify({'success': True, 'message': 'Emails already up to date.', 'new_count': 0})

    new_count, error = sync_emails_internal()
    if error:
        return jsonify({'success': False, 'error': error}), 500

    last_sync_time = datetime.now()
    return jsonify({'success': True, 'message': f'Synced {new_count} new emails', 'new_count': new_count})

@app.route('/api/emails/<int:email_db_id>/star', methods=['POST'])
def toggle_star(email_db_id):
    """Toggle star status of email"""
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
    """Toggle read status of email"""
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
    """Get email statistics"""
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
                'last_sync': last_sync_time.isoformat() if last_sync_time else None
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'last_sync': last_sync_time.isoformat() if last_sync_time else None
    })

if __name__ == '__main__':
    print("\n" + "="*50)
    print("Welcome to Vexmail - Your Ultimate Email Client")
    print("="*50)
    
    init_db()
    
    if EMAIL_USER and EMAIL_PASS:
        bg_thread = threading.Thread(target=background_sync_worker, daemon=True)
        bg_thread.start()
        print("[*] Background sync worker initiated.")
    else:
        print("[!] WARNING: Email credentials not configured. Background sync disabled.")

    print(f"[*] Starting server on http://0.0.0.0:5000")
    print("="*50 + "\n")

    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
