"""
Advanced caching service with intelligent cache management
"""
import json
import logging
import hashlib
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path
import pickle
import threading
import time

logger = logging.getLogger(__name__)

class CacheService:
    """Advanced caching service with file-based storage and intelligent management"""
    
    def __init__(self, cache_dir: str = "cache", default_ttl: int = 3600):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.default_ttl = default_ttl
        self.memory_cache = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
        self.lock = threading.RLock()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        logger.info(f"Cache service initialized with directory: {self.cache_dir}")
    
    def _get_cache_key_hash(self, key: str) -> str:
        """Generate a safe filename from cache key"""
        return hashlib.md5(key.encode()).hexdigest()
    
    def _get_cache_file_path(self, key: str) -> Path:
        """Get the file path for a cache key"""
        key_hash = self._get_cache_key_hash(key)
        return self.cache_dir / f"{key_hash}.cache"
    
    def _get_metadata_file_path(self, key: str) -> Path:
        """Get the metadata file path for a cache key"""
        key_hash = self._get_cache_key_hash(key)
        return self.cache_dir / f"{key_hash}.meta"
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache with TTL"""
        try:
            with self.lock:
                ttl = ttl or self.default_ttl
                expires_at = datetime.utcnow() + timedelta(seconds=ttl)
                
                # Store in memory cache for fast access
                self.memory_cache[key] = {
                    'value': value,
                    'expires_at': expires_at,
                    'created_at': datetime.utcnow()
                }
                
                # Store in file cache for persistence
                cache_file = self._get_cache_file_path(key)
                meta_file = self._get_metadata_file_path(key)
                
                # Save data
                with open(cache_file, 'wb') as f:
                    pickle.dump(value, f)
                
                # Save metadata
                metadata = {
                    'key': key,
                    'expires_at': expires_at.isoformat(),
                    'created_at': datetime.utcnow().isoformat(),
                    'ttl': ttl
                }
                with open(meta_file, 'w') as f:
                    json.dump(metadata, f)
                
                self.cache_stats['sets'] += 1
                return True
                
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from cache"""
        try:
            with self.lock:
                # Check memory cache first
                if key in self.memory_cache:
                    cache_entry = self.memory_cache[key]
                    if datetime.utcnow() < cache_entry['expires_at']:
                        self.cache_stats['hits'] += 1
                        return cache_entry['value']
                    else:
                        # Expired, remove from memory
                        del self.memory_cache[key]
                
                # Check file cache
                cache_file = self._get_cache_file_path(key)
                meta_file = self._get_metadata_file_path(key)
                
                if cache_file.exists() and meta_file.exists():
                    # Check if expired
                    with open(meta_file, 'r') as f:
                        metadata = json.load(f)
                    
                    expires_at = datetime.fromisoformat(metadata['expires_at'])
                    if datetime.utcnow() < expires_at:
                        # Load from file and put back in memory
                        with open(cache_file, 'rb') as f:
                            value = pickle.load(f)
                        
                        self.memory_cache[key] = {
                            'value': value,
                            'expires_at': expires_at,
                            'created_at': datetime.fromisoformat(metadata['created_at'])
                        }
                        
                        self.cache_stats['hits'] += 1
                        return value
                    else:
                        # Expired, clean up
                        self._delete_cache_files(key)
                
                self.cache_stats['misses'] += 1
                return default
                
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            self.cache_stats['misses'] += 1
            return default
    
    def delete(self, key: str) -> bool:
        """Delete a cache entry"""
        try:
            with self.lock:
                # Remove from memory
                if key in self.memory_cache:
                    del self.memory_cache[key]
                
                # Remove files
                self._delete_cache_files(key)
                
                self.cache_stats['deletes'] += 1
                return True
                
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    def _delete_cache_files(self, key: str):
        """Delete cache files for a key"""
        try:
            cache_file = self._get_cache_file_path(key)
            meta_file = self._get_metadata_file_path(key)
            
            if cache_file.exists():
                cache_file.unlink()
            if meta_file.exists():
                meta_file.unlink()
                
        except Exception as e:
            logger.error(f"Error deleting cache files for {key}: {e}")
    
    def clear(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries, optionally matching a pattern"""
        try:
            with self.lock:
                cleared_count = 0
                
                if pattern is None:
                    # Clear all
                    self.memory_cache.clear()
                    
                    # Clear all files
                    for cache_file in self.cache_dir.glob("*.cache"):
                        cache_file.unlink()
                        cleared_count += 1
                    
                    for meta_file in self.cache_dir.glob("*.meta"):
                        meta_file.unlink()
                else:
                    # Clear matching pattern
                    keys_to_delete = []
                    for key in self.memory_cache.keys():
                        if pattern in key:
                            keys_to_delete.append(key)
                    
                    for key in keys_to_delete:
                        self.delete(key)
                        cleared_count += 1
                
                return cleared_count
                
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in cache"""
        return self.get(key) is not None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
            hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'hits': self.cache_stats['hits'],
                'misses': self.cache_stats['misses'],
                'sets': self.cache_stats['sets'],
                'deletes': self.cache_stats['deletes'],
                'hit_rate': round(hit_rate, 2),
                'memory_entries': len(self.memory_cache),
                'file_entries': len(list(self.cache_dir.glob("*.cache")))
            }
    
    def _cleanup_loop(self):
        """Background cleanup of expired entries"""
        while True:
            try:
                time.sleep(300)  # Run every 5 minutes
                self._cleanup_expired()
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
    
    def _cleanup_expired(self):
        """Clean up expired cache entries"""
        try:
            with self.lock:
                current_time = datetime.utcnow()
                
                # Clean memory cache
                expired_keys = []
                for key, entry in self.memory_cache.items():
                    if current_time >= entry['expires_at']:
                        expired_keys.append(key)
                
                for key in expired_keys:
                    del self.memory_cache[key]
                
                # Clean file cache
                for meta_file in self.cache_dir.glob("*.meta"):
                    try:
                        with open(meta_file, 'r') as f:
                            metadata = json.load(f)
                        
                        expires_at = datetime.fromisoformat(metadata['expires_at'])
                        if current_time >= expires_at:
                            # Remove both meta and cache files
                            key = metadata['key']
                            self._delete_cache_files(key)
                            
                    except Exception as e:
                        logger.error(f"Error cleaning up cache file {meta_file}: {e}")
                        # Remove corrupted files
                        try:
                            meta_file.unlink()
                            cache_file = meta_file.with_suffix('.cache')
                            if cache_file.exists():
                                cache_file.unlink()
                        except:
                            pass
                
                if expired_keys:
                    logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
                    
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")

# Global cache service instance
cache_service = CacheService()