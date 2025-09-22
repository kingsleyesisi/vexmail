"""
Real-time service for instant email updates using WebSocket-like functionality
"""
import json
import logging
import threading
import time
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from queue import Queue, Empty
import uuid

logger = logging.getLogger(__name__)

class RealtimeService:
    """Real-time service for instant email notifications"""
    
    def __init__(self):
        self.clients = {}  # client_id -> client_info
        self.event_queue = Queue()
        self.running = True
        self.lock = threading.RLock()
        
        # Start event processing thread
        self.processor_thread = threading.Thread(target=self._process_events, daemon=True)
        self.processor_thread.start()
        
        logger.info("Real-time service initialized")
    
    def register_client(self, client_id: str = None) -> str:
        """Register a new client for real-time updates"""
        if not client_id:
            client_id = str(uuid.uuid4())
        
        with self.lock:
            self.clients[client_id] = {
                'id': client_id,
                'connected_at': datetime.utcnow(),
                'last_ping': datetime.utcnow(),
                'events': Queue(),
                'subscriptions': set(['email_updates'])  # Default subscription
            }
        
        logger.info(f"Client {client_id} registered for real-time updates")
        return client_id
    
    def unregister_client(self, client_id: str):
        """Unregister a client"""
        with self.lock:
            if client_id in self.clients:
                del self.clients[client_id]
                logger.info(f"Client {client_id} unregistered")
    
    def ping_client(self, client_id: str):
        """Update client's last ping time"""
        with self.lock:
            if client_id in self.clients:
                self.clients[client_id]['last_ping'] = datetime.utcnow()
    
    def subscribe_client(self, client_id: str, event_types: List[str]):
        """Subscribe client to specific event types"""
        with self.lock:
            if client_id in self.clients:
                self.clients[client_id]['subscriptions'].update(event_types)
    
    def unsubscribe_client(self, client_id: str, event_types: List[str]):
        """Unsubscribe client from specific event types"""
        with self.lock:
            if client_id in self.clients:
                self.clients[client_id]['subscriptions'].difference_update(event_types)
    
    def broadcast_event(self, event_type: str, data: Dict[str, Any], target_clients: List[str] = None):
        """Broadcast an event to all or specific clients"""
        event = {
            'type': event_type,
            'data': data,
            'timestamp': datetime.utcnow().isoformat(),
            'id': str(uuid.uuid4())
        }
        
        with self.lock:
            target_client_ids = target_clients or list(self.clients.keys())
            
            for client_id in target_client_ids:
                if client_id in self.clients:
                    client = self.clients[client_id]
                    
                    # Check if client is subscribed to this event type
                    if event_type in client['subscriptions'] or 'all' in client['subscriptions']:
                        try:
                            client['events'].put(event, block=False)
                        except:
                            # Queue is full, skip this client
                            logger.warning(f"Event queue full for client {client_id}")
        
        logger.debug(f"Broadcasted {event_type} event to {len(target_client_ids)} clients")
    
    def get_client_events(self, client_id: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Get pending events for a client (long-polling)"""
        with self.lock:
            if client_id not in self.clients:
                return None
            
            client = self.clients[client_id]
        
        try:
            # Update ping time
            self.ping_client(client_id)
            
            # Get event with timeout
            event = client['events'].get(timeout=timeout)
            return event
            
        except Empty:
            # No events within timeout, return heartbeat
            return {
                'type': 'heartbeat',
                'data': {'timestamp': datetime.utcnow().isoformat()},
                'timestamp': datetime.utcnow().isoformat(),
                'id': str(uuid.uuid4())
            }
        except Exception as e:
            logger.error(f"Error getting events for client {client_id}: {e}")
            return None
    
    def _process_events(self):
        """Process events from the main event queue"""
        while self.running:
            try:
                # Clean up disconnected clients
                self._cleanup_clients()
                
                # Process any queued events
                try:
                    event = self.event_queue.get(timeout=1)
                    self._handle_event(event)
                except Empty:
                    continue
                    
            except Exception as e:
                logger.error(f"Error processing events: {e}")
                time.sleep(1)
    
    def _handle_event(self, event: Dict[str, Any]):
        """Handle a specific event"""
        event_type = event.get('type')
        data = event.get('data', {})
        
        # Broadcast to all subscribed clients
        self.broadcast_event(event_type, data)
    
    def _cleanup_clients(self):
        """Clean up disconnected clients"""
        current_time = datetime.utcnow()
        timeout_threshold = current_time - timedelta(minutes=5)  # 5 minute timeout
        
        with self.lock:
            disconnected_clients = []
            
            for client_id, client in self.clients.items():
                if client['last_ping'] < timeout_threshold:
                    disconnected_clients.append(client_id)
            
            for client_id in disconnected_clients:
                del self.clients[client_id]
                logger.info(f"Cleaned up disconnected client {client_id}")
    
    def emit_email_received(self, email_data: Dict[str, Any]):
        """Emit new email received event"""
        self.broadcast_event('email_received', {
            'email_id': email_data.get('id'),
            'subject': email_data.get('subject'),
            'sender': email_data.get('sender_name'),
            'sender_email': email_data.get('sender_email'),
            'preview': email_data.get('body', '')[:100] + '...' if email_data.get('body') else '',
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def emit_email_updated(self, email_id: str, updates: Dict[str, Any]):
        """Emit email updated event"""
        self.broadcast_event('email_updated', {
            'email_id': email_id,
            'updates': updates,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def emit_email_deleted(self, email_id: str):
        """Emit email deleted event"""
        self.broadcast_event('email_deleted', {
            'email_id': email_id,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def emit_sync_status(self, status: str, message: str, progress: int = None):
        """Emit sync status update"""
        self.broadcast_event('sync_status', {
            'status': status,
            'message': message,
            'progress': progress,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def get_stats(self) -> Dict[str, Any]:
        """Get real-time service statistics"""
        with self.lock:
            return {
                'connected_clients': len(self.clients),
                'total_events_queued': sum(client['events'].qsize() for client in self.clients.values()),
                'clients': [
                    {
                        'id': client['id'],
                        'connected_at': client['connected_at'].isoformat(),
                        'last_ping': client['last_ping'].isoformat(),
                        'subscriptions': list(client['subscriptions']),
                        'pending_events': client['events'].qsize()
                    }
                    for client in self.clients.values()
                ]
            }
    
    def shutdown(self):
        """Shutdown the real-time service"""
        self.running = False
        logger.info("Real-time service shutting down")

# Global real-time service instance
realtime_service = RealtimeService()