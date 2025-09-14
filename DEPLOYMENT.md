# VexMail Deployment Guide

This guide covers deploying VexMail in various environments, from development to production.

## Table of Contents

1. [Development Setup](#development-setup)
2. [Docker Deployment](#docker-deployment)
3. [Production Deployment](#production-deployment)
4. [Environment Configuration](#environment-configuration)
5. [Monitoring and Logging](#monitoring-and-logging)
6. [Scaling](#scaling)
7. [Security](#security)
8. [Troubleshooting](#troubleshooting)

## Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 13+
- Redis 6+
- Node.js 16+ (for frontend development)

### Local Development

1. **Clone and setup**
   ```bash
   git clone <repository-url>
   cd vexmail
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Start services**
   ```bash
   # Start PostgreSQL and Redis
   docker-compose up -d postgres redis minio
   
   # Or install locally
   # PostgreSQL: brew install postgresql (macOS) or apt install postgresql (Ubuntu)
   # Redis: brew install redis (macOS) or apt install redis (Ubuntu)
   ```

3. **Configure environment**
   ```bash
   cp env.example .env
   # Edit .env with your settings
   ```

4. **Initialize database**
   ```bash
   python -c "from app import app, db; app.app_context().push(); db.create_all()"
   ```

5. **Run the application**
   ```bash
   # Terminal 1: Flask app
   python app.py
   
   # Terminal 2: Celery worker
   celery -A celery_config worker --loglevel=info
   
   # Terminal 3: Celery beat (scheduler)
   celery -A celery_config beat --loglevel=info
   ```

## Docker Deployment

### Single Container

```bash
# Build and run
docker build -t vexmail .
docker run -p 5000:5000 --env-file .env vexmail
```

### Multi-Container (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Scale workers
docker-compose up -d --scale worker=3
```

### Docker Compose Services

| Service | Port | Description |
|---------|------|-------------|
| web | 5000 | Flask application |
| postgres | 5432 | PostgreSQL database |
| redis | 6379 | Redis cache/broker |
| minio | 9000/9001 | Object storage |
| worker | - | Celery workers |
| beat | - | Celery scheduler |
| flower | 5555 | Celery monitoring |

## Production Deployment

### Using Docker Swarm

1. **Initialize swarm**
   ```bash
   docker swarm init
   ```

2. **Deploy stack**
   ```bash
   docker stack deploy -c docker-compose.yml vexmail
   ```

3. **Scale services**
   ```bash
   docker service scale vexmail_web=3 vexmail_worker=5
   ```

### Using Kubernetes

1. **Create namespace**
   ```yaml
   apiVersion: v1
   kind: Namespace
   metadata:
     name: vexmail
   ```

2. **Deploy services**
   ```bash
   kubectl apply -f k8s/
   ```

3. **Expose service**
   ```bash
   kubectl expose deployment vexmail-web --type=LoadBalancer --port=80 --target-port=5000
   ```

### Traditional Server Deployment

1. **Server requirements**
   - Ubuntu 20.04+ or CentOS 8+
   - 4GB RAM minimum (8GB recommended)
   - 50GB disk space
   - SSL certificate

2. **Install dependencies**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install postgresql redis-server nginx python3.11 python3.11-venv git
   
   # CentOS/RHEL
   sudo yum install postgresql-server redis python3.11 git
   ```

3. **Setup application**
   ```bash
   sudo useradd -m -s /bin/bash vexmail
   sudo su - vexmail
   git clone <repository-url> /home/vexmail/app
   cd /home/vexmail/app
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Configure services**
   ```bash
   # PostgreSQL
   sudo -u postgres createdb vexmail
   sudo -u postgres createuser vexmail
   
   # Redis
   sudo systemctl enable redis
   sudo systemctl start redis
   
   # Nginx
   sudo cp nginx.conf /etc/nginx/sites-available/vexmail
   sudo ln -s /etc/nginx/sites-available/vexmail /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   ```

5. **Systemd services**
   ```bash
   # /etc/systemd/system/vexmail.service
   [Unit]
   Description=VexMail Web Application
   After=network.target postgresql.service redis.service
   
   [Service]
   Type=simple
   User=vexmail
   WorkingDirectory=/home/vexmail/app
   Environment=PATH=/home/vexmail/app/venv/bin
   ExecStart=/home/vexmail/app/venv/bin/python app.py
   Restart=always
   
   [Install]
   WantedBy=multi-user.target
   ```

## Environment Configuration

### Production Environment Variables

```env
# Database
DATABASE_URL=postgresql://vexmail_user:secure_password@localhost:5432/vexmail
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=secure_redis_password

# Storage
STORAGE_PROVIDER=s3
STORAGE_ENDPOINT_URL=https://s3.amazonaws.com
STORAGE_ACCESS_KEY=your_access_key
STORAGE_SECRET_KEY=your_secret_key
STORAGE_BUCKET=vexmail-attachments
STORAGE_REGION=us-east-1

# IMAP
IMAP_SERVER=imap.gmail.com
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your_app_password
IMAP_MAILBOX=INBOX

# Security
SECRET_KEY=your-super-secret-key-change-in-production
FLASK_ENV=production
FLASK_DEBUG=False

# Celery
CELERY_WORKER_CONCURRENCY=4
CELERY_MAX_TASKS_PER_CHILD=1000
CELERY_TASK_TIME_LIMIT=300

# Monitoring
LOG_LEVEL=INFO
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

### SSL/TLS Configuration

#### Nginx SSL Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /api/events {
        proxy_pass http://localhost:5000;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
        proxy_buffering off;
        proxy_cache off;
    }
}
```

## Monitoring and Logging

### Application Monitoring

1. **Health Checks**
   ```bash
   # Basic health check
   curl http://localhost:5000/api/status
   
   # Detailed status
   curl http://localhost:5000/api/stats
   ```

2. **Log Aggregation**
   ```bash
   # Using ELK Stack
   docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
   
   # Using Fluentd
   fluentd -c fluent.conf
   ```

3. **Metrics Collection**
   ```bash
   # Prometheus metrics
   pip install prometheus-flask-exporter
   
   # Custom metrics
   from prometheus_client import Counter, Histogram
   ```

### Logging Configuration

```python
# logging.conf
[loggers]
keys=root,vexmail

[handlers]
keys=console,file

[formatters]
keys=standard,detailed

[logger_root]
level=INFO
handlers=console

[logger_vexmail]
level=INFO
handlers=console,file
qualname=vexmail
propagate=0

[handler_console]
class=StreamHandler
level=INFO
formatter=standard
args=(sys.stdout,)

[handler_file]
class=FileHandler
level=INFO
formatter=detailed
args=('/var/log/vexmail/app.log',)

[formatter_standard]
format=%(asctime)s [%(levelname)s] %(name)s: %(message)s

[formatter_detailed]
format=%(asctime)s [%(levelname)s] %(name)s: %(message)s [%(filename)s:%(lineno)d]
```

## Scaling

### Horizontal Scaling

1. **Load Balancer Configuration**
   ```nginx
   upstream vexmail_backend {
       least_conn;
       server 127.0.0.1:5000 max_fails=3 fail_timeout=30s;
       server 127.0.0.1:5001 max_fails=3 fail_timeout=30s;
       server 127.0.0.1:5002 max_fails=3 fail_timeout=30s;
   }
   ```

2. **Database Scaling**
   ```bash
   # Read replicas
   DATABASE_READ_URL=postgresql://readonly_user:pass@read-replica:5432/vexmail
   DATABASE_WRITE_URL=postgresql://write_user:pass@master:5432/vexmail
   ```

3. **Redis Clustering**
   ```bash
   # Redis Cluster
   redis-cli --cluster create 127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002
   ```

### Performance Optimization

1. **Database Optimization**
   ```sql
   -- Indexes
   CREATE INDEX idx_emails_date ON emails(date DESC);
   CREATE INDEX idx_emails_sender ON emails(sender_email);
   CREATE INDEX idx_emails_read ON emails(is_read);
   
   -- Connection pooling
   ALTER SYSTEM SET max_connections = 200;
   ALTER SYSTEM SET shared_buffers = '256MB';
   ```

2. **Redis Optimization**
   ```bash
   # Redis configuration
   maxmemory 1gb
   maxmemory-policy allkeys-lru
   save 900 1
   save 300 10
   save 60 10000
   ```

3. **Application Optimization**
   ```python
   # Gunicorn configuration
   workers = 4
   worker_class = "eventlet"
   worker_connections = 1000
   max_requests = 1000
   max_requests_jitter = 100
   ```

## Security

### Security Checklist

- [ ] Use HTTPS in production
- [ ] Set strong SECRET_KEY
- [ ] Enable database SSL
- [ ] Use Redis AUTH
- [ ] Configure firewall rules
- [ ] Enable fail2ban
- [ ] Set up log monitoring
- [ ] Use app passwords for IMAP
- [ ] Regular security updates
- [ ] Backup encryption

### Firewall Configuration

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# iptables
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
iptables -A INPUT -j DROP
```

### Backup Strategy

```bash
#!/bin/bash
# backup.sh

# Database backup
pg_dump -h localhost -U vexmail_user vexmail | gzip > /backups/vexmail_$(date +%Y%m%d_%H%M%S).sql.gz

# Redis backup
redis-cli --rdb /backups/redis_$(date +%Y%m%d_%H%M%S).rdb

# Application backup
tar -czf /backups/app_$(date +%Y%m%d_%H%M%S).tar.gz /home/vexmail/app

# Clean old backups (keep 30 days)
find /backups -name "*.gz" -mtime +30 -delete
find /backups -name "*.rdb" -mtime +30 -delete
find /backups -name "*.tar.gz" -mtime +30 -delete
```

## Troubleshooting

### Common Issues

1. **High Memory Usage**
   ```bash
   # Check memory usage
   free -h
   ps aux --sort=-%mem | head
   
   # Reduce worker concurrency
   CELERY_WORKER_CONCURRENCY=2
   ```

2. **Database Connection Issues**
   ```bash
   # Check connections
   sudo -u postgres psql -c "SELECT * FROM pg_stat_activity;"
   
   # Increase pool size
   DATABASE_POOL_SIZE=50
   ```

3. **Redis Memory Issues**
   ```bash
   # Check Redis memory
   redis-cli info memory
   
   # Clear cache
   redis-cli FLUSHDB
   ```

4. **IMAP Connection Problems**
   ```bash
   # Test IMAP connection
   telnet imap.gmail.com 993
   
   # Check credentials
   python -c "from imap_manager import imap_manager; print(imap_manager.fetch_emails(limit=1))"
   ```

### Performance Monitoring

```bash
# System resources
htop
iotop
netstat -tulpn

# Application metrics
curl http://localhost:5000/api/stats

# Database performance
sudo -u postgres psql -c "SELECT * FROM pg_stat_user_tables;"

# Redis performance
redis-cli --latency-history -i 1
```

### Log Analysis

```bash
# Application logs
tail -f /var/log/vexmail/app.log

# System logs
journalctl -u vexmail -f

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

This deployment guide provides comprehensive instructions for deploying VexMail in various environments. Choose the approach that best fits your infrastructure and requirements.
