# VexMail - Modern Gmail-like Email Client

A modern, scalable email client built with Flask, featuring intelligent caching, real-time updates, and a Gmail-like user interface.

## 🚀 Features

### Core Features
- **Gmail-like Interface**: Clean, responsive design with familiar Gmail-style layout
- **Real-time Updates**: Instant email notifications without page refresh
- **Intelligent Caching**: Smart caching system that reduces server load and improves performance
- **Advanced Search**: Full-text search across emails with instant results
- **Email Management**: Read, star, flag, delete emails with batch operations
- **Attachment Support**: Secure attachment storage and download
- **Email Threading**: Intelligent conversation grouping

### Technical Features
- **Modular Architecture**: Clean separation of concerns with service-based architecture
- **Intelligent Caching**: Multi-layer caching (memory + file) with automatic invalidation
- **Real-time Service**: WebSocket-like real-time updates using long-polling
- **IMAP Integration**: Efficient IMAP connection pooling with IDLE support
- **Local Storage**: All data stored locally (SQLite + file system)
- **Performance Optimized**: Virtual scrolling, debounced search, and optimized queries

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │  Flask Backend   │    │    Services     │
│                 │    │                  │    │                 │
│ Gmail-like UI   │◄──►│ REST API         │◄──►│ Email Service   │
│ Real-time       │    │ Real-time Events │    │ Cache Service   │
│ Updates         │    │                  │    │ Realtime Service│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                         │
                                ▼                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Data Layer    │    │  External APIs   │    │   Background    │
│                 │    │                  │    │                 │
│ SQLite Database │◄──►│ IMAP Manager     │◄──►│ IMAP IDLE       │
│ Local Storage   │    │ Email Parser     │    │ Monitoring      │
│ File Cache      │    │ Storage Client   │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 📁 Project Structure

```
vexmail/
├── app.py                     # Main Flask application
├── models.py                  # Database models
├── imap_manager.py           # IMAP connection management
├── email_parser.py           # Email parsing and sanitization
├── storage_client.py         # Local file storage
├── init_db.py               # Database initialization
├── services/                 # Service layer
│   ├── __init__.py
│   ├── email_service.py     # Email business logic
│   ├── cache_service.py     # Intelligent caching
│   └── realtime_service.py  # Real-time updates
├── templates/
│   └── index.html           # Gmail-like frontend
├── instance/
│   └── vexmail.db          # SQLite database
├── attachments/            # Email attachments storage
├── cache/                  # File-based cache
├── requirements.txt        # Python dependencies
├── .env                   # Configuration
└── README.md             # This file
```

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8+
- IMAP email account (Gmail, Outlook, etc.)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd vexmail
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp env.example .env
   # Edit .env with your email settings
   ```

4. **Initialize database**
   ```bash
   python init_db.py
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Access the application**
   Open your browser and go to: `http://localhost:5000`

### Configuration

Edit the `.env` file with your email settings:

```env
# IMAP Configuration
IMAP_SERVER=imap.gmail.com
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your-app-password
IMAP_MAILBOX=INBOX

# Database (SQLite)
DATABASE_URL=sqlite:///instance/vexmail.db

# Storage (Local)
STORAGE_PROVIDER=local
STORAGE_PATH=./attachments
STORAGE_MAX_SIZE=104857600

# Security
SECRET_KEY=your-secret-key-change-in-production
```

