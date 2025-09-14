"""
Local file system client for attachment storage
"""
import os
import shutil
from typing import Optional, Dict, Any, BinaryIO, Union
from decouple import config
import logging
import mimetypes
import hashlib
import uuid
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class StorageClient:
    """Local file system storage client for attachments"""
    
    def __init__(self):
        self.storage_path = config('STORAGE_PATH', default='./attachments')
        # Parse max file size more safely
        try:
            self.max_file_size = config('STORAGE_MAX_SIZE', default='104857600', cast=int)  # 100MB
        except ValueError:
            # If parsing fails, use default value
            self.max_file_size = 104857600  # 100MB
        
        # Ensure storage directory exists
        self.storage_dir = Path(self.storage_path)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories for organization
        (self.storage_dir / 'emails').mkdir(exist_ok=True)
        (self.storage_dir / 'temp').mkdir(exist_ok=True)
        
        logger.info(f"Local storage client initialized at: {self.storage_dir.absolute()}")
    
    def _generate_file_path(self, email_id: str, filename: str, attachment_id: str = None) -> Path:
        """Generate file path for storage"""
        # Sanitize filename
        safe_filename = self._sanitize_filename(filename)
        
        # Generate path: emails/{email_id}/attachments/{attachment_id}/{filename}
        if attachment_id:
            file_path = self.storage_dir / 'emails' / email_id / 'attachments' / attachment_id / safe_filename
        else:
            # Fallback if no attachment_id
            file_path = self.storage_dir / 'emails' / email_id / 'attachments' / safe_filename
        
        # Ensure parent directories exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        return file_path
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for storage"""
        import re
        # Remove or replace unsafe characters
        safe_filename = re.sub(r'[^\w\-_\.]', '_', filename)
        # Limit length
        if len(safe_filename) > 255:
            name, ext = safe_filename.rsplit('.', 1) if '.' in safe_filename else (safe_filename, '')
            safe_filename = name[:250] + '.' + ext if ext else name[:255]
        return safe_filename
    
    def upload_attachment(self, email_id: str, filename: str, content: Union[bytes, BinaryIO], 
                         content_type: str = None, attachment_id: str = None) -> Dict[str, Any]:
        """Upload attachment to local storage"""
        try:
            # Generate file path
            file_path = self._generate_file_path(email_id, filename, attachment_id)
            
            # Determine content type
            if not content_type:
                content_type, _ = mimetypes.guess_type(filename)
                if not content_type:
                    content_type = 'application/octet-stream'
            
            # Handle content as bytes or file-like object
            if isinstance(content, bytes):
                file_data = content
            else:
                # For file-like objects, read the content
                content.seek(0)
                file_data = content.read()
            
            # Check file size
            if len(file_data) > self.max_file_size:
                raise ValueError(f"File size {len(file_data)} exceeds maximum allowed size {self.max_file_size}")
            
            # Calculate checksum
            checksum = hashlib.sha256(file_data).hexdigest()
            
            # Write file to disk
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            # Store metadata
            metadata_path = file_path.with_suffix('.meta')
            metadata = {
                'email_id': email_id,
                'filename': filename,
                'content_type': content_type,
                'checksum': checksum,
                'size': len(file_data),
                'uploaded_at': datetime.utcnow().isoformat(),
                'attachment_id': attachment_id
            }
            
            with open(metadata_path, 'w') as f:
                import json
                json.dump(metadata, f, indent=2)
            
            # Generate download URL (relative path)
            download_path = f"/api/attachment/{attachment_id or 'temp'}/download"
            
            result = {
                'object_key': str(file_path.relative_to(self.storage_dir)),
                'file_path': str(file_path),
                'filename': filename,
                'content_type': content_type,
                'size': len(file_data),
                'checksum': checksum,
                'download_url': download_path,
                'uploaded_at': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Successfully uploaded attachment: {file_path}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to upload attachment: {e}")
            raise
    
    def download_attachment(self, file_path: str) -> bytes:
        """Download attachment from local storage"""
        try:
            full_path = self.storage_dir / file_path
            if not full_path.exists():
                raise FileNotFoundError(f"Attachment not found: {file_path}")
            
            with open(full_path, 'rb') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Failed to download attachment: {e}")
            raise
    
    def delete_attachment(self, file_path: str) -> bool:
        """Delete attachment from local storage"""
        try:
            full_path = self.storage_dir / file_path
            if full_path.exists():
                full_path.unlink()
                logger.info(f"Successfully deleted attachment: {full_path}")
            
            # Also delete metadata file if it exists
            metadata_path = full_path.with_suffix('.meta')
            if metadata_path.exists():
                metadata_path.unlink()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete attachment: {e}")
            return False
    
    def generate_presigned_url(self, file_path: str, expiration: int = 3600, 
                              method: str = 'get_object') -> str:
        """Generate download URL for attachment (local storage doesn't need presigned URLs)"""
        try:
            # For local storage, we just return the download endpoint
            # Extract attachment ID from file path or use a placeholder
            attachment_id = file_path.split('/')[-2] if '/' in file_path else 'temp'
            return f"/api/attachment/{attachment_id}/download"
            
        except Exception as e:
            logger.error(f"Failed to generate download URL: {e}")
            raise
    
    def get_attachment_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get attachment metadata"""
        try:
            full_path = self.storage_dir / file_path
            if not full_path.exists():
                return None
            
            # Try to read metadata file first
            metadata_path = full_path.with_suffix('.meta')
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    import json
                    metadata = json.load(f)
                    metadata['last_modified'] = datetime.fromtimestamp(full_path.stat().st_mtime)
                    return metadata
            
            # Fallback to basic file info
            stat = full_path.stat()
            return {
                'size': stat.st_size,
                'content_type': mimetypes.guess_type(str(full_path))[0] or 'application/octet-stream',
                'last_modified': datetime.fromtimestamp(stat.st_mtime),
                'filename': full_path.name
            }
            
        except Exception as e:
            logger.error(f"Failed to get attachment info: {e}")
            return None
    
    def list_attachments(self, email_id: str, prefix: str = None) -> list:
        """List attachments for an email"""
        try:
            email_dir = self.storage_dir / 'emails' / email_id / 'attachments'
            if not email_dir.exists():
                return []
            
            attachments = []
            for file_path in email_dir.rglob('*'):
                if file_path.is_file() and not file_path.name.endswith('.meta'):
                    attachments.append({
                        'file_path': str(file_path.relative_to(self.storage_dir)),
                        'size': file_path.stat().st_size,
                        'last_modified': datetime.fromtimestamp(file_path.stat().st_mtime),
                        'filename': file_path.name
                    })
            
            return attachments
            
        except Exception as e:
            logger.error(f"Failed to list attachments: {e}")
            return []
    
    def cleanup_old_attachments(self, days_old: int = 30) -> int:
        """Clean up old attachments"""
        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            deleted_count = 0
            
            # Walk through all files in emails directory
            emails_dir = self.storage_dir / 'emails'
            if not emails_dir.exists():
                return 0
            
            for file_path in emails_dir.rglob('*'):
                if (file_path.is_file() and 
                    not file_path.name.endswith('.meta') and
                    datetime.fromtimestamp(file_path.stat().st_mtime) < cutoff_date):
                    try:
                        file_path.unlink()
                        # Also delete metadata file
                        metadata_path = file_path.with_suffix('.meta')
                        if metadata_path.exists():
                            metadata_path.unlink()
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Failed to delete old attachment {file_path}: {e}")
            
            logger.info(f"Cleaned up {deleted_count} old attachments")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old attachments: {e}")
            return 0
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            total_size = 0
            total_files = 0
            
            # Count files and size in emails directory
            emails_dir = self.storage_dir / 'emails'
            if emails_dir.exists():
                for file_path in emails_dir.rglob('*'):
                    if file_path.is_file() and not file_path.name.endswith('.meta'):
                        total_size += file_path.stat().st_size
                        total_files += 1
            
            return {
                'total_objects': total_files,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'total_size_gb': round(total_size / (1024 * 1024 * 1024), 2),
                'storage_path': str(self.storage_dir.absolute()),
                'provider': 'local'
            }
            
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {}

# Global storage client instance
storage_client = StorageClient()