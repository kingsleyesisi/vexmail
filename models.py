# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid
import json

db = SQLAlchemy()

class Email(db.Model):
    __tablename__ = 'emails'
    
    # Primary fields
    id = db.Column(db.String(50), primary_key=True)  # IMAP UID or Message-ID hash
    uid_validity = db.Column(db.String(50), nullable=False)
    message_id = db.Column(db.String(255), unique=True, index=True)
    thread_id = db.Column(db.String(255), index=True)
    
    # Email content
    subject = db.Column(db.Text)
    sender_name = db.Column(db.String(255))
    sender_email = db.Column(db.String(255), index=True)
    recipient = db.Column(db.String(255))
    cc = db.Column(db.Text)  # JSON array
    bcc = db.Column(db.Text)  # JSON array
    
    # Email body and content
    body = db.Column(db.Text)
    html_content = db.Column(db.Text)
    text_content = db.Column(db.Text)
    
    # Metadata
    date = db.Column(db.DateTime, index=True)
    size = db.Column(db.Integer, default=0)
    priority = db.Column(db.String(20), default='normal')  # 'low', 'normal', 'high'
    importance = db.Column(db.String(20), default='normal')
    
    # Status flags
    is_read = db.Column(db.Boolean, default=False, index=True)
    is_deleted = db.Column(db.Boolean, default=False, index=True)
    is_flagged = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)
    is_starred = db.Column(db.Boolean, default=False)
    
    # Security and analysis
    is_suspicious = db.Column(db.Boolean, default=False)
    suspicious_reasons = db.Column(db.Text)  # JSON array
    security_info = db.Column(db.Text)  # JSON object
    
    # Headers and raw data
    raw_headers = db.Column(db.Text)  # JSON object
    references = db.Column(db.Text)  # JSON array
    in_reply_to = db.Column(db.String(255))
    
    # Attachments
    attachments_info = db.Column(db.Text)  # JSON array
    attachment_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    operations = db.relationship('EmailOperation', backref='email', lazy='dynamic', cascade='all, delete-orphan')
    attachments = db.relationship('EmailAttachment', backref='email', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert email to dictionary"""
        return {
            'id': self.id,
            'subject': self.subject,
            'from': self.sender_name,
            'email': self.sender_email,
            'body': self.body,
            'date': self.date.strftime("%b %d, %Y %I:%M %p") if self.date else '',
            'preview': self.body[:150] + "..." if self.body and len(self.body) > 150 else (self.body or ''),
            'is_read': self.is_read,
            'is_flagged': self.is_flagged,
            'is_starred': self.is_starred,
            'priority': self.priority,
            'size': self.size,
            'attachment_count': self.attachment_count,
            'thread_id': self.thread_id
        }
    
    def get_cc_list(self):
        """Get CC recipients as list"""
        if self.cc:
            try:
                return json.loads(self.cc)
            except:
                return []
        return []
    
    def get_bcc_list(self):
        """Get BCC recipients as list"""
        if self.bcc:
            try:
                return json.loads(self.bcc)
            except:
                return []
        return []
    
    def get_suspicious_reasons(self):
        """Get suspicious reasons as list"""
        if self.suspicious_reasons:
            try:
                return json.loads(self.suspicious_reasons)
            except:
                return []
        return []

class EmailOperation(db.Model):
    __tablename__ = 'email_operations'
    
    id = db.Column(db.String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    email_uid = db.Column(db.String(50), db.ForeignKey('emails.id'), nullable=False, index=True)
    operation_type = db.Column(db.String(20), nullable=False, index=True)  # 'read', 'unread', 'delete', 'flag', 'archive'
    
    # Status tracking
    status = db.Column(db.String(20), default='pending', index=True)  # 'pending', 'processing', 'success', 'failed'
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    
    # Additional data
    operation_data = db.Column(db.Text)  # JSON object for additional operation data
    error_message = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_retry = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    def to_dict(self):
        """Convert operation to dictionary"""
        return {
            'id': self.id,
            'email_uid': self.email_uid,
            'operation_type': self.operation_type,
            'status': self.status,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_retry': self.last_retry.isoformat() if self.last_retry else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message
        }

class EmailAttachment(db.Model):
    __tablename__ = 'email_attachments'
    
    id = db.Column(db.String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    email_id = db.Column(db.String(50), db.ForeignKey('emails.id'), nullable=False, index=True)
    
    # Attachment metadata
    filename = db.Column(db.String(500), nullable=False)
    content_type = db.Column(db.String(100))
    size = db.Column(db.BigInteger)
    checksum = db.Column(db.String(64), index=True)  # SHA256 hash
    
    # Storage information
    storage_path = db.Column(db.String(1000))  # Local file path
    storage_provider = db.Column(db.String(50), default='local')  # 'local', 's3', 'minio'
    storage_bucket = db.Column(db.String(255), nullable=True)  # Not used for local storage
    
    # Security and processing
    is_scanned = db.Column(db.Boolean, default=False)
    is_safe = db.Column(db.Boolean, default=True)
    scan_results = db.Column(db.Text)  # JSON object
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    scanned_at = db.Column(db.DateTime)
    
    def to_dict(self):
        """Convert attachment to dictionary"""
        return {
            'id': self.id,
            'email_id': self.email_id,
            'filename': self.filename,
            'content_type': self.content_type,
            'size': self.size,
            'checksum': self.checksum,
            'storage_path': self.storage_path,
            'is_safe': self.is_safe,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255))
    
    # IMAP configuration
    imap_server = db.Column(db.String(255))
    imap_username = db.Column(db.String(255))
    imap_password = db.Column(db.String(255))  # Should be encrypted
    imap_mailbox = db.Column(db.String(100), default='INBOX')
    imap_ssl = db.Column(db.Boolean, default=True)
    imap_port = db.Column(db.Integer, default=993)
    
    # User preferences
    preferences = db.Column(db.Text)  # JSON object
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    last_sync = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert user to dictionary (excluding sensitive data)"""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'imap_server': self.imap_server,
            'imap_mailbox': self.imap_mailbox,
            'is_active': self.is_active,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class EmailThread(db.Model):
    __tablename__ = 'email_threads'
    
    id = db.Column(db.String(255), primary_key=True)  # thread_id
    subject = db.Column(db.Text)
    email_count = db.Column(db.Integer, default=1)
    last_email_date = db.Column(db.DateTime, index=True)
    participants = db.Column(db.Text)  # JSON array of email addresses
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_participants_list(self):
        """Get participants as list"""
        if self.participants:
            try:
                return json.loads(self.participants)
            except:
                return []
        return []
    
    def to_dict(self):
        """Convert thread to dictionary"""
        return {
            'id': self.id,
            'subject': self.subject,
            'email_count': self.email_count,
            'last_email_date': self.last_email_date.isoformat() if self.last_email_date else None,
            'participants': self.get_participants_list(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(50), db.ForeignKey('users.id'), nullable=False, index=True)
    email_id = db.Column(db.String(50), db.ForeignKey('emails.id'), nullable=True, index=True)
    
    # Notification content
    type = db.Column(db.String(50), nullable=False, index=True)  # 'new_email', 'sync_complete', 'error'
    title = db.Column(db.String(255))
    message = db.Column(db.Text)
    data = db.Column(db.Text)  # JSON object
    
    # Status
    is_read = db.Column(db.Boolean, default=False, index=True)
    is_sent = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    read_at = db.Column(db.DateTime)
    sent_at = db.Column(db.DateTime)
    
    def to_dict(self):
        """Convert notification to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'email_id': self.email_id,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'is_read': self.is_read,
            'is_sent': self.is_sent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None
        }