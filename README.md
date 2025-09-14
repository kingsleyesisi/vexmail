# VexMail

A modern, scalable email client built with Flask, featuring real-time updates, IMAP IDLE support, and a robust microservices architecture.

## Architecture Overview

VexMail implements a comprehensive email management system with the following components:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   IMAP Providers│    │  Flask Backend   │    │  Realtime & Queue│
│                 │    │                  │    │                 │
│ Gmail/Office365 │◄──►│ IMAP Manager     │◄──►│ Redis Cache     │
│ Custom IMAP     │    │ Webhook/REST API │    │ Celery/RQ       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                         │
                                ▼                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Durable Storage│    │  Workers & Proc  │    │    Frontend     │
│                  │    │                  │    │                 │
│ PostgreSQL      │◄──►│ Email Parser     │◄──►│ SPA (Virtual    │
│ S3/MinIO        │    │ Background Jobs  │    │  Scroll)        │
│ Retry Queue     │    │ Notifications    │    │ Real-time UI    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Features

### Core Features
- **Real-time Email Sync**: IMAP IDLE support for instant email notifications
- **Modern Web Interface**: Responsive SPA with virtual scrolling for large inboxes
- **Advanced Search**: Full-text search across emails with debounced input
- **Batch Operations**: Select multiple emails for bulk actions
- **Attachment Management**: Secure attachment storage with virus scanning
- **Email Threading**: Intelligent conversation grouping

### Technical Features
- **Connection Pooling**: Efficient IMAP connection management
- **Background Processing**: Celery workers for async operations
- **Caching**: Redis-based caching for improved performance
- **Event Streaming**: Server-Sent Events for real-time updates
- **Error Handling**: Comprehensive error tracking and retry mechanisms
- **Monitoring**: Health checks and performance metrics
- **Docker Support**: Complete containerized deployment

## Quick Start

### Using Docker Compose (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd vexmail
   ```

2. **Configure environment**
   ```bash
   cp env.example .env
   # Edit .env with your IMAP credentials and settings
   ```

3. **Start all services**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Web Interface: http://localhost:5000
   - Flower (Celery Monitor): http://localhost:5555
   - MinIO Console: http://localhost:9001

### Manual Installation

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up services**
   - PostgreSQL database
   - Redis server
   - MinIO or AWS S3 for storage

3. **Configure environment**
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

4. **Run database migrations**
   ```bash
   python -c "from app import app, db; app.app_context().push(); db.create_all()"
   ```

5. **Start the application**
   ```bash
   python app.py
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@localhost/vexmail` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `IMAP_SERVER` | IMAP server hostname | Required |
| `EMAIL_USER` | Email username | Required |
| `EMAIL_PASS` | Email password/app password | Required |
| `STORAGE_PROVIDER` | Storage provider (s3/minio) | `minio` |
| `STORAGE_ENDPOINT_URL` | Storage endpoint URL | `http://localhost:9000` |
| `SECRET_KEY` | Flask secret key | Change in production |

### IMAP Configuration

#### Gmail
```
IMAP_SERVER=imap.gmail.com
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your-app-password
```

#### Office 365
```
IMAP_SERVER=outlook.office365.com
EMAIL_USER=your-email@company.com
EMAIL_PASS=your-password
```

#### Custom IMAP
```
IMAP_SERVER=your-imap-server.com
EMAIL_USER=your-username
EMAIL_PASS=your-password
IMAP_MAILBOX=INBOX
```

## API Documentation

### Authentication
Currently, VexMail uses a single-user model. Multi-user support can be added by implementing proper authentication.

### Endpoints

#### Email Management
- `GET /api/emails` - List emails with pagination
- `GET /api/emails/search` - Search emails
- `GET /api/email/<id>` - Get email details
- `POST /api/emails/<id>/read` - Mark as read
- `POST /api/emails/<id>/unread` - Mark as unread
- `POST /api/emails/<id>/flag` - Flag/unflag email
- `POST /api/emails/<id>/star` - Star/unstar email
- `DELETE /api/emails/<id>` - Delete email
- `POST /api/emails/batch` - Batch operations

#### Attachments
- `GET /api/email/<id>/attachments` - List email attachments
- `GET /api/attachment/<id>/download` - Download attachment

#### System
- `GET /api/status` - System health status
- `GET /api/stats` - System statistics
- `POST /api/sync` - Trigger email sync
- `GET /api/events` - Server-Sent Events stream

### Real-time Events

The `/api/events` endpoint provides real-time updates via Server-Sent Events:

```javascript
const eventSource = new EventSource('/api/events');
eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    // Handle: email_received, email_read, email_deleted, etc.
};
```

## Development

### Project Structure
```
vexmail/
├── app.py                 # Main Flask application
├── models.py              # Database models
├── redis_client.py        # Redis cache and pub/sub
├── imap_manager.py        # IMAP connection management
├── email_parser.py        # Email parsing and sanitization
├── storage_client.py      # S3/MinIO storage client
├── tasks.py               # Celery background tasks
├── celery_config.py       # Celery configuration
├── monitoring.py          # Error handling and monitoring
├── templates/
│   └── index.html         # Frontend SPA
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
├── docker-compose.yml    # Multi-service deployment
└── README.md            # This file
```

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-flask

# Run tests
pytest
```

### Code Style
```bash
# Install linting tools
pip install flake8 black

# Format code
black .

# Lint code
flake8 .
```

## Deployment

### Production Considerations

1. **Security**
   - Use strong `SECRET_KEY`
   - Enable HTTPS
   - Configure firewall rules
   - Use environment variables for secrets

2. **Performance**
   - Configure Redis persistence
   - Set up database connection pooling
   - Use CDN for static assets
   - Enable gzip compression

3. **Monitoring**
   - Set up log aggregation
   - Configure health check endpoints
   - Monitor system resources
   - Set up alerting

### Scaling

VexMail is designed to scale horizontally:

- **Web Servers**: Multiple Flask instances behind a load balancer
- **Workers**: Scale Celery workers based on load
- **Database**: Read replicas for read-heavy workloads
- **Storage**: S3 with CloudFront for global distribution

## Troubleshooting

### Common Issues

1. **IMAP Connection Failed**
   - Check credentials and server settings
   - Ensure IMAP is enabled on your email account
   - Use app passwords for Gmail

2. **Redis Connection Error**
   - Verify Redis is running
   - Check connection string in environment

3. **Database Connection Issues**
   - Ensure PostgreSQL is running
   - Check database credentials
   - Verify database exists

4. **Storage Errors**
   - Check MinIO/S3 configuration
   - Verify bucket exists and is accessible
   - Check storage credentials

### Logs

View logs for each service:
```bash
# Web application
docker-compose logs web

# Celery worker
docker-compose logs worker

# All services
docker-compose logs -f
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review the API documentation

---

**VexMail** - Modern email management made simple.