# VexMail Architecture Documentation

## Overview

VexMail is built with a modern, modular architecture that emphasizes performance, maintainability, and scalability. The application follows a service-oriented architecture with clear separation of concerns.

## Architecture Layers

### 1. Presentation Layer
- **Frontend**: Modern Gmail-like interface built with vanilla JavaScript and Tailwind CSS
- **Templates**: Server-side rendered HTML templates
- **Real-time UI**: Dynamic updates without page refresh

### 2. API Layer
- **REST API**: RESTful endpoints for all email operations
- **Real-time API**: Long-polling endpoints for instant updates
- **Error Handling**: Comprehensive error handling and validation

### 3. Service Layer
- **Email Service**: Core email business logic and operations
- **Cache Service**: Intelligent multi-layer caching system
- **Real-time Service**: Event-driven real-time communication

### 4. Data Access Layer
- **Models**: SQLAlchemy ORM models for database operations
- **IMAP Manager**: Efficient IMAP connection pooling and management
- **Storage Client**: Local file system operations for attachments

### 5. External Integration Layer
- **Email Parser**: Advanced email parsing and sanitization
- **IMAP Protocol**: Direct IMAP server communication
- **File System**: Local storage for attachments and cache

## Service Architecture

### Email Service (`services/email_service.py`)

**Responsibilities:**
- Email CRUD operations with caching
- Email synchronization from IMAP servers
- Search functionality with caching
- Real-time event emission
- Cache invalidation management

**Key Features:**
- Intelligent caching with automatic invalidation
- Real-time event broadcasting
- Duplicate email prevention
- Batch operations support
- Performance monitoring

**Caching Strategy:**
```python
# Email lists: 5 minutes TTL
cache_key = f"emails:page:{page}:per_page:{per_page}"

# Email details: 1 hour TTL  
cache_key = f"email:detail:{email_id}"

# Search results: 5 minutes TTL
cache_key = f"search:{query_hash}:page:{page}"
```

### Cache Service (`services/cache_service.py`)

**Responsibilities:**
- Multi-layer caching (memory + file)
- Automatic cache expiration
- Cache statistics and monitoring
- Background cleanup of expired entries

**Architecture:**
```
Memory Cache (Fast Access)
    ↓ (Miss)
File Cache (Persistent)
    ↓ (Miss)
Database/IMAP (Source)
```

**Features:**
- Thread-safe operations
- Automatic cleanup of expired entries
- Cache statistics and hit rate monitoring
- Configurable TTL per cache entry
- Graceful degradation on cache failures

### Real-time Service (`services/realtime_service.py`)

**Responsibilities:**
- Client registration and management
- Event broadcasting to subscribed clients
- Long-polling implementation
- Automatic client cleanup

**Event Types:**
- `email_received`: New email notifications
- `email_updated`: Email status changes
- `email_deleted`: Email deletion notifications
- `sync_status`: Synchronization progress updates
- `heartbeat`: Keep-alive messages

**Client Management:**
```python
clients = {
    'client_id': {
        'id': 'client_id',
        'connected_at': datetime,
        'last_ping': datetime,
        'events': Queue(),
        'subscriptions': set(['email_updates'])
    }
}
```

## Data Flow

### Email Synchronization Flow
```
1. User triggers sync OR IMAP IDLE detects new email
2. IMAP Manager fetches emails from server
3. Email Parser processes raw email content
4. Email Service stores emails in database
5. Cache Service invalidates relevant caches
6. Real-time Service broadcasts events to clients
7. Frontend receives real-time updates
```

### Email Retrieval Flow
```
1. Frontend requests emails
2. Email Service checks cache first
3. If cache miss, query database
4. Cache results for future requests
5. Return paginated results to frontend
```

### Real-time Update Flow
```
1. Email operation (read, star, delete, etc.)
2. Database updated
3. Cache invalidated
4. Real-time event emitted
5. All connected clients receive update
6. Frontend updates UI without refresh
```

## Caching Strategy

### Cache Hierarchy
1. **Memory Cache**: Fastest access, limited size
2. **File Cache**: Persistent across restarts
3. **Database**: Source of truth

### Cache Keys
- `emails:page:{page}:per_page:{per_page}` - Email lists
- `email:detail:{email_id}` - Individual email details
- `search:{query_hash}:page:{page}` - Search results
- `email:stats` - Email statistics

### Cache Invalidation
- **Automatic**: TTL-based expiration
- **Manual**: Triggered by data changes
- **Pattern-based**: Clear multiple related keys

### Cache Statistics
```json
{
    "hits": 1250,
    "misses": 180,
    "sets": 95,
    "deletes": 12,
    "hit_rate": 87.4,
    "memory_entries": 45,
    "file_entries": 120
}
```

## Database Schema

### Core Tables
- **emails**: Main email storage
- **email_attachments**: Attachment metadata
- **email_operations**: Queued IMAP operations
- **email_threads**: Email conversation threading
- **users**: User accounts (future multi-user support)
- **notifications**: System notifications

### Key Relationships
```sql
emails (1) -> (N) email_attachments
emails (1) -> (N) email_operations
emails (N) -> (1) email_threads
users (1) -> (N) emails
users (1) -> (N) notifications
```

## Performance Optimizations

### Database Optimizations
- Indexed columns for fast queries
- Pagination to limit result sets
- Efficient query patterns
- Connection pooling

### Caching Optimizations
- Multi-layer caching strategy
- Intelligent cache invalidation
- Background cache cleanup
- Cache statistics monitoring

### Frontend Optimizations
- Virtual scrolling for large lists
- Debounced search input
- Optimistic UI updates
- Real-time updates without polling

### IMAP Optimizations
- Connection pooling
- IDLE support for real-time detection
- Efficient email fetching
- Background monitoring

## Security Considerations

### Email Content Security
- HTML sanitization to prevent XSS
- Safe attachment handling
- Content type validation

### Data Security
- Local storage only (no cloud dependencies)
- Secure file permissions
- Input validation and sanitization

### API Security
- Request validation
- Error message sanitization
- Rate limiting considerations

## Scalability Considerations

### Horizontal Scaling
- Stateless service design
- Shared cache layer
- Load balancer friendly

### Vertical Scaling
- Efficient memory usage
- Database connection pooling
- Background task optimization

### Storage Scaling
- Local file system storage
- Configurable storage limits
- Automatic cleanup of old data

## Monitoring and Observability

### Health Checks
- Database connectivity
- Cache service health
- IMAP connection status
- Storage availability

### Metrics
- Email processing rates
- Cache hit rates
- Real-time client counts
- System resource usage

### Logging
- Structured logging
- Error tracking
- Performance monitoring
- Debug information

## Error Handling

### Error Categories
- **Network Errors**: IMAP connection issues
- **Data Errors**: Database constraint violations
- **Cache Errors**: Cache service failures
- **Parsing Errors**: Email content parsing issues

### Error Recovery
- Graceful degradation
- Automatic retries
- Fallback mechanisms
- User-friendly error messages

## Future Enhancements

### Planned Features
- Multi-user support
- Email composition
- Advanced filtering
- Mobile app support

### Scalability Improvements
- Redis cache backend option
- Message queue integration
- Microservices architecture
- Container orchestration

### Performance Improvements
- Database sharding
- CDN integration
- Advanced caching strategies
- Real-time WebSocket support

This architecture provides a solid foundation for a modern, scalable email client while maintaining simplicity and performance.