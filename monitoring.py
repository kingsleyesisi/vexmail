"""
Monitoring and error handling utilities
"""
import logging
import traceback
import functools
import time
from typing import Any, Callable, Dict, Optional
from datetime import datetime, timedelta
from flask import request, g
import json

logger = logging.getLogger(__name__)

class ErrorHandler:
    """Centralized error handling and logging"""
    
    @staticmethod
    def log_error(error: Exception, context: Dict[str, Any] = None):
        """Log error with context"""
        error_info = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.utcnow().isoformat(),
            'traceback': traceback.format_exc(),
            'context': context or {}
        }
        
        logger.error(f"Error occurred: {json.dumps(error_info, indent=2)}")
        return error_info
    
    @staticmethod
    def handle_imap_error(error: Exception, operation: str, email_id: str = None):
        """Handle IMAP-specific errors"""
        context = {
            'operation': operation,
            'email_id': email_id,
            'component': 'imap'
        }
        return ErrorHandler.log_error(error, context)
    
    @staticmethod
    def handle_storage_error(error: Exception, operation: str, object_key: str = None):
        """Handle storage-specific errors"""
        context = {
            'operation': operation,
            'object_key': object_key,
            'component': 'storage'
        }
        return ErrorHandler.log_error(error, context)
    
    @staticmethod
    def handle_database_error(error: Exception, operation: str, table: str = None):
        """Handle database-specific errors"""
        context = {
            'operation': operation,
            'table': table,
            'component': 'database'
        }
        return ErrorHandler.log_error(error, context)

def error_handler(func: Callable) -> Callable:
    """Decorator for error handling"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            ErrorHandler.log_error(e, {
                'function': func.__name__,
                'args': str(args)[:200],  # Truncate long arguments
                'kwargs': str(kwargs)[:200]
            })
            raise
    return wrapper

class PerformanceMonitor:
    """Performance monitoring and metrics collection"""
    
    def __init__(self):
        self.metrics = {}
        self.start_times = {}
    
    def start_timer(self, operation: str):
        """Start timing an operation"""
        self.start_times[operation] = time.time()
    
    def end_timer(self, operation: str) -> float:
        """End timing and record metric"""
        if operation not in self.start_times:
            return 0.0
        
        duration = time.time() - self.start_times[operation]
        
        if operation not in self.metrics:
            self.metrics[operation] = {
                'count': 0,
                'total_time': 0.0,
                'avg_time': 0.0,
                'min_time': float('inf'),
                'max_time': 0.0
            }
        
        metrics = self.metrics[operation]
        metrics['count'] += 1
        metrics['total_time'] += duration
        metrics['avg_time'] = metrics['total_time'] / metrics['count']
        metrics['min_time'] = min(metrics['min_time'], duration)
        metrics['max_time'] = max(metrics['max_time'], duration)
        
        del self.start_times[operation]
        
        # Log slow operations
        if duration > 5.0:  # Log operations taking more than 5 seconds
            logger.warning(f"Slow operation detected: {operation} took {duration:.2f}s")
        
        return duration
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all performance metrics"""
        return self.metrics.copy()
    
    def reset_metrics(self):
        """Reset all metrics"""
        self.metrics.clear()
        self.start_times.clear()

