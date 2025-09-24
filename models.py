"""
Database models for VexMail - Gmail-style email client
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid
import json
import hashlib

db = SQLAlchemy()

class Email(db.Model):
    """Email model with Gmail-style features"""
    __tablename__ = 'emails'
    
    # Primary identifiers
    id = db.Column(db.String(50), primary_key=True)
    message_id = db.Column(db.String(255), unique=True, index=True)
    thread_id = db.Column(db.String(255), index=True)
    
    # Email headers and content
    subject = db.Column(db.Text)
    sender_name = db.Column(db.String(255))
    sender_email = db.Column(db.String(255), index=True)
    recipient_emails = db.Column(db.Text)  # JSON array of recipients
    cc_emails = db.Column(db.Text)  # JSON array
    bcc_emails = db.Column(db.Text)  # JSON array
    
    # Email body content
    html_content = db.Column(db.Text)
    text_content = db.Column(db.Text)
    
    # Email metadata
    date_received = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    size_bytes = db.Column(db.Integer, default=0)
    
    # Gmail-style status flags
    is_read = db.Column(db.Boolean, default=False, index=True)
    is_starred = db.Column(db.Boolean, default=False, index=True)
    is_important = db.Column(db.Boolean, default=False, index=True)
    is_archived = db.Column(db.Boolean, default=False, index=True)
    is_deleted = db.Column(db.Boolean, default=False, index=True)
    is_spam = db.Column(db.Boolean, default=False, index=True)
    
    # Labels and categories (Gmail-style)
    labels = db.Column(db.Text)  # JSON array of label names
    category = db.Column(db.String(50), default='primary')  # primary, social, promotions, updates
    
    # Attachments
    has_attachments = db.Column(db.Boolean, default=False)
    attachment_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    attachments = db.relationship('EmailAttachment', backref='email', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(Email, self).__init__(**kwargs)
        if not self.id:
            self.id = self.generate_id()
    
    def generate_id(self):
        """Generate unique email ID from message_id or create new UUID"""
        if self.message_id:
            return hashlib.md5(self.message_id.encode()).hexdigest()
        return str(uuid.uuid4())
    
    def get_recipients(self):
        """Get list of recipient email addresses"""
        if self.recipient_emails:
            try:
                return json.loads(self.recipient_emails)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    def get_cc_recipients(self):
        """Get list of CC recipients"""
        if self.cc_emails:
            try:
                return json.loads(self.cc_emails)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    def get_labels(self):
        """Get list of email labels"""
        if self.labels:
            try:
                return json.loads(self.labels)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    def add_label(self, label_name):
        """Add a label to the email"""
        current_labels = self.get_labels()
        if label_name not in current_labels:
            current_labels.append(label_name)
            self.labels = json.dumps(current_labels)
    
    def remove_label(self, label_name):
        """Remove a label from the email"""
        current_labels = self.get_labels()
        if label_name in current_labels:
            current_labels.remove(label_name)
            self.labels = json.dumps(current_labels)
    
    def get_preview_text(self, length=150):
        """Get email preview text for list view"""
        content = self.text_content or self.html_content or ''
        if len(content) > length:
            return content[:length] + '...'
        return content
    
    def to_dict(self, include_content=False):
        """Convert email to dictionary for API responses"""
        data = {
            'id': self.id,
            'message_id': self.message_id,
            'thread_id': self.thread_id,
            'subject': self.subject or '(No Subject)',
            'sender_name': self.sender_name,
            'sender_email': self.sender_email,
            'recipients': self.get_recipients(),
            'cc_recipients': self.get_cc_recipients(),
            'date_received': self.date_received.isoformat() if self.date_received else None,
            'date_display': self.date_received.strftime('%b %d') if self.date_received else '',
            'size_bytes': self.size_bytes,
            'is_read': self.is_read,
            'is_starred': self.is_starred,
            'is_important': self.is_important,
            'is_archived': self.is_archived,
            'labels': self.get_labels(),
            'category': self.category,
            'has_attachments': self.has_attachments,
            'attachment_count': self.attachment_count,
            'preview_text': self.get_preview_text()
        }
        
        if include_content:
            data.update({
                'html_content': self.html_content,
                'text_content': self.text_content
            })
        
        return data

class EmailThread(db.Model):
    """Email thread/conversation model"""
    __tablename__ = 'email_threads'
    
    id = db.Column(db.String(255), primary_key=True)
    subject_hash = db.Column(db.String(64), index=True)  # Hash of normalized subject
    participants = db.Column(db.Text)  # JSON array of participant emails
    email_count = db.Column(db.Integer, default=1)
    last_email_date = db.Column(db.DateTime, index=True)
    has_unread = db.Column(db.Boolean, default=False, index=True)
    is_starred = db.Column(db.Boolean, default=False)
    labels = db.Column(db.Text)  # JSON array of labels
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_participants(self):
        """Get list of thread participants"""
        if self.participants:
            try:
                return json.loads(self.participants)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    def add_participant(self, email_address):
        """Add participant to thread"""
        current_participants = self.get_participants()
        if email_address not in current_participants:
            current_participants.append(email_address)
            self.participants = json.dumps(current_participants)
    
    def to_dict(self):
        """Convert thread to dictionary"""
        return {
            'id': self.id,
            'subject_hash': self.subject_hash,
            'participants': self.get_participants(),
            'email_count': self.email_count,
            'last_email_date': self.last_email_date.isoformat() if self.last_email_date else None,
            'has_unread': self.has_unread,
            'is_starred': self.is_starred,
            'labels': json.loads(self.labels) if self.labels else []
        }

class EmailAttachment(db.Model):
    """Email attachment model"""
    __tablename__ = 'email_attachments'
    
    id = db.Column(db.String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    email_id = db.Column(db.String(50), db.ForeignKey('emails.id'), nullable=False, index=True)
    
    filename = db.Column(db.String(500), nullable=False)
    content_type = db.Column(db.String(100))
    size_bytes = db.Column(db.BigInteger)
    
    # Local storage information
    storage_path = db.Column(db.String(1000))
    checksum = db.Column(db.String(64))  # SHA256 hash
    
    # Security flags
    is_safe = db.Column(db.Boolean, default=True)
    scan_result = db.Column(db.Text)  # JSON object with scan details
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert attachment to dictionary"""
        return {
            'id': self.id,
            'filename': self.filename,
            'content_type': self.content_type,
            'size_bytes': self.size_bytes,
            'size_display': self.get_size_display(),
            'is_safe': self.is_safe,
            'download_url': f'/api/attachments/{self.id}/download'
        }
    
    def get_size_display(self):
        """Get human-readable file size"""
        if not self.size_bytes:
            return '0 B'
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.size_bytes < 1024.0:
                return f"{self.size_bytes:.1f} {unit}"
            self.size_bytes /= 1024.0
        return f"{self.size_bytes:.1f} TB"

