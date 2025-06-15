import os
import json
import logging
import time
from typing import Dict, Any, List, Optional
import tempfile
import subprocess
import uuid

from agno.agent import Agent
from agno.models.google import Gemini
from agno.team import Team
from services.geolocation_service import GeolocationService
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

from config import Config

logger = logging.getLogger(__name__)

try:
    from google.ai.generativelanguage import Part, Blob as InlineData
    GOOGLE_GEMINI_PARTS_AVAILABLE = True
except ImportError:
    GOOGLE_GEMINI_PARTS_AVAILABLE = False
    Part = None
    InlineData = None
    if logger:
        logger.warning("Could not import Part/Blob from google.ai.generativelanguage. Multimodality may not work as expected.")
    else:
        print("WARNING: Could not import Part/Blob from google.ai.generativelanguage.")

class AIService:
    def __init__(self):
        self.model_name = Config.GEMINI_API_KEY and "gemini-1.5-flash-latest"
        self.api_key = Config.GEMINI_API_KEY

        if not self.api_key:
            logger.error("GEMINI_API_KEY is not configured. AIService will not work.")
            raise ValueError("GEMINI_API_KEY is required for AIService.")

        self.geolocation_service = GeolocationService()

        # --- Construção Dinâmica do Prompt Conversacional ---
        # As seções são combinadas para criar um guia de comportamento completo e personalizável para a IA.
        conversational_prompt = f"""
        Você é {Config.AI_NAME}, um assistente de IA para conversas no WhatsApp.

        ---
        **CONTEXTO DO NEGÓCIO:**
        {Config.AI_BUSINESS_CONTEXT}
        ---
        **🎯 PERSONALIDADE E TOM:**
        Sua personalidade deve ser: {Config.AI_PERSONALITY_DESCRIPTION}
        ---
        **⚡ ESTILO DE RESPOSTA:**
        {Config.AI_RESPONSE_STYLE}
        ---
        **💡 HABILIDADES GERAIS:**
            - Responda perguntas de forma clara e concisa. Ofereça ajuda e use exemplos.
        - Mantenha conversas envolventes e naturais.
        ---
        **⚠️ REGRAS DE ESCALONAMENTO PARA ATENDIMENTO HUMANO:**
            - Se o usuário pedir para falar com um humano (ex: 'falar com atendente', 'quero um humano'), sua resposta DEVE incluir o marcador [USER_REQUESTS_HUMAN_AGENT].
            - Se você não conseguir ajudar, o usuário estiver frustrado, ou a conversa entrar em loop, sua resposta DEVE incluir o marcador [AI_NEEDS_ASSISTANCE].
        - Exemplo de escalonamento pelo usuário: "Entendido! Vou te transferir para um de nossos atendentes. [USER_REQUESTS_HUMAN_AGENT] Por favor, aguarde."
        - Exemplo de escalonamento pela IA: "Hmm, essa é uma pergunta complexa para mim. [AI_NEEDS_ASSISTANCE] Vou pedir ajuda a um colega humano."
        """

        self.agent_prompts = {
            'conversational': "\n".join([line.strip() for line in conversational_prompt.strip().splitlines()]),
            'visual_analyzer': "Você é um assistente visual. Sua função é analisar imagens e vídeos no contexto de uma conversa. Descreva o que você vê de forma conversacional. Se o usuário fizer uma pergunta, responda com base no conteúdo visual.",
            'audio_processor': "Sua única função é transcrever o áudio fornecido com a maior precisão possível. Apenas retorne o texto transcrito. Se não for fala, descreva os sons (ex: [música], [risada]). Não adicione nenhuma outra palavra ou frase à sua resposta.",
            'document_expert': "Você é um especialista em análise de documentos. Extraia e estruture informações-chave de PDFs, planilhas e outros documentos.",
            'geolocation_specialist': """Você é um assistente IA especializado em calcular fretes e distâncias.
            - Peça o endereço de ORIGEM e DESTINO se não forem fornecidos.
            - Se você receber coordenadas de latitude e longitude, informe ao usuário que você recebeu a localização e peça a informação que falta (o endereço de destino) para poder calcular o frete.
            - Use a ferramenta para calcular distância e custo.
            - Apresente o resultado de forma clara: Distância (km), Duração Estimada e Custo do Frete (R$).
            - Use a ferramenta. NÃO invente valores.
            """,
            'profile_manager': """Você é um analista de dados silencioso. Sua única função é identificar informações de perfil do usuário na mensagem fornecida e estruturá-las em JSON.

            OBJETIVO: Identificar atributos chave que raramente mudam (nome, endereço, telefone, e-mail, preferências, etc.). Ignore informações transacionais como "meu último pedido foi X".

            REGRAS DE SAÍDA:
            1.  Sua saída DEVE SER SEMPRE um objeto JSON válido. Não inclua texto explicativo, apenas o JSON.
            2.  Se você identificar uma informação de perfil, retorne:
                `{"action": "SAVE", "data": {"key": "chave_identificada", "value": "valor_extraído"}}`
            3.  As chaves permitidas são: "name", "address", "email", "phone", "company", "birthday", "preferences".
            4.  Se a mensagem NÃO contiver nenhuma informação de perfil clara e acionável, retorne:
                `{"action": "NONE"}`
            
            EXEMPLOS:
            - Mensagem: "Olá, meu nome é Carlos." -> Saída: `{"action": "SAVE", "data": {"key": "name", "value": "Carlos"}}`
            - Mensagem: "Gostaria de registrar minha preferência por chocolate amargo." -> Saída: `{"action": "SAVE", "data": {"key": "preferences", "value": "prefere chocolate amargo"}}`
            - Mensagem: "Pode me enviar a fatura?" -> Saída: `{"action": "NONE"}`
            - Mensagem: "meu endereço é rua das flores 123" -> Saída: `{"action": "SAVE", "data": {"key": "address", "value": "Rua das Flores, 123"}}`
            """,
            'multimodal_fusion': "Você é um especialista em fusão multimodal. Combine informações de texto, imagem e áudio para criar análises holísticas e contextualizadas."
        }

        self.specialist_agents: Dict[str, Agent] = {}
        agent_list_for_team: List[Agent] = []

        for agent_name_key, system_prompt in self.agent_prompts.items():
            descriptive_name = agent_name_key.replace("_", " ").title()
            tools_for_agent = [self.calculate_shipping_tool] if agent_name_key == 'geolocation_specialist' else None
            gemini_model = Gemini(id=self.model_name, api_key=self.api_key)
            specialist_agent = Agent(
                name=descriptive_name,
                model=gemini_model,
                instructions=[system_prompt],
                role=f"Especialista em {descriptive_name}",
                tools=tools_for_agent,
                expected_output="Uma resposta relevante ou a chamada de uma ferramenta.",
                markdown=False 
            )
            self.specialist_agents[agent_name_key] = specialist_agent
            agent_list_for_team.append(specialist_agent)

        team_model = Gemini(id=self.model_name, api_key=self.api_key)
        team_instructions = [
            "Você é um despachante de IA mestre para um chatbot do WhatsApp.",
            "Sua tarefa é analisar a solicitação do usuário e o histórico da conversa, e encaminhar para o agente especialista mais apropriado da sua equipe.",
            "REGRA DE ROTEAMENTO:",
            "1. Se a entrada contiver uma IMAGEM, encaminhe para o Visual Analyzer.",
            "2. Se a entrada contiver ÁUDIO, encaminhe para o Audio Processor.",
            "3. Se a intenção for sobre FRETE/ENTREGA/DISTÂNCIA, encaminhe para o Geolocation Specialist.",
            "4. Para MÚLTIPLOS tipos de mídia, use o Multimodal Fusion.",
            "5. Para todo o resto (conversa geral, texto), use o Conversational Specialist.",
            "Sua saída final deve ser a resposta do agente especialista escolhido."
        ]
        self.team = Team(
            name="WhatsAppMasterAITeam",
            members=agent_list_for_team,
            model=team_model,
            instructions=team_instructions
        )
        logger.info("AIService inicializado com Master Team e agentes especialistas.")

    def _prepare_text_and_history(self, text: str, conversation_history: Optional[List[Dict[str, Any]]] = None, profile_data: Optional[Dict] = None, location_data: Optional[Dict] = None) -> str:
        history_lines = []
        if conversation_history:
            for msg in conversation_history:
                sender = "Usuário" if msg.get('sender_type') == 'user' else "Assistente"
                content = msg.get('message_text', '').strip()
                if content:
                    history_lines.append(f"{sender}: {content}")
        history_str = "\n".join(history_lines)
        
        final_prompt_parts = []

        if profile_data:
            profile_items = [f"- {key}: {value}" for key, value in profile_data.items()]
            profile_str = "\n".join(profile_items)
            final_prompt_parts.append(f"INFORMAÇÕES CONHECIDAS SOBRE O USUÁRIO (use isso para personalizar a resposta):\n{profile_str}")

        if location_data:
            final_prompt_parts.append(f"LOCALIZAÇÃO ATUAL DO USUÁRIO (use isso como contexto de origem): Latitude {location_data['latitude']}, Longitude {location_data['longitude']}")

        if history_str:
            final_prompt_parts.append(f"Contexto da conversa anterior:\n{history_str}")
        
        current_message_text = text.strip()
        if current_message_text:
            final_prompt_parts.append(f"Mensagem atual do usuário:\n{current_message_text}")
        
        return "\n\n".join(final_prompt_parts) if final_prompt_parts else "Olá."

    def calculate_shipping_tool(self, origin: str, destination: str) -> Dict[str, Any]:
        logger.info(f"[TOOL CALL] calculate_shipping com origem: '{origin}', destino: '{destination}'")
        if not origin or not destination:
            return {"status": "error", "message": "Por favor, forneça os endereços de origem e destino."}

        result = self.geolocation_service.get_distance_and_duration(origin, destination)
        if result:
            distance_km, _, _, duration_text = result
            shipping_fee = self.geolocation_service.calculate_shipping_fee(distance_km)
            response_message = f"Cálculo para '{origin}' até '{destination}':\n- Distância: {distance_km:.2f} km\n- Duração Estimada: {duration_text}\n- Custo do Frete: R$ {shipping_fee:.2f}"
            logger.info(f"Resultado da ferramenta: {response_message}")
            return {"status": "success", "message_to_user": response_message}
        else:
            logger.error(f"Falha ao calcular distância/frete entre '{origin}' e '{destination}'.")
            return {"status": "error", "message": "Desculpe, não consegui calcular o frete. Verifique os endereços."}

    def process_text_message(self, text: str, conversation_history: List[Dict] = None, profile_data: Optional[Dict] = None, location_data: Optional[Dict] = None) -> Dict[str, Any]:
        if not text or not text.strip():
            return {'success': True, 'response': "Olá! Como posso te ajudar?", 'metadata': {}}
        
        conversational_agent = self.specialist_agents['conversational']
        # --- Lógica de Roteamento Simples ---
        # Se a intenção parecer relacionada a frete, usar o especialista.
        # Poderíamos usar uma lógica mais avançada aqui, mas para começar:
        if any(keyword in text.lower() for keyword in ['frete', 'entrega', 'distância', 'endereço', 'localização', 'calcular']):
            conversational_agent = self.specialist_agents['geolocation_specialist']
            logger.info("Roteado para Geolocation Specialist com base em palavras-chave.")
        
        start_time = time.time()
        prompt = self._prepare_text_and_history(text, conversation_history, profile_data, location_data)
        run_response = conversational_agent.run(prompt)
        response_text = run_response.content if hasattr(run_response, 'content') else str(run_response)
        processing_time_ms = int((time.time() - start_time) * 1000)

        logger.info(f"Mensagem de texto processada pelo {conversational_agent.name} em {processing_time_ms}ms.")
        return {
            'success': True,
            'response': response_text,
            'metadata': {'agent_name': conversational_agent.name, 'processing_time_ms': processing_time_ms}
        }

    def process_image_message(self, image_data: bytes, text_prompt: str = "", conversation_history: List[Dict] = None, profile_data: Optional[Dict] = None) -> Dict[str, Any]:
        start_time = time.time()
        agent = self.specialist_agents['visual_analyzer']
        
        # Usa o text_prompt se fornecido, senão usa um prompt padrão.
        prompt = self._prepare_text_and_history(text_prompt or "Analise esta imagem em detalhes.", conversation_history, profile_data)
        
        temp_image_path = None
        try:
            # Salva os bytes da imagem em um arquivo temporário
            fd, temp_image_path = tempfile.mkstemp(suffix=".jpg")
            with os.fdopen(fd, 'wb') as temp_file:
                temp_file.write(image_data)
            
            # Prepara a entrada para o agente no formato esperado
            image_input = [{"filepath": temp_image_path}]
            
            logger.debug(f"Enviando para Visual Analyzer. Prompt: '{prompt[:100]}...', Imagem: {image_input}")
            
            # Executa o agente
            run_response = agent.run(prompt, images=image_input)
            response_text = run_response.content if hasattr(run_response, 'content') else str(run_response)
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Imagem processada pelo Visual Analyzer em {processing_time_ms}ms.")
            
            return {
                'success': True,
                'response': response_text,
                'metadata': {'agent_name': 'Visual Analyzer (Shortcut)', 'processing_time_ms': processing_time_ms}
            }
        except Exception as e:
            logger.error(f"Falha ao processar imagem com Visual Analyzer: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'response': "Desculpe, a IA encontrou um problema ao analisar a imagem. 😥"
            }
        finally:
            # Garante que o arquivo temporário seja removido
            if temp_image_path and os.path.exists(temp_image_path):
                os.remove(temp_image_path)
                logger.debug(f"Removed temp image file: {temp_image_path}")

    def process_video_message(self, video_data: bytes, text_prompt: str = "", conversation_history: List[Dict] = None, profile_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Processa uma mensagem de vídeo, analisando seu conteúdo."""
        start_time = time.time()
        agent = self.specialist_agents['visual_analyzer']
        
        prompt = self._prepare_text_and_history(text_prompt or "Analise este vídeo em detalhes e descreva o que acontece.", conversation_history, profile_data)
        
        temp_video_path = None
        try:
            # Salva os bytes do vídeo em um arquivo temporário com a extensão correta.
            fd, temp_video_path = tempfile.mkstemp(suffix=".mp4")
            with os.fdopen(fd, 'wb') as temp_file:
                temp_file.write(video_data)
            
            video_input = [{"filepath": temp_video_path}]
            logger.debug(f"Enviando para Visual Analyzer. Prompt: '{prompt[:100]}...', Vídeo: {video_input}")
            
            # Executa o agente, passando o vídeo para análise.
            # Assumimos que a biblioteca `agno` suporta o parâmetro `videos`.
            run_response = agent.run(prompt, videos=video_input)
            response_text = run_response.content if hasattr(run_response, 'content') else str(run_response)
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Vídeo processado pelo Visual Analyzer em {processing_time_ms}ms.")
            
            return {
                'success': True,
                'response': response_text,
                'metadata': {'agent_name': 'Visual Analyzer (Shortcut)', 'processing_time_ms': processing_time_ms}
            }
        except Exception as e:
            logger.error(f"Falha ao processar vídeo com Visual Analyzer: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'response': "Desculpe, a IA encontrou um problema ao analisar o vídeo. 😥"
            }
        finally:
            # Garante que o arquivo de vídeo temporário seja removido
            if temp_video_path and os.path.exists(temp_video_path):
                os.remove(temp_video_path)
                logger.debug(f"Removed temp video file: {temp_video_path}")

    def process_audio_message(self, audio_data: bytes, conversation_history: List[Dict] = None, profile_data: Optional[Dict] = None) -> Dict[str, Any]:
        start_time = time.time()
        agent = self.specialist_agents['audio_processor']
        # A tarefa é focada na transcrição do áudio fornecido.
        prompt = "Transcreva o áudio a seguir. Se não for fala, descreva os sons que você ouve."

        temp_out_path = None
        try:
            # Adicionar uma verificação para garantir que os dados do áudio não estão vazios
            if not audio_data:
                logger.error("process_audio_message received empty audio data. Aborting ffmpeg conversion.")
                return {
                    'success': False,
                    'error': "Empty audio data received, possibly due to a decryption error.",
                    'response': "Desculpe, não consegui processar o áudio. Parece que houve um problema na descriptografia. 😥"
                }

            # Etapa 1: Em vez de salvar um arquivo temporário, vamos passar os dados de áudio
            # diretamente para o stdin do ffmpeg para evitar race conditions no sistema de arquivos.
            fd_out, temp_out_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd_out)  # Fechar o handle para que o ffmpeg possa escrever no caminho

            logger.debug(f"Attempting ffmpeg conversion via stdin to {temp_out_path}")
            
            command = [
                'ffmpeg',
                '-v', 'error',           # Logar apenas erros
                '-f', 'ogg',             # Assumir o formato de contêiner OGG para a entrada
                '-c:a', 'libopus',       # EXPLICITAMENTE use o codec libopus para a entrada
                '-i', '-',               # Ler a entrada do stdin (pipe)
                '-acodec', 'pcm_s16le',  # Codec de áudio de saída (WAV padrão)
                '-ar', '16000',          # Taxa de amostragem de 16kHz (bom para ASR)
                '-ac', '1',              # Um canal de áudio (mono)
                '-y',                    # Sobrescrever arquivo de saída
                temp_out_path
            ]
            
            # Executa o comando, passando os bytes do áudio para o stdin do processo.
            # text=False é crucial, pois o input e o stderr são tratados como bytes.
            result = subprocess.run(command, input=audio_data, capture_output=True, check=False)

            if result.returncode != 0:
                # Decodificar stderr para logar o erro do ffmpeg de forma legível
                stderr_text = result.stderr.decode('utf-8', errors='replace').strip()
                logger.error(f"ffmpeg conversion failed with code {result.returncode}. stderr: {stderr_text}")
                raise Exception(f"ffmpeg failed: {stderr_text}")
            
            logger.debug(f"Successfully converted audio to {temp_out_path}")

            # Etapa 2: Preparar o arquivo WAV convertido para o agente.
            audio_input = [{"filepath": temp_out_path}]

            logger.debug(f"Enviando para Audio Processor. Prompt: '{prompt[:100]}...', Audio (convertido para WAV): {audio_input}")
            
            # Etapa 3: Executar o agente com o áudio WAV.
            run_response = agent.run(prompt, audio=audio_input)
            transcribed_text = run_response.content if hasattr(run_response, 'content') else str(run_response)
            
            transcription_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Audio transcribed in {transcription_time_ms}ms. Text: '{transcribed_text}'")
            
            # Etapa 4: Processar o texto transcrito como uma mensagem de conversação.
            if not transcribed_text or not transcribed_text.strip():
                logger.warning("Transcription resulted in empty text. Sending a default reply.")
            return {
                'success': True,
                    'response': "Não consegui entender o que foi dito no áudio. Pode tentar de novo?", 
                    'metadata': {'agent_name': 'Audio Processor (Shortcut)', 'processing_time_ms': transcription_time_ms}
                }
            
            logger.info("Processing transcribed text with conversational agent.")
            text_processing_result = self.process_text_message(transcribed_text, conversation_history, profile_data)
            
            # Adicionar o texto transcrito ao metadata para que o webhook possa usá-lo para atualizar o perfil
            if 'metadata' not in text_processing_result:
                text_processing_result['metadata'] = {}
            text_processing_result['metadata']['transcribed_text'] = transcribed_text
            
            return text_processing_result
            
        except Exception as e:
            logger.error(f"Falha ao processar áudio com Audio Processor: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'response': "Desculpe, a IA encontrou um problema ao processar o áudio. 😥"
            }
        finally:
            # Não há mais arquivo de entrada temporário para remover.
            if temp_out_path and os.path.exists(temp_out_path):
                os.remove(temp_out_path)
                logger.debug(f"Removed temp output audio file: {temp_out_path}")
            
    def extract_profile_info(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Usa o agente Profile Manager para extrair informações de perfil do texto.
        Retorna um dicionário estruturado ou None.
        """
        if not text or not text.strip():
            return None
            
        agent = self.specialist_agents.get('profile_manager')
        if not agent:
            logger.error("Agente 'profile_manager' não encontrado.")
            return None
        
        try:
            # O prompt para este agente é a própria mensagem do usuário.
            # O system prompt do agente já contém todas as instruções.
            run_response = agent.run(text)
            response_content = run_response.content if hasattr(run_response, 'content') else str(run_response)
            
            # A resposta esperada é um JSON puro.
            logger.debug(f"Profile Manager raw response: {response_content}")

            # Limpa a string JSON de possíveis blocos de código markdown.
            clean_json_str = response_content.strip()
            if clean_json_str.startswith("```json"):
                clean_json_str = clean_json_str[7:]
            if clean_json_str.startswith("```"):
                clean_json_str = clean_json_str[3:]
            if clean_json_str.endswith("```"):
                clean_json_str = clean_json_str[:-3]
            clean_json_str = clean_json_str.strip()

            profile_action = json.loads(clean_json_str)
            
            # Validação básica do schema esperado
            if 'action' in profile_action and (profile_action['action'] == 'NONE' or ('data' in profile_action and 'key' in profile_action['data'] and 'value' in profile_action['data'])):
                logger.info(f"Profile Manager extraiu a ação: {profile_action}")
                return profile_action
            else:
                logger.warning(f"Profile Manager retornou JSON em formato inesperado: {clean_json_str}")
                return None
                
        except json.JSONDecodeError:
            logger.error(f"Falha ao decodificar a resposta JSON do Profile Manager. Resposta original: '{response_content}', Após limpeza: '{clean_json_str}'")
            return None
        except Exception as e:
            logger.error(f"Erro ao extrair informações de perfil: {e}", exc_info=True)
            return None
            
    def _process_with_team(self, text_prompt: str, conversation_history: Optional[List[Dict]] = None, audio_data: Optional[bytes] = None, image_data: Optional[List[bytes]] = None) -> Dict[str, Any]:
        start_time = time.time()
        temp_audio_path = None
        temp_image_paths = []
        try:
            full_prompt = self._prepare_text_and_history(text_prompt, conversation_history)
            
            audio_path_for_run = None
            if audio_data:
                fd, temp_audio_path = tempfile.mkstemp(suffix=".ogg")
                with os.fdopen(fd, 'wb') as temp_file:
                    temp_file.write(audio_data)
                audio_path_for_run = [{"filepath": temp_audio_path}]
            
            image_paths_for_run = None
            if image_data:
                image_paths_for_run = []
                for i, img_bytes in enumerate(image_data):
                    # Usar uma extensão de arquivo mais genérica ou detectar o tipo
                    fd, temp_img_path = tempfile.mkstemp(suffix=".jpg") 
                    with os.fdopen(fd, 'wb') as temp_file:
                        temp_file.write(img_bytes)
                    image_paths_for_run.append({"filepath": temp_img_path})
                    temp_image_paths.append(temp_img_path)

            logger.debug(f"Enviando para master_team.run(). Prompt: '{full_prompt[:100]}...', Audio: {audio_path_for_run}, Imagens: {image_paths_for_run}")
            
            team_response_obj = self.team.run(full_prompt, audio=audio_path_for_run, images=image_paths_for_run)
            response_text = team_response_obj.content if hasattr(team_response_obj, 'content') else str(team_response_obj)
            
            processing_time = int((time.time() - start_time) * 1000)
            logger.info(f"Mensagem processada por {self.team.name} em {processing_time}ms.")
            
            metadata = {'agent_name': self.team.name, 'processing_time_ms': processing_time}

            if "[USER_REQUESTS_HUMAN_AGENT]" in response_text:
                metadata['action'] = "REQUEST_HUMAN_AGENT"
            elif "[AI_NEEDS_ASSISTANCE]" in response_text:
                metadata['action'] = "REQUEST_HUMAN_AGENT"
            
            return {
                'success': True,
                'response': response_text,
                'metadata': metadata
            }
        except Exception as e:
            logger.error(f"Falha ao processar mensagem com Agno Master Team: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'response': "Desculpe, a equipe de IA encontrou um problema ao processar sua solicitação. 😥"
            }
        finally:
            if temp_audio_path and os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
                logger.debug(f"Removed temp audio file: {temp_audio_path}")
            for path in temp_image_paths:
                if os.path.exists(path):
                    os.remove(path)
                    logger.debug(f"Removed temp image file: {path}")

    def generate_summary(self, conversation_history: List[Dict]) -> str:
        if not conversation_history:
            return "Não há conversa para resumir."
        
        context = self._build_conversation_context(conversation_history)
        summary_prompt = f"Por favor, gere um resumo conciso desta conversa em um parágrafo:\n\n{context}"
        
        summary_result_dict = self._process_with_team(text_prompt=summary_prompt)
        return summary_result_dict['response'] if summary_result_dict['success'] else "Erro ao gerar resumo."

    def _build_conversation_context(self, conversation_history: List[Dict]) -> str:
        if not conversation_history:
            return ""
        return "\n".join([f"{('Usuário' if msg['sender_type'] == 'user' else 'Assistente')}: {msg.get('message_text', '')}" for msg in conversation_history])

    def process_location_message(self, latitude: float, longitude: float, conversation_history: List[Dict] = None, profile_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Processa uma mensagem de localização, usando o Geolocation Specialist para pedir o destino.
        """
        logger.info(f"Processando mensagem de localização: lat={latitude}, lon={longitude}")
        
        # O texto é um placeholder para acionar o fluxo, mas o contexto principal vem dos dados de localização.
        text_prompt = "O usuário enviou uma localização."
        location_data = {"latitude": latitude, "longitude": longitude}
        
        # Forçar o uso do agente de geolocalização para este tipo de mensagem.
        agent = self.specialist_agents['geolocation_specialist']
        
        start_time = time.time()
        prompt = self._prepare_text_and_history(text_prompt, conversation_history, profile_data, location_data)
        
        run_response = agent.run(prompt)
        response_text = run_response.content if hasattr(run_response, 'content') else str(run_response)
        processing_time_ms = int((time.time() - start_time) * 1000)

        logger.info(f"Localização processada pelo Geolocation Specialist em {processing_time_ms}ms.")
        return {
            'success': True,
            'response': response_text,
            'metadata': {'agent_name': agent.name, 'processing_time_ms': processing_time_ms}
        }
