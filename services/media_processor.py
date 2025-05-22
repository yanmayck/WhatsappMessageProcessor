import os
import io
import logging
from PIL import Image
from pydub import AudioSegment
from typing import Optional, Tuple, Dict, Any
import mimetypes

logger = logging.getLogger(__name__)

class MediaProcessor:
    def __init__(self):
        self.supported_image_formats = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        self.supported_audio_formats = ['.mp3', '.wav', '.ogg', '.m4a', '.opus', '.aac']
        self.supported_video_formats = ['.mp4', '.avi', '.mov', '.webm', '.mkv']
        
    def process_image(self, image_data: bytes, filename: str) -> Tuple[Optional[bytes], Optional[Dict[str, Any]]]:
        """Process image data and return optimized version with metadata"""
        try:
            # Open image from bytes
            image = Image.open(io.BytesIO(image_data))
            
            # Get original metadata
            metadata = {
                'format': image.format,
                'mode': image.mode,
                'size': image.size,
                'original_size': len(image_data)
            }
            
            # Convert to RGB if necessary (for JPEG compatibility)
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create a white background for transparency
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # Resize if too large (max 1920x1920)
            max_size = (1920, 1920)
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
                metadata['resized'] = True
                metadata['new_size'] = image.size
            
            # Save to bytes with optimization
            output = io.BytesIO()
            
            # Determine format based on filename
            file_ext = os.path.splitext(filename.lower())[1]
            if file_ext in ['.jpg', '.jpeg']:
                image.save(output, format='JPEG', quality=85, optimize=True)
                metadata['output_format'] = 'JPEG'
            elif file_ext == '.png':
                image.save(output, format='PNG', optimize=True)
                metadata['output_format'] = 'PNG'
            elif file_ext == '.webp':
                image.save(output, format='WEBP', quality=85, optimize=True)
                metadata['output_format'] = 'WEBP'
            else:
                # Default to JPEG for unknown formats
                image.save(output, format='JPEG', quality=85, optimize=True)
                metadata['output_format'] = 'JPEG'
            
            processed_data = output.getvalue()
            metadata['processed_size'] = len(processed_data)
            metadata['compression_ratio'] = metadata['original_size'] / metadata['processed_size']
            
            logger.info(f"Image processed successfully: {filename}, size reduced from {metadata['original_size']} to {metadata['processed_size']} bytes")
            
            return processed_data, metadata
            
        except Exception as e:
            logger.error(f"Failed to process image {filename}: {str(e)}")
            return None, None
    
    def process_audio(self, audio_data: bytes, filename: str) -> Tuple[Optional[bytes], Optional[Dict[str, Any]]]:
        """Process audio data and return optimized version with metadata"""
        try:
            # Determine audio format from filename
            file_ext = os.path.splitext(filename.lower())[1]
            
            # Load audio from bytes
            audio_io = io.BytesIO(audio_data)
            
            # AudioSegment can auto-detect format, but we'll specify it if we know it
            if file_ext == '.mp3':
                audio = AudioSegment.from_mp3(audio_io)
            elif file_ext == '.wav':
                audio = AudioSegment.from_wav(audio_io)
            elif file_ext == '.ogg':
                audio = AudioSegment.from_ogg(audio_io)
            elif file_ext == '.m4a':
                audio = AudioSegment.from_file(audio_io, format="m4a")
            else:
                # Try to auto-detect
                audio = AudioSegment.from_file(audio_io)
            
            # Get metadata
            metadata = {
                'duration': len(audio) / 1000.0,  # duration in seconds
                'channels': audio.channels,
                'frame_rate': audio.frame_rate,
                'sample_width': audio.sample_width,
                'original_size': len(audio_data)
            }
            
            # Optimize audio (convert to MP3 with reasonable quality)
            # Normalize audio levels
            normalized_audio = audio.normalize()
            
            # Convert to mono if stereo (saves space)
            if normalized_audio.channels > 1:
                normalized_audio = normalized_audio.set_channels(1)
                metadata['converted_to_mono'] = True
            
            # Reduce sample rate if too high (WhatsApp supports up to 16kHz for voice)
            if normalized_audio.frame_rate > 16000:
                normalized_audio = normalized_audio.set_frame_rate(16000)
                metadata['resampled'] = True
                metadata['new_frame_rate'] = 16000
            
            # Export as MP3
            output = io.BytesIO()
            normalized_audio.export(output, format="mp3", bitrate="64k")
            
            processed_data = output.getvalue()
            metadata['processed_size'] = len(processed_data)
            metadata['compression_ratio'] = metadata['original_size'] / metadata['processed_size']
            metadata['output_format'] = 'MP3'
            
            logger.info(f"Audio processed successfully: {filename}, duration: {metadata['duration']:.2f}s, size reduced from {metadata['original_size']} to {metadata['processed_size']} bytes")
            
            return processed_data, metadata
            
        except Exception as e:
            logger.error(f"Failed to process audio {filename}: {str(e)}")
            return None, None
    
    def extract_audio_from_video(self, video_data: bytes, filename: str) -> Tuple[Optional[bytes], Optional[Dict[str, Any]]]:
        """Extract audio from video file"""
        try:
            # Load video and extract audio
            video_io = io.BytesIO(video_data)
            audio = AudioSegment.from_file(video_io)
            
            # Process extracted audio
            return self.process_audio(audio.export(format="wav").read(), f"extracted_audio_{filename}.wav")
            
        except Exception as e:
            logger.error(f"Failed to extract audio from video {filename}: {str(e)}")
            return None, None
    
    def get_media_type(self, filename: str, mime_type: str = None) -> str:
        """Determine media type from filename and/or mime type"""
        file_ext = os.path.splitext(filename.lower())[1]
        
        if mime_type:
            if mime_type.startswith('image/'):
                return 'image'
            elif mime_type.startswith('audio/'):
                return 'audio'
            elif mime_type.startswith('video/'):
                return 'video'
            elif mime_type.startswith('application/') or mime_type.startswith('text/'):
                return 'document'
        
        # Fallback to file extension
        if file_ext in self.supported_image_formats:
            return 'image'
        elif file_ext in self.supported_audio_formats:
            return 'audio'
        elif file_ext in self.supported_video_formats:
            return 'video'
        else:
            return 'document'
    
    def is_supported_format(self, filename: str, media_type: str) -> bool:
        """Check if the file format is supported for processing"""
        file_ext = os.path.splitext(filename.lower())[1]
        
        if media_type == 'image':
            return file_ext in self.supported_image_formats
        elif media_type == 'audio':
            return file_ext in self.supported_audio_formats
        elif media_type == 'video':
            return file_ext in self.supported_video_formats
        else:
            return True  # Documents are generally supported
    
    def get_file_info(self, data: bytes, filename: str) -> Dict[str, Any]:
        """Get basic file information"""
        file_ext = os.path.splitext(filename.lower())[1]
        mime_type, _ = mimetypes.guess_type(filename)
        
        return {
            'filename': filename,
            'size': len(data),
            'extension': file_ext,
            'mime_type': mime_type,
            'media_type': self.get_media_type(filename, mime_type),
            'is_supported': self.is_supported_format(filename, self.get_media_type(filename, mime_type))
        }