class EmailLabel(db.Model):
    """Gmail-style email labels"""
    __tablename__ = 'email_labels'
    
    id = db.Column(db.String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(7), default='#cccccc')  # Hex color code
    is_system = db.Column(db.Boolean, default=False)  # System labels like Inbox, Sent, etc.
    email_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert label to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'color': self.color,
            'is_system': self.is_system,
            'email_count': self.email_count
        }

def init_system_labels():
    """Initialize system labels (Inbox, Sent, Drafts, etc.)"""
    system_labels = [
        {'name': 'inbox', 'display_name': 'Inbox', 'color': '#1a73e8'},
        {'name': 'sent', 'display_name': 'Sent', 'color': '#34a853'},
        {'name': 'drafts', 'display_name': 'Drafts', 'color': '#ea4335'},
        {'name': 'spam', 'display_name': 'Spam', 'color': '#fbbc04'},
        {'name': 'trash', 'display_name': 'Trash', 'color': '#5f6368'},
        {'name': 'starred', 'display_name': 'Starred', 'color': '#fbbc04'},
        {'name': 'important', 'display_name': 'Important', 'color': '#ea4335'},
    ]
    
    for label_data in system_labels:
        existing_label = EmailLabel.query.filter_by(name=label_data['name']).first()
        if not existing_label:
            label = EmailLabel(
                name=label_data['name'],
                display_name=label_data['display_name'],
                color=label_data['color'],
                is_system=True
            )
            db.session.add(label)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error initializing system labels: {e}")