def performance_monitor(operation: str = None):
    """Decorator for performance monitoring"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation or func.__name__
            monitor.start_timer(op_name)
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = monitor.end_timer(op_name)
                logger.debug(f"{op_name} completed in {duration:.3f}s")
        return wrapper
    return decorator

class HealthChecker:
    """System health monitoring"""
    
    def __init__(self):
        self.checks = {}
        self.last_checks = {}
    
    def register_check(self, name: str, check_func: Callable, interval: int = 60):
        """Register a health check"""
        self.checks[name] = {
            'function': check_func,
            'interval': interval,
            'last_result': None,
            'last_check': None
        }
    
    def run_check(self, name: str) -> Dict[str, Any]:
        """Run a specific health check"""
        if name not in self.checks:
            return {'status': 'unknown', 'error': 'Check not found'}
        
        check = self.checks[name]
        now = datetime.utcnow()
        
        try:
            result = check['function']()
            check['last_result'] = result
            check['last_check'] = now
            return result
        except Exception as e:
            error_result = {
                'status': 'error',
                'error': str(e),
                'timestamp': now.isoformat()
            }
            check['last_result'] = error_result
            check['last_check'] = now
            return error_result
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        results = {}
        now = datetime.utcnow()
        
        for name, check in self.checks.items():
            # Check if enough time has passed since last check
            if (check['last_check'] is None or 
                (now - check['last_check']).total_seconds() >= check['interval']):
                results[name] = self.run_check(name)
            else:
                # Return cached result
                results[name] = check['last_result'] or {'status': 'unknown'}
        
        return results

class AlertManager:
    """Alert management system"""
    
    def __init__(self):
        self.alerts = []
        self.alert_thresholds = {
            'error_rate': 0.1,  # 10% error rate
            'response_time': 5.0,  # 5 seconds
            'memory_usage': 0.9,  # 90% memory usage
            'disk_usage': 0.9  # 90% disk usage
        }
    
    def check_alerts(self, metrics: Dict[str, Any]):
        """Check if any metrics exceed thresholds"""
        alerts = []
        
        # Check error rate
        if 'error_rate' in metrics and metrics['error_rate'] > self.alert_thresholds['error_rate']:
            alerts.append({
                'type': 'error_rate',
                'message': f"High error rate: {metrics['error_rate']:.2%}",
                'severity': 'high',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Check response time
        if 'avg_response_time' in metrics and metrics['avg_response_time'] > self.alert_thresholds['response_time']:
            alerts.append({
                'type': 'response_time',
                'message': f"Slow response time: {metrics['avg_response_time']:.2f}s",
                'severity': 'medium',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Store new alerts
        self.alerts.extend(alerts)
        
        # Keep only last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        
        return alerts
    
    def get_alerts(self, severity: str = None) -> list:
        """Get alerts, optionally filtered by severity"""
        if severity:
            return [alert for alert in self.alerts if alert['severity'] == severity]
        return self.alerts.copy()
    
    def clear_alerts(self):
        """Clear all alerts"""
        self.alerts.clear()

class RequestLogger:
    """HTTP request logging"""
    
    @staticmethod
    def log_request(response):
        """Log HTTP request details"""
        request_data = {
            'method': request.method,
            'url': request.url,
            'path': request.path,
            'remote_addr': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', ''),
            'status_code': response.status_code,
            'timestamp': datetime.utcnow().isoformat(),
            'response_time': getattr(g, 'request_start_time', None)
        }
        
        if hasattr(g, 'request_start_time'):
            request_data['response_time'] = time.time() - g.request_start_time
        
        # Log based on status code
        if response.status_code >= 500:
            logger.error(f"Server error: {json.dumps(request_data)}")
        elif response.status_code >= 400:
            logger.warning(f"Client error: {json.dumps(request_data)}")
        else:
            logger.info(f"Request: {json.dumps(request_data)}")
        
        return response

# Global instances
monitor = PerformanceMonitor()
health_checker = HealthChecker()
alert_manager = AlertManager()

# Health check functions
def check_database_health():
    """Check database connectivity"""
    try:
        from models import db, Email
        Email.query.count()
        return {'status': 'healthy', 'message': 'Database connection OK'}
    except Exception as e:
        return {'status': 'unhealthy', 'message': f'Database error: {str(e)}'}

def check_redis_health():
    """Check Redis connectivity"""
    try:
        from redis_client import redis_client
        redis_client.ping()
        return {'status': 'healthy', 'message': 'Redis connection OK'}
    except Exception as e:
        return {'status': 'unhealthy', 'message': f'Redis error: {str(e)}'}

def check_storage_health():
    """Check storage connectivity"""
    try:
        from storage_client import storage_client
        storage_client.get_storage_stats()
        return {'status': 'healthy', 'message': 'Storage connection OK'}
    except Exception as e:
        return {'status': 'unhealthy', 'message': f'Storage error: {str(e)}'}

def check_imap_health():
    """Check IMAP connectivity"""
    try:
        from imap_manager import imap_manager
        with imap_manager.connection_pool.get_connection() as conn:
            if conn.is_connected():
                return {'status': 'healthy', 'message': 'IMAP connection OK'}
            else:
                return {'status': 'unhealthy', 'message': 'IMAP connection failed'}
    except Exception as e:
        return {'status': 'unhealthy', 'message': f'IMAP error: {str(e)}'}

# Register health checks
health_checker.register_check('database', check_database_health, interval=30)
health_checker.register_check('redis', check_redis_health, interval=30)
health_checker.register_check('storage', check_storage_health, interval=60)
health_checker.register_check('imap', check_imap_health, interval=60)