#### Gmail Setup
1. Enable 2-factor authentication
2. Generate an app password: [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Use the app password in `EMAIL_PASS`

#### Outlook/Office 365 Setup
```env
IMAP_SERVER=outlook.office365.com
EMAIL_USER=your-email@outlook.com
EMAIL_PASS=your-password
```

## 🎯 Key Improvements Made

### 1. Modular Architecture
- **Service Layer**: Separated business logic into dedicated services
- **Clean Separation**: Clear boundaries between data, business logic, and presentation
- **Maintainable Code**: Easy to test, debug, and extend

### 2. Intelligent Caching System
- **Multi-layer Caching**: Memory + file-based caching for optimal performance
- **Smart Invalidation**: Automatic cache invalidation when data changes
- **Cache Statistics**: Built-in monitoring and performance metrics
- **Persistent Cache**: Survives application restarts

### 3. Real-time Updates
- **Instant Notifications**: New emails appear immediately without refresh
- **Long-polling**: Efficient real-time communication
- **Event-driven**: Clean event system for real-time updates
- **Client Management**: Automatic cleanup of disconnected clients

### 4. Enhanced User Experience
- **Gmail-like Interface**: Familiar and intuitive design
- **Responsive Design**: Works perfectly on all devices
- **Performance Optimized**: Fast loading and smooth interactions
- **Smart Search**: Debounced search with caching

### 5. Removed Unused Components
- Removed Redis dependency (replaced with file-based caching)
- Removed Celery (replaced with threading)
- Removed unused monitoring and task files
- Simplified deployment requirements

## 🔧 API Documentation

### Email Endpoints
- `GET /api/emails` - Get emails with pagination and caching
- `GET /api/emails/search` - Search emails with caching
- `GET /api/email/<id>` - Get email details with caching
- `POST /api/emails/<id>/read` - Mark email as read
- `POST /api/emails/<id>/star` - Star/unstar email
- `POST /api/emails/<id>/flag` - Flag/unflag email
- `DELETE /api/emails/<id>` - Delete email
- `POST /api/emails/batch` - Batch operations

### Real-time Endpoints
- `POST /api/realtime/register` - Register for real-time updates
- `GET /api/realtime/events/<client_id>` - Get real-time events (long-polling)

### System Endpoints
- `GET /api/status` - System health status
- `GET /api/stats` - System statistics
- `POST /api/sync` - Trigger email synchronization

## 🚀 Performance Features

### Caching Strategy
1. **Email Lists**: Cached for 5 minutes, invalidated on updates
2. **Email Details**: Cached for 1 hour, invalidated on updates
3. **Search Results**: Cached for 5 minutes
4. **Statistics**: Cached for 5 minutes

### Real-time Updates
- New emails appear instantly
- Status changes (read/unread, star, flag) update immediately
- Sync progress shown in real-time
- Automatic reconnection on connection loss

### Performance Optimizations
- Virtual scrolling for large email lists
- Debounced search (300ms delay)
- Intelligent cache invalidation
- Optimized database queries
- Background IMAP monitoring

## 🔍 Monitoring & Debugging

### Cache Statistics
```bash
curl http://localhost:5000/api/stats
```

### System Health
```bash
curl http://localhost:5000/api/status
```

### Real-time Service Stats
The `/api/stats` endpoint includes real-time service statistics:
- Connected clients
- Event queue sizes
- Client subscriptions

## 🛡️ Security Features

- **Email Sanitization**: HTML content sanitized to prevent XSS
- **Attachment Scanning**: Basic file type validation
- **Secure Storage**: Local file storage with proper permissions
- **Input Validation**: All user inputs validated and sanitized

## 🚀 Deployment

### Development
```bash
python app.py
```

### Production
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Docker (Optional)
```bash
docker build -t vexmail .
docker run -p 5000:5000 -v $(pwd)/.env:/app/.env vexmail
```

## 🔧 Troubleshooting

### Common Issues

1. **IMAP Connection Failed**
   - Check credentials and server settings
   - Ensure IMAP is enabled on your email account
   - Use app passwords for Gmail

2. **Cache Issues**
   - Check cache directory permissions
   - Clear cache: `rm -rf cache/*`

3. **Database Issues**
   - Reinitialize: `python init_db.py`
   - Check file permissions

4. **Real-time Updates Not Working**
   - Check browser console for errors
   - Verify `/api/realtime/register` endpoint

### Logs
Application logs are printed to console. For production, configure proper logging:

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('vexmail.log'),
        logging.StreamHandler()
    ]
)
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**VexMail** - A modern, intelligent email client that brings Gmail-like experience with powerful caching and real-time features.