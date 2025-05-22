import requests
import logging
from typing import Dict, Any, Optional
from config import Config

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.api_url = Config.WHATSAPP_API_URL
        self.api_token = Config.WHATSAPP_API_TOKEN
        self.phone_number_id = Config.WHATSAPP_PHONE_NUMBER_ID
        
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }
    
    def send_text_message(self, to: str, text: str) -> Optional[str]:
        """Send a text message via WhatsApp API"""
        try:
            url = f"{self.api_url}/{self.phone_number_id}/messages"
            
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {
                    "body": text
                }
            }
            
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            message_id = data.get('messages', [{}])[0].get('id')
            
            logger.info(f"Text message sent successfully to {to}, message_id: {message_id}")
            return message_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send text message to {to}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending text message: {str(e)}")
            return None
    
    def send_media_message(self, to: str, media_type: str, media_url: str, caption: str = None) -> Optional[str]:
        """Send a media message via WhatsApp API"""
        try:
            url = f"{self.api_url}/{self.phone_number_id}/messages"
            
            media_payload = {
                "link": media_url
            }
            
            if caption:
                media_payload["caption"] = caption
            
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": media_type,
                media_type: media_payload
            }
            
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            message_id = data.get('messages', [{}])[0].get('id')
            
            logger.info(f"Media message sent successfully to {to}, message_id: {message_id}")
            return message_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send media message to {to}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending media message: {str(e)}")
            return None
    
    def download_media(self, media_id: str) -> Optional[bytes]:
        """Download media file from WhatsApp"""
        try:
            # First, get the media URL
            url = f"{self.api_url}/{media_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            media_info = response.json()
            media_url = media_info.get('url')
            
            if not media_url:
                logger.error(f"No URL found for media_id: {media_id}")
                return None
            
            # Download the actual media file
            media_response = requests.get(media_url, headers=self.headers)
            media_response.raise_for_status()
            
            logger.info(f"Media downloaded successfully, size: {len(media_response.content)} bytes")
            return media_response.content
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download media {media_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading media: {str(e)}")
            return None
    
    def get_media_info(self, media_id: str) -> Optional[Dict[str, Any]]:
        """Get media information from WhatsApp"""
        try:
            url = f"{self.api_url}/{media_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get media info for {media_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting media info: {str(e)}")
            return None
    
    def mark_message_as_read(self, message_id: str) -> bool:
        """Mark a message as read"""
        try:
            url = f"{self.api_url}/{self.phone_number_id}/messages"
            
            payload = {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id
            }
            
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            
            logger.info(f"Message {message_id} marked as read")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to mark message as read {message_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error marking message as read: {str(e)}")
            return False
