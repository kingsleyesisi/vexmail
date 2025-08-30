from flask import Flask, render_template, jsonify, request
import imaplib
import email
from email.header import decode_header
from datetime import datetime
import re
from decouple import config
from models import db, Email, EmailOperation
import threading
import time
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vexmail.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    db.create_all()

def get_email_body(msg):
    """
    Parses an email message and returns the body content.
    It prioritizes the plain text part of multipart emails.
    """
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="ignore")
                except (UnicodeDecodeError, AttributeError):
                    body = part.get_payload(decode=True).decode("latin-1", errors="ignore")
                break
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="ignore")
        except (UnicodeDecodeError, AttributeError):
            body = msg.get_payload(decode=True).decode("latin-1", errors="ignore")
    return body

def decode_header_part(header_part):
    """
    Decodes a header part, returning it as a UTF-8 string.
    """
    decoded, encoding = header_part
    if isinstance(decoded, bytes):
        return decoded.decode(encoding or "utf-8", errors="ignore")
    return decoded

def extract_email_from_string(email_string):
    """Extract email address from a string like 'John Doe <john@example.com>'"""
    email_pattern = r'<(.+?)>'
    match = re.search(email_pattern, email_string)
    if match:
        return match.group(1)
    return email_string

def get_imap_connection():
    """Get IMAP connection"""
    try:
        IMAP_SERVER = config("IMAP_SERVER")
        EMAIL_USER = config("EMAIL_USER")
        EMAIL_PASS = config("EMAIL_PASS")
        
        print(f"Connecting to IMAP server: {IMAP_SERVER}")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select('INBOX')
        print("IMAP connection successful")
        return mail
    except Exception as e:
        print(f"Error connecting to IMAP: {e}")
        raise

def get_uid_validity():
    """Get UIDVALIDITY - using timestamp for reliability"""
    return str(int(time.time()))

def sync_emails_with_db():
    """Sync emails from IMAP with local database"""
    mail = None
    try:
        mail = get_imap_connection()
        
        # Use timestamp as UIDVALIDITY (more reliable than IMAP command)
        uid_validity = get_uid_validity()
        print(f"Using UIDVALIDITY: {uid_validity}")
        
        # Check if we need to resync
        existing_emails = Email.query.all()
        if existing_emails and existing_emails[0].uid_validity == uid_validity:
            print("No resync needed - UIDVALIDITY unchanged")
            return  # No need to resync
        
        # Clear existing emails if UIDVALIDITY changed
        if existing_emails and existing_emails[0].uid_validity != uid_validity:
            print(f"UIDVALIDITY changed from {existing_emails[0].uid_validity} to {uid_validity}")
            Email.query.delete()
            db.session.commit()
        
        # Fetch emails from IMAP
        status, messages = mail.search(None, 'ALL')
        if status != 'OK':
            print(f"Failed to search emails: {status}")
            return
        
        message_ids = messages[0].split()
        total = len(message_ids)
        print(f"Found {total} emails in INBOX")
        if total == 0:
            print("No emails found in INBOX")
            return
        
        # Take the last 20 IDs and reverse them so highest ID (newest) comes first
        last_ids = message_ids[-20:][::-1] if total >= 20 else message_ids[::-1]
        print(f"Processing {len(last_ids)} emails")
        
        # Collect all emails to add in a single transaction
        emails_to_add = []
        
        for eid in last_ids:
            try:
                uid = eid.decode()
                
                # Check if email already exists in DB
                existing_email = Email.query.get(uid)
                if existing_email:
                    continue
                
                status, msg_data = mail.fetch(eid, '(RFC822)')
                if status != 'OK':
                    print(f"Failed to fetch email {uid}: {status}")
                    continue
                
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                subject_hdr = decode_header(msg.get("Subject", ""))[0]
                from_hdr = decode_header(msg.get("From", ""))[0]
                date_hdr = msg.get("Date", "")
                
                subject = decode_header_part(subject_hdr)
                sender = decode_header_part(from_hdr)
                body = get_email_body(msg)
                
                # Extract email address and name
                email_address = extract_email_from_string(sender)
                sender_name = sender.replace(f'<{email_address}>', '').strip()
                if not sender_name:
                    sender_name = email_address
                
                # Parse date
                try:
                    date_obj = email.utils.parsedate_to_datetime(date_hdr)
                except:
                    date_obj = datetime.utcnow()
                
                # Check if email is read (has \Seen flag)
                status, flags_data = mail.fetch(eid, '(FLAGS)')
                is_read = False
                if status == 'OK':
                    flags = flags_data[0].decode()
                    is_read = '\\Seen' in flags
                
                # Create email record
                email_record = Email(
                    id=uid,
                    uid_validity=uid_validity,
                    subject=subject,
                    sender_name=sender_name,
                    sender_email=email_address,
                    body=body,
                    date=date_obj,
                    is_read=is_read
                )
                
                emails_to_add.append(email_record)
                print(f"Prepared email {uid}: {subject[:50]}...")
                
            except Exception as e:
                print(f"Error processing email {eid}: {e}")
                continue
        
        # Add all emails in a single transaction
        if emails_to_add:
            try:
                db.session.add_all(emails_to_add)
                db.session.commit()
                print(f"Successfully added {len(emails_to_add)} emails to database")
            except Exception as e:
                db.session.rollback()
                print(f"Error committing emails to database: {e}")
        
        print("Email sync completed successfully")
        
    except Exception as e:
        print(f"Error syncing emails: {e}")
        if 'db' in locals():
            db.session.rollback()
    finally:
        if mail:
            try:
                mail.logout()
            except:
                pass

