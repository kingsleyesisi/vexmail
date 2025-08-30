# VexMail - Flask + IMAP Email Client

A modern, responsive email client built with Flask and IMAP, featuring read/unread status management, email deletion, and mobile-optimized UI.

## Features

- 📧 **IMAP Email Integration** - Connect to any IMAP server
- 📱 **Mobile Responsive** - Optimized for mobile and desktop
- ✅ **Read/Unread Management** - Mark emails as read/unread with optimistic updates
- 🗑️ **Email Deletion** - Delete emails with confirmation
- 🔄 **Batch Operations** - Select multiple emails for bulk actions
- 💾 **Local Caching** - Fast UI with local database caching
- 🔄 **Background Sync** - Automatic retry queue for failed operations
- 🎨 **Modern UI** - Clean, intuitive interface with Tailwind CSS

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the project root:

```env
IMAP_SERVER=your-imap-server.com
EMAIL_USER=your-email@domain.com
EMAIL_PASS=your-password
```

### 3. Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## API Endpoints

### Email Management

- `GET /api/emails` - Get all emails
- `GET /api/emails/<email_id>` - Get specific email details
- `POST /api/emails/<email_id>/read` - Mark email as read
- `POST /api/emails/<email_id>/unread` - Mark email as unread
- `DELETE /api/emails/<email_id>` - Delete email

### Batch Operations

- `POST /api/emails/batch` - Batch operations on multiple emails
  ```json
  {
    "operation": "read|unread|delete",
    "uids": ["1", "2", "3"]
  }
  ```

## Database Schema

### Email Table
- `id` (String) - IMAP UID (Primary Key)
- `uid_validity` (String) - IMAP UIDVALIDITY
- `subject` (String) - Email subject
- `sender_name` (String) - Sender display name
- `sender_email` (String) - Sender email address
- `body` (Text) - Email body content
- `date` (DateTime) - Email date
- `is_read` (Boolean) - Read status
- `is_deleted` (Boolean) - Deletion status
- `created_at` (DateTime) - Record creation time
- `updated_at` (DateTime) - Record update time

### EmailOperation Table
- `id` (String) - Operation ID (Primary Key)
- `email_uid` (String) - Email UID
- `operation_type` (String) - Operation type (read/unread/delete)
- `status` (String) - Operation status (pending/success/failed)
- `retry_count` (Integer) - Number of retry attempts
- `max_retries` (Integer) - Maximum retry attempts
- `created_at` (DateTime) - Operation creation time
- `last_retry` (DateTime) - Last retry time

## IMAP Operations

### Read/Unread Status
```bash
# Mark as read
UID STORE <uid> +FLAGS (\Seen)

# Mark as unread
UID STORE <uid> -FLAGS (\Seen)
```

### Email Deletion
```bash
# Mark as deleted
UID STORE <uid> +FLAGS (\Deleted)
EXPUNGE
```

## Mobile Features

- **Swipe Actions** - Swipe left on emails to reveal action buttons
- **Touch Optimized** - Large touch targets and intuitive gestures
- **Responsive Design** - Adapts to different screen sizes
- **Mobile Search** - Dedicated mobile search overlay
- **Modal Email View** - Full-screen email viewing on mobile

## Error Handling & Retry Logic

1. **Optimistic Updates** - UI updates immediately for better UX
2. **Operation Queue** - Failed operations are queued for retry
3. **Exponential Backoff** - Retry with increasing delays
4. **Background Processing** - Operations processed in background thread
5. **Reconciliation** - Sync with IMAP server on failures

## Testing

Run the test script to verify functionality:

```bash
python test.py
```

## Development

### Project Structure
```
vexmail/
├── app.py              # Main Flask application
├── models.py           # Database models
├── mail.py             # IMAP utilities
├── templates/
│   └── index.html      # Main UI template
├── requirements.txt    # Python dependencies
├── test.py            # API test script
└── README.md          # This file
```

### Key Components

1. **Database Layer** - SQLAlchemy models for local caching
2. **IMAP Layer** - Connection and operation management
3. **API Layer** - RESTful endpoints for email operations
4. **UI Layer** - Responsive frontend with JavaScript
5. **Background Queue** - Async operation processing

## Troubleshooting

### Common Issues

1. **IMAP Connection Failed**
   - Verify IMAP server settings
   - Check email credentials
   - Ensure IMAP is enabled on your email provider

2. **Database Errors**
   - Delete `vexmail.db` to reset database
   - Check file permissions

3. **Mobile Responsiveness Issues**
   - Clear browser cache
   - Test on different devices

### Logs

Check console output for detailed error messages and operation status.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License. 
