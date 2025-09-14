"""
Background task manager using threading and queue
"""
import threading
import queue
import logging
from typing import Callable, Any, Dict

logger = logging.getLogger(__name__)

class TaskManager:
    def __init__(self, num_workers: int = 4):
        self.task_queue = queue.Queue()
        self.num_workers = num_workers
        self.workers = []
        self._start_workers()

    def _start_workers(self):
        for i in range(self.num_workers):
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            worker.start()
            self.workers.append(worker)
        logger.info(f"Started {self.num_workers} worker threads")

    def _worker_loop(self):
        while True:
            try:
                task, args, kwargs = self.task_queue.get()
                logger.info(f"Executing task: {task.__name__}")
                task(*args, **kwargs)
                self.task_queue.task_done()
            except Exception as e:
                logger.error(f"Error executing task: {e}")

    def add_task(self, task: Callable, *args, **kwargs):
        """Add a task to the queue"""
        self.task_queue.put((task, args, kwargs))

# Global task manager instance
task_manager = TaskManager()

# --- Task Functions ---

def process_new_email_task(app, email_data: Dict[str, Any]):
    """Task to process a new email"""
    from email_sync_service import email_sync_service
    with app.app_context():
        email_sync_service.store_email_safely(email_data)

def sync_emails_task(app, limit: int = 50):
    """Task to sync emails from IMAP server"""
    from email_sync_service import email_sync_service
    from imap_manager import imap_manager

    with app.app_context():
        emails = imap_manager.fetch_emails(limit=limit)
        if not emails:
            return

        for email_data in emails:
            task_manager.add_task(process_new_email_task, app, email_data)

def process_pending_operations_task(app):
    """Task to process pending email operations"""
    from models import db, EmailOperation
    from imap_manager import imap_manager
    from datetime import datetime

    with app.app_context():
        pending_ops = EmailOperation.query.filter_by(status='pending').all()
        for op in pending_ops:
            if op.retry_count >= op.max_retries:
                op.status = 'failed'
                db.session.commit()
                continue

            success = imap_manager.execute_operation(op.operation_type, op.email_uid)
            if success:
                op.status = 'success'
            else:
                op.retry_count += 1
                op.last_retry = datetime.utcnow()
            db.session.commit()

def periodic_sync_task(app):
    """Periodic task to sync emails"""
    task_manager.add_task(sync_emails_task, app, limit=100)

def start_periodic_tasks(app):
    """Starts the periodic tasks"""
    import time

    def periodic_loop():
        while True:
            task_manager.add_task(periodic_sync_task, app)
            task_manager.add_task(process_pending_operations_task, app)
            time.sleep(600) # Run every 10 minutes

    thread = threading.Thread(target=periodic_loop, daemon=True)
    thread.start()
