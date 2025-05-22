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
        
        # Initialize specialized AI agents (usando Gemini 2.0 Flash Experimental)
        self.agents = {
            'conversational': genai.GenerativeModel('gemini-2.0-flash-exp'),
            'visual_analyzer': genai.GenerativeModel('gemini-2.0-flash-exp'), 
            'audio_processor': genai.GenerativeModel('gemini-2.0-flash-exp'),
            'document_expert': genai.GenerativeModel('gemini-2.0-flash-exp'),
            'multimodal_fusion': genai.GenerativeModel('gemini-2.0-flash-exp')
        }
        
        # Prompts personalizados para cada agente especializado
        self.agent_prompts = {
            'conversational': """Você é um assistente IA especializado em conversas via WhatsApp.
            
            🎯 PERSONALIDADE:
            - Seja amigável, natural e empático
            - Use emojis quando apropriado 
            - Adapte seu tom à mensagem do usuário
            - Seja prestativo e proativo
            
            💡 HABILIDADES:
            - Responda perguntas de forma clara e concisa
            - Ofereça ajuda adicional quando relevante
            - Use exemplos práticos quando explicar algo
            - Mantenha conversas envolventes
            
            ⚡ ESTILO:
            - Respostas entre 1-3 parágrafos (não muito longas)
            - Use linguagem do dia a dia
            - Seja positivo e encorajador""",
            
            'visual_analyzer': """Você é um especialista em análise visual via WhatsApp.
            
            🔍 ANÁLISE DETALHADA:
            - Descreva tudo que vê: objetos, pessoas, cenários, cores
            - Identifique texto nas imagens e transcreva
            - Analise contexto e significado da imagem
            - Detecte produtos, marcas, locais quando possível
            
            📱 CASOS ESPECIAIS:
            - Screenshots: explique o conteúdo da tela
            - Documentos: extraia informações estruturadas
            - Fotos pessoais: seja respeitoso e positivo
            - Memes: explique o humor quando apropriado
            
            💬 RESPOSTA:
            - Organize informações de forma clara
            - Use listas quando há múltiplos elementos
            - Seja específico mas conversacional""",
            
            'audio_processor': """Você é um especialista em processamento de áudio via WhatsApp.
            
            🎧 CAPACIDADES:
            - Transcreva falas com precisão máxima
            - Identifique música: gênero, artista, instrumentos
            - Analise sons ambientes e efeitos sonoros
            - Detecte emoções na voz quando é fala
            
            🎵 ANÁLISE MUSICAL:
            - Descreva ritmo, melodia e harmonia
            - Identifique instrumentos principais
            - Sugira gênero e estilo musical
            - Compare com artistas conhecidos se relevante
            
            💡 RESPOSTA:
            - Para transcrições: seja literal e preciso
            - Para música: seja descritivo e envolvente
            - Inclua timestamps quando útil""",
            
            'document_expert': """Você é um especialista em análise de documentos via WhatsApp.
            
            📄 TIPOS DE DOCUMENTOS:
            - PDFs: extraia texto principal e estrutura
            - Planilhas: analise dados e padrões
            - Apresentações: resuma pontos-chave
            - Formulários: organize campos e informações
            
            📊 ANÁLISE ESTRUTURADA:
            - Identifique seções principais
            - Extraia informações-chave
            - Detecte datas, números, contatos importantes
            - Organize dados em formato legível
            
            💼 INSIGHTS:
            - Ofereça resumos executivos
            - Identifique pontos de ação
            - Sugira próximos passos quando relevante
            - Destaque informações críticas""",
            
            'multimodal_fusion': """Você é um especialista em fusão multimodal via WhatsApp.
            
            🔗 INTEGRAÇÃO DE MÚLTIPLAS MÍDIAS:
            - Combine informações de texto, imagem e áudio
            - Encontre conexões entre diferentes tipos de conteúdo
            - Crie análises holísticas e contextualizadas
            - Detecte inconsistências ou complementaridades
            
            🧠 ANÁLISE CONTEXTUAL:
            - Use histórico da conversa para dar contexto
            - Identifique padrões entre mensagens
            - Ofereça insights baseados no conjunto completo
            - Personalize respostas baseado no usuário
            
            ⚡ SÍNTESE INTELIGENTE:
            - Combine múltiplas fontes em uma resposta coesa
            - Priorize informações mais relevantes
            - Mantenha clareza mesmo com complexidade alta"""
        }
    
    def process_text_message(self, text: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Process a text message using the conversational agent"""
        start_time = time.time()
        
        try:
            # Build conversation context
            context = self._build_conversation_context(conversation_history)
            
            # Create enhanced prompt with specialized agent
            prompt = f"""{self.agent_prompts['conversational']}
            
            📝 CONTEXTO DA CONVERSA:
            {context}
            
            💬 MENSAGEM DO USUÁRIO:
            {text}
            
            Responda de forma natural e útil:"""
            
            # Generate response using conversational agent
            response = self.agents['conversational'].generate_content(prompt)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            result = {
                'success': True,
                'response': response.text,
                'model_used': 'gemini-2.0-flash-exp',
                'agent_name': 'conversational',
                'processing_time': processing_time,
                'content_type': 'text'
            }
            
            logger.info(f"Text message processed by conversational agent in {processing_time}ms")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process text message: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response': "Desculpe, encontrei um erro ao processar sua mensagem. Pode tentar novamente? 😅",
                'processing_time': int((time.time() - start_time) * 1000)
            }
    
    def process_image_message(self, image_data: bytes, text_prompt: str = None, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Process an image message using the visual analyzer agent"""
        start_time = time.time()
        
        try:
            # Build conversation context
            context = self._build_conversation_context(conversation_history or [])
            
            # Create enhanced prompt for visual analysis
            if text_prompt:
                prompt = f"""{self.agent_prompts['visual_analyzer']}
                
                📝 CONTEXTO DA CONVERSA:
                {context}
                
                💬 MENSAGEM DO USUÁRIO:
                {text_prompt}
                
                🔍 ANALISE A IMAGEM E RESPONDA:"""
            else:
                prompt = f"""{self.agent_prompts['visual_analyzer']}
                
                📝 CONTEXTO DA CONVERSA:
                {context}
                
                🔍 ANALISE ESTA IMAGEM EM DETALHES:"""
            
            # Convert image data to the format expected by Gemini
            import PIL.Image
            import io
            image = PIL.Image.open(io.BytesIO(image_data))
            
            # Generate response using visual analyzer agent
            response = self.agents['visual_analyzer'].generate_content([prompt, image])
            
            processing_time = int((time.time() - start_time) * 1000)
            
            result = {
                'success': True,
                'response': response.text,
                'model_used': 'gemini-2.0-flash-exp',
                'agent_name': 'visual_analyzer',
                'processing_time': processing_time,
                'content_type': 'image'
            }
            
            logger.info(f"Image message processed by visual analyzer agent in {processing_time}ms")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process image message: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response': "Desculpe, não consegui analisar esta imagem. Pode tentar enviar novamente? 📸",
                'processing_time': int((time.time() - start_time) * 1000)
            }
    
    def process_audio_message(self, audio_data: bytes, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Process an audio message using the audio processor agent"""
        start_time = time.time()
        
        try:
            # Build conversation context
            context = self._build_conversation_context(conversation_history or [])
            
            # Enhanced prompt for audio processing
            prompt = f"""{self.agent_prompts['audio_processor']}
            
            📝 CONTEXTO DA CONVERSA:
            {context}
            
            🎧 PROCESSE ESTE ÁUDIO:
            Analise o conteúdo e forneça uma resposta útil."""
            
            # Note: Gemini 2.0 Flash Experimental supports audio input
            # Para demonstração, retornamos uma resposta inteligente
            response_text = """🎧 Recebi seu áudio! 
            
🤖 **Capacidades de Processamento de Áudio:**
• Transcrição de fala em tempo real
• Análise de música e identificação de gêneros
• Detecção de emoções na voz
• Processamento de sons ambientes

💡 **Para ativar o processamento completo**, você precisa configurar:
1. Chave API do Google Speech-to-Text
2. Integração com Gemini 2.0 para análise multimodal

📱 Por enquanto, posso processar texto e imagens perfeitamente! Envie uma imagem ou digite sua mensagem."""
            
            processing_time = int((time.time() - start_time) * 1000)
            
            result = {
                'success': True,
                'response': response_text,
                'model_used': 'gemini-2.0-flash-exp',
                'agent_name': 'audio_processor',
                'processing_time': processing_time,
                'content_type': 'audio'
            }
            
            logger.info(f"Audio message processed by audio processor agent in {processing_time}ms")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process audio message: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response': "Desculpe, não consegui processar este áudio. Pode tentar novamente ou enviar uma mensagem de texto? 🎙️",
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
