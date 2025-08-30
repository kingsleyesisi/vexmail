# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()

class Email(db.Model):
    id = db.Column(db.String(50), primary_key=True)  # IMAP UID
    uid_validity = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(500))
    sender_name = db.Column(db.String(200))
    sender_email = db.Column(db.String(200))
    body = db.Column(db.Text)
    date = db.Column(db.DateTime)
    is_read = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EmailOperation(db.Model):
    id = db.Column(db.String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    email_uid = db.Column(db.String(50), nullable=False)
    operation_type = db.Column(db.String(20), nullable=False)  # 'read', 'unread', 'delete'
    status = db.Column(db.String(20), default='pending')  # 'pending', 'success', 'failed'
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_retry = db.Column(db.DateTime)