import os
import logging
from typing import Optional, Tuple
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
import uuid
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

class CloudStorageService:
    def __init__(self):
        self.project_id = Config.GOOGLE_CLOUD_PROJECT_ID
        self.bucket_name = Config.GOOGLE_CLOUD_BUCKET_NAME
        
        try:
            # Initialize the Google Cloud Storage client
            self.client = storage.Client(project=self.project_id)
            self.bucket = self.client.bucket(self.bucket_name)
            
            # Ensure bucket exists
            self._ensure_bucket_exists()
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud Storage: {str(e)}")
            self.client = None
            self.bucket = None
    
    def _ensure_bucket_exists(self):
        """Ensure the bucket exists, create if it doesn't"""
        try:
            if not self.bucket.exists():
                logger.info(f"Creating bucket: {self.bucket_name}")
                self.bucket = self.client.create_bucket(self.bucket_name)
                
                # Make bucket publicly readable for media files
                policy = self.bucket.get_iam_policy()
                policy.bindings.append({
                    "role": "roles/storage.objectViewer",
                    "members": {"allUsers"}
                })
                self.bucket.set_iam_policy(policy)
                
            logger.info(f"Bucket {self.bucket_name} is ready")
            
        except GoogleCloudError as e:
            logger.error(f"Failed to ensure bucket exists: {str(e)}")
            raise
    
    def upload_file(self, file_data: bytes, filename: str, content_type: str = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Upload a file to Google Cloud Storage
        Returns: (blob_name, public_url) or (None, None) if failed
        """
        if not self.client or not self.bucket:
            logger.error("Google Cloud Storage not properly initialized")
            return None, None
        
        try:
            # Generate unique filename with timestamp and UUID
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            file_extension = os.path.splitext(filename)[1]
            
            blob_name = f"whatsapp_media/{timestamp}_{unique_id}_{filename}"
            
            # Create blob and upload
            blob = self.bucket.blob(blob_name)
            
            # Set content type if provided
            if content_type:
                blob.content_type = content_type
            
            # Upload the file
            blob.upload_from_string(file_data)
            
            # Make the blob publicly readable
            blob.make_public()
            
            # Get public URL
            public_url = blob.public_url
            
            logger.info(f"File uploaded successfully: {blob_name}")
            logger.info(f"Public URL: {public_url}")
            
            return blob_name, public_url
            
        except GoogleCloudError as e:
            logger.error(f"Failed to upload file to Cloud Storage: {str(e)}")
            return None, None
        except Exception as e:
            logger.error(f"Unexpected error uploading file: {str(e)}")
            return None, None
    
    def download_file(self, blob_name: str) -> Optional[bytes]:
        """Download a file from Google Cloud Storage"""
        if not self.client or not self.bucket:
            logger.error("Google Cloud Storage not properly initialized")
            return None
        
        try:
            blob = self.bucket.blob(blob_name)
            
            if not blob.exists():
                logger.error(f"File not found: {blob_name}")
                return None
            
            file_data = blob.download_as_bytes()
            logger.info(f"File downloaded successfully: {blob_name}")
            
            return file_data
            
        except GoogleCloudError as e:
            logger.error(f"Failed to download file from Cloud Storage: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading file: {str(e)}")
            return None
    
    def delete_file(self, blob_name: str) -> bool:
        """Delete a file from Google Cloud Storage"""
        if not self.client or not self.bucket:
            logger.error("Google Cloud Storage not properly initialized")
            return False
        
        try:
            blob = self.bucket.blob(blob_name)
            
            if blob.exists():
                blob.delete()
                logger.info(f"File deleted successfully: {blob_name}")
                return True
            else:
                logger.warning(f"File not found for deletion: {blob_name}")
                return True  # Consider it successful if file doesn't exist
            
        except GoogleCloudError as e:
            logger.error(f"Failed to delete file from Cloud Storage: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting file: {str(e)}")
            return False
    
    def get_file_info(self, blob_name: str) -> Optional[dict]:
        """Get information about a file in Cloud Storage"""
        if not self.client or not self.bucket:
            logger.error("Google Cloud Storage not properly initialized")
            return None
        
        try:
            blob = self.bucket.blob(blob_name)
            
            if not blob.exists():
                logger.error(f"File not found: {blob_name}")
                return None
            
            blob.reload()  # Refresh blob metadata
            
            return {
                'name': blob.name,
                'size': blob.size,
                'content_type': blob.content_type,
                'created': blob.time_created,
                'updated': blob.updated,
                'public_url': blob.public_url,
                'md5_hash': blob.md5_hash,
                'etag': blob.etag
            }
            
        except GoogleCloudError as e:
            logger.error(f"Failed to get file info from Cloud Storage: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting file info: {str(e)}")
            return None
    
    def list_files(self, prefix: str = "whatsapp_media/", max_results: int = 100) -> list:
        """List files in the bucket with optional prefix filter"""
        if not self.client or not self.bucket:
            logger.error("Google Cloud Storage not properly initialized")
            return []
        
        try:
            blobs = self.bucket.list_blobs(prefix=prefix, max_results=max_results)
            
            file_list = []
            for blob in blobs:
                file_list.append({
                    'name': blob.name,
                    'size': blob.size,
                    'content_type': blob.content_type,
                    'created': blob.time_created,
                    'public_url': blob.public_url
                })
            
            logger.info(f"Listed {len(file_list)} files with prefix: {prefix}")
            return file_list
            
        except GoogleCloudError as e:
            logger.error(f"Failed to list files from Cloud Storage: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing files: {str(e)}")
            return []
    
    def get_signed_url(self, blob_name: str, expiration_hours: int = 24) -> Optional[str]:
        """Generate a signed URL for private file access"""
        if not self.client or not self.bucket:
            logger.error("Google Cloud Storage not properly initialized")
            return None
        
        try:
            from datetime import timedelta
            
            blob = self.bucket.blob(blob_name)
            
            if not blob.exists():
                logger.error(f"File not found: {blob_name}")
                return None
            
            # Generate signed URL
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(hours=expiration_hours),
                method="GET"
            )
            
            logger.info(f"Generated signed URL for: {blob_name}")
            return signed_url
            
        except GoogleCloudError as e:
            logger.error(f"Failed to generate signed URL: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating signed URL: {str(e)}")
            return None
