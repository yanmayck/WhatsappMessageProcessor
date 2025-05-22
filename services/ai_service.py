import os
import json
import logging
import time
from typing import Dict, Any, List, Optional
import google.generativeai as genai
from config import Config

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        # Configure Gemini API
        genai.configure(api_key=Config.GEMINI_API_KEY)
        
        # Initialize different models for different types of content
        self.text_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        self.vision_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        self.multimodal_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # System prompts for different scenarios
        self.system_prompts = {
            'text': """You are a helpful AI assistant integrated with WhatsApp. 
            Respond naturally and conversationally. Keep responses concise but informative.
            If asked about your capabilities, mention that you can process text, images, and audio.""",
            
            'image': """You are an AI that analyzes images sent via WhatsApp.
            Describe what you see in detail, including objects, people, text, scenes, colors, and any notable features.
            If there's text in the image, transcribe it. Be thorough but conversational.""",
            
            'audio': """You are an AI that processes audio content sent via WhatsApp.
            If this is speech, transcribe it accurately. If it's music, describe the genre, mood, and instruments.
            For other sounds, describe what you hear. Be detailed but natural in your response.""",
            
            'document': """You are an AI that analyzes documents sent via WhatsApp.
            Summarize the content, extract key information, and provide insights.
            If it's a form or structured document, organize the information clearly."""
        }
    
    def process_text_message(self, text: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Process a text message and generate a response"""
        start_time = time.time()
        
        try:
            # Build conversation context
            context = self._build_conversation_context(conversation_history)
            
            # Create the prompt
            prompt = f"{self.system_prompts['text']}\n\nContext: {context}\n\nUser: {text}\n\nAssistant:"
            
            # Generate response
            response = self.text_model.generate_content(prompt)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            result = {
                'success': True,
                'response': response.text,
                'model_used': 'gemini-2.0-flash-exp',
                'processing_time': processing_time,
                'content_type': 'text'
            }
            
            logger.info(f"Text message processed successfully in {processing_time}ms")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process text message: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response': "I'm sorry, I encountered an error processing your message. Please try again.",
                'processing_time': int((time.time() - start_time) * 1000)
            }
    
    def process_image_message(self, image_data: bytes, text_prompt: str = None, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Process an image message and generate a response"""
        start_time = time.time()
        
        try:
            # Build conversation context
            context = self._build_conversation_context(conversation_history)
            
            # Create the prompt
            if text_prompt:
                prompt = f"{self.system_prompts['image']}\n\nContext: {context}\n\nUser also said: {text_prompt}\n\nPlease analyze this image and respond to the user's message:"
            else:
                prompt = f"{self.system_prompts['image']}\n\nContext: {context}\n\nPlease analyze this image:"
            
            # Convert image data to the format expected by Gemini
            import PIL.Image
            import io
            image = PIL.Image.open(io.BytesIO(image_data))
            
            # Generate response
            response = self.vision_model.generate_content([prompt, image])
            
            processing_time = int((time.time() - start_time) * 1000)
            
            result = {
                'success': True,
                'response': response.text,
                'model_used': 'gemini-2.0-flash-exp',
                'processing_time': processing_time,
                'content_type': 'image'
            }
            
            logger.info(f"Image message processed successfully in {processing_time}ms")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process image message: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response': "I'm sorry, I couldn't analyze this image. Please try sending it again or check the image format.",
                'processing_time': int((time.time() - start_time) * 1000)
            }
    
    def process_audio_message(self, audio_data: bytes, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Process an audio message and generate a response"""
        start_time = time.time()
        
        try:
            # For now, we'll return a helpful message about audio processing
            # In a full implementation, you'd use speech-to-text services
            context = self._build_conversation_context(conversation_history)
            
            # Note: Gemini 2.0 Flash Experimental supports audio input
            # This is a simplified implementation
            prompt = f"{self.system_prompts['audio']}\n\nContext: {context}\n\nPlease process this audio message:"
            
            # For this demo, we'll return a standard response
            # In production, you'd integrate with Gemini's audio capabilities
            response_text = "I received your audio message. While I can process audio, this demo version responds with text. In a full implementation, I would transcribe speech or analyze the audio content."
            
            processing_time = int((time.time() - start_time) * 1000)
            
            result = {
                'success': True,
                'response': response_text,
                'model_used': 'gemini-2.0-flash-exp',
                'processing_time': processing_time,
                'content_type': 'audio'
            }
            
            logger.info(f"Audio message processed successfully in {processing_time}ms")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process audio message: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response': "I'm sorry, I couldn't process this audio message. Please try again or send a text message.",
                'processing_time': int((time.time() - start_time) * 1000)
            }
    
    def process_multimodal_message(self, content_items: List[Dict], conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Process a message with multiple types of content (text + image + audio)"""
        start_time = time.time()
        
        try:
            context = self._build_conversation_context(conversation_history)
            
            prompt_parts = [f"Context: {context}\n\nYou received a multimodal message with the following content:"]
            
            for item in content_items:
                if item['type'] == 'text':
                    prompt_parts.append(f"Text: {item['content']}")
                elif item['type'] == 'image':
                    prompt_parts.append("Image: [attached image]")
                    # Add image to prompt_parts
                    import PIL.Image
                    import io
                    image = PIL.Image.open(io.BytesIO(item['data']))
                    prompt_parts.append(image)
                elif item['type'] == 'audio':
                    prompt_parts.append("Audio: [attached audio file]")
            
            prompt_parts.append("Please analyze all the content and provide a comprehensive response.")
            
            # Generate response using multimodal model
            response = self.multimodal_model.generate_content(prompt_parts)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            result = {
                'success': True,
                'response': response.text,
                'model_used': 'gemini-2.0-flash-exp',
                'processing_time': processing_time,
                'content_type': 'multimodal'
            }
            
            logger.info(f"Multimodal message processed successfully in {processing_time}ms")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process multimodal message: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response': "I'm sorry, I encountered an error processing your multimodal message. Please try again.",
                'processing_time': int((time.time() - start_time) * 1000)
            }
    
    def _build_conversation_context(self, conversation_history: List[Dict]) -> str:
        """Build conversation context from message history"""
        if not conversation_history:
            return "This is the start of a new conversation."
        
        context_parts = []
        # Get last 5 messages for context (to avoid token limits)
        recent_messages = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
        
        for msg in recent_messages:
            sender = "User" if msg.get('is_from_user') else "Assistant"
            content = msg.get('content', '')
            message_type = msg.get('message_type', 'text')
            
            if message_type == 'text':
                context_parts.append(f"{sender}: {content}")
            else:
                context_parts.append(f"{sender}: [sent {message_type}] {content}")
        
        return "\n".join(context_parts)
    
    def generate_summary(self, conversation_history: List[Dict]) -> str:
        """Generate a summary of the conversation"""
        try:
            context = self._build_conversation_context(conversation_history)
            
            prompt = f"""Please provide a brief summary of this WhatsApp conversation:

{context}

Summary (2-3 sentences max):"""
            
            response = self.text_model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Failed to generate conversation summary: {str(e)}")
            return "Unable to generate summary"