def execute_imap_operation(operation):
    """Execute IMAP operation with retry logic"""
    try:
        mail = get_imap_connection()
        
        if operation.operation_type in ['read', 'unread']:
            flag_command = '+FLAGS' if operation.operation_type == 'read' else '-FLAGS'
            status, data = mail.uid('STORE', operation.email_uid, flag_command, '(\\Seen)')
            success = status == 'OK'
        elif operation.operation_type == 'delete':
            # Mark as deleted
            status, data = mail.uid('STORE', operation.email_uid, '+FLAGS', '(\\Deleted)')
            if status == 'OK':
                # Expunge to actually delete
                status, data = mail.expunge()
                success = status == 'OK'
            else:
                success = False
        else:
            success = False
        
        mail.logout()
        return success
        
    except Exception as e:
        print(f"Error executing IMAP operation: {e}")
        return False

def process_operation_queue():
    """Process pending email operations"""
    while True:
        try:
            with app.app_context():
                pending_ops = EmailOperation.query.filter_by(status='pending').all()
                
                for op in pending_ops:
                    if op.retry_count >= op.max_retries:
                        op.status = 'failed'
                        db.session.commit()
                        continue
                    
                    success = execute_imap_operation(op)
                    if success:
                        op.status = 'success'
                        db.session.commit()
                    else:
                        op.retry_count += 1
                        op.last_retry = datetime.utcnow()
                        db.session.commit()
                
                time.sleep(5)  # Wait 5 seconds before next check
                
        except Exception as e:
            print(f"Error in operation queue: {e}")
            time.sleep(10)

def get_emails(page, per_page):
    """Fetch emails from database with pagination"""
    sync_emails_with_db()
    emails = Email.query.filter_by(is_deleted=False).order_by(Email.date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return {
        "total": emails.total,
        "pages": emails.pages,
        "current_page": emails.page,
        "per_page": emails.per_page,
        "emails": [{
            "id": email.id,
            "subject": email.subject,
            "from": email.sender_name,
            "email": email.sender_email,
            "body": email.body,
            "date": email.date.strftime("%b %d, %Y %I:%M %p"),
            "preview": email.body[:150] + "..." if len(email.body) > 150 else email.body,
            "is_read": email.is_read
        } for email in emails.items]   
    }

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/emails')
def api_emails():
    """API endpoint to get emails with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    result = get_emails(page, per_page)
    return jsonify(result)

@app.route('/api/emails/all')
def api_all_emails():
    """API endpoint to get all emails (for backward compatibility)"""
    result = get_emails(1, 1000)  # Get all emails
    return jsonify(result["emails"])

@app.route('/api/email/<email_id>')
def api_email_detail(email_id):
    """API endpoint to get specific email details"""
    email = Email.query.get(email_id)
    if email:
        return jsonify({
            "id": email.id,
            "subject": email.subject,
            "from": email.sender_name,
            "email": email.sender_email,
            "body": email.body,
            "date": email.date.strftime("%b %d, %Y %I:%M %p"),
            "is_read": email.is_read
        })
    return jsonify({"error": "Email not found"}), 404

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
        
        return jsonify({"success": True, "email": {
            "id": email.id,
            "is_read": email.is_read
        }})
        
    except Exception as e:
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
        
        return jsonify({"success": True, "email": {
            "id": email.id,
            "is_read": email.is_read
        }})
        
    except Exception as e:
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
        
        return jsonify({"success": True, "message": "Email deleted"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/emails/batch', methods=['POST'])
def batch_operations():
    """Batch operations on emails"""
    try:
        data = request.get_json()
        operation = data.get('operation')
        uids = data.get('uids', [])
        
        if operation not in ['read', 'unread', 'delete']:
            return jsonify({"error": "Invalid operation"}), 400
        
        for uid in uids:
            email = Email.query.get(uid)
            if email:
                if operation == 'read':
                    email.is_read = True
                elif operation == 'unread':
                    email.is_read = False
                elif operation == 'delete':
                    email.is_deleted = True
                
                # Queue IMAP operation
                op = EmailOperation(
                    email_uid=uid,
                    operation_type=operation
                )
                db.session.add(op)
        
        db.session.commit()
        
        return jsonify({"success": True, "message": f"Batch {operation} operation queued"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Start background operation queue processor
def start_background_processor():
    thread = threading.Thread(target=process_operation_queue, daemon=True)
    thread.start()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        start_background_processor()
    app.run(debug=True, host='0.0.0.0', port=5000)