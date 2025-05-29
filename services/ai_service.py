import os
import json
import logging
import time
from typing import Dict, Any, List, Optional

# Removido: import google.generativeai as genai
# Adicionado: Imports da biblioteca agno
from agno.agent import Agent
from agno.models.google import Gemini
from agno.team import Team # Adicionado import para Team

# Tentativa de importar Parts diretamente da biblioteca google-generativeai
# Isso assume que agno.models.google.Gemini pode lidar com eles.
try:
    # from google.generativeai.types import Part, InlineData # Antigo
    from google.ai.generativelanguage import Part, Blob as InlineData # Novo, google-genai usa Blob
    # Se estiver usando a SDK mais nova "google-genai", o caminho pode ser:
    # from google.ai.generativelanguage import Part, Blob as InlineData (Blob tem mime_type e data)
    # Por enquanto, vamos manter o google.generativeai.types que corresponde à dependência atual
    GOOGLE_GEMINI_PARTS_AVAILABLE = True
except ImportError:
    GOOGLE_GEMINI_PARTS_AVAILABLE = False
    Part = None # type: ignore
    InlineData = None # type: ignore
    # logger.warning("Não foi possível importar Part/InlineData de google.generativeai.types. A multimodalidade pode não funcionar como esperado.") # Comentário antigo
    if logger: # logger pode não estar definido se o import falhar muito cedo
        logger.warning("Não foi possível importar Part/Blob de google.ai.generativelanguage. A multimodalidade pode não funcionar como esperado.")
    else:
        print("ALERTA: Não foi possível importar Part/Blob de google.ai.generativelanguage.")

from config import Config

logger = logging.getLogger(__name__)

# Definição para compatibilidade com a estrutura esperada pela agno para multimodalidade
# (Pode precisar de ajustes com base na documentação exata da agno para parts)
class ImagePart:
    def __init__(self, mime_type: str, data: bytes):
        self.mime_type = mime_type
        self.data = data

    def to_dict(self): # A agno pode esperar um formato específico para 'parts'
        return {"inline_data": {"mime_type": self.mime_type, "data": self.data}}

class AIService:
    def __init__(self):
        # Configuração da API Gemini não é mais feita globalmente com genai.configure
        # A API key é passada diretamente para o modelo Gemini da agno

        self.model_name = Config.GEMINI_API_KEY and "gemini-1.5-flash-latest" # Garante que só define se a key existir
        self.api_key = Config.GEMINI_API_KEY

        if not self.api_key:
            logger.error("GEMINI_API_KEY não configurada. O AIService não funcionará.")
            # Levantar um erro aqui ou ter um estado inoperante claro
            raise ValueError("GEMINI_API_KEY é necessária para AIService.")

        # Prompts personalizados para cada agente especializado (mantidos como estavam)
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

            ⚠️ DETECÇÃO DE SOLICITAÇÃO DE ATENDIMENTO HUMANO E ESCALONAMENTO:
            - Se o usuário expressar claramente o desejo de falar com um atendente humano (usando frases como 'falar com atendente', 'quero um humano', 'suporte humano', 'falar com uma pessoa', 'assistente humano', etc.), sua resposta DEVE indicar que a solicitação foi entendida e será encaminhada. NESTE CASO ESPECÍFICO, e somente neste caso, sua resposta DEVE OBRIGATORIAMENTE incluir o seguinte marcador textual em qualquer lugar da sua mensagem: [USER_REQUESTS_HUMAN_AGENT]
            - Se você, como IA, determinar que não pode ajudar adequadamente, se o usuário parecer excessivamente frustrado, se a conversa entrar em um loop improdutivo, ou se a complexidade da consulta exceder suas capacidades atuais, você DEVE sinalizar a necessidade de assistência humana. NESTE CASO, sua resposta DEVE incluir o seguinte marcador: [AI_NEEDS_ASSISTANCE] e, idealmente, uma breve frase indicando o motivo (ex: "Não consigo processar este tipo de solicitação complexa.", "Percebo que você está frustrado e um colega humano poderá ajudar melhor.").
            - Exemplo de resposta com [USER_REQUESTS_HUMAN_AGENT]: "Entendido! Vou te transferir para um de nossos atendentes. [USER_REQUESTS_HUMAN_AGENT] Por favor, aguarde um momento."
            - Exemplo de resposta com [AI_NEEDS_ASSISTANCE]: "Hmm, essa é uma pergunta um pouco complexa para mim. [AI_NEEDS_ASSISTANCE] Vou pedir ajuda a um colega humano."
            - NÃO use os marcadores para nenhuma outra finalidade.
            - Antes de usar [AI_NEEDS_ASSISTANCE], tente o seu melhor para ajudar. Use este marcador como último recurso.
            
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

        # 1. Criar Agentes Especialistas Individuais
        self.specialist_agents: Dict[str, Agent] = {}
        agent_list_for_team: List[Agent] = []

        for agent_name_key, system_prompt in self.agent_prompts.items():
            descriptive_name = agent_name_key.replace("_", " ").title() + " Specialist"
            # Role pode ser usado pela Team para entender a capacidade do agente
            role_description = f"Especialista em {agent_name_key.replace('_', ' ')}. {system_prompt.splitlines()[0]}"


            gemini_model_for_specialist = Gemini(
                id=self.model_name,
                api_key=self.api_key,
                # System prompt é melhor nas instructions do Agent da Agno
            )
            specialist_agent = Agent(
                name=descriptive_name,
                model=gemini_model_for_specialist,
                instructions=[system_prompt], # Prompt do sistema principal aqui
                role=role_description, 
                # tools=[NotTool()], # Se o agente não tiver outras ferramentas específicas
                expected_output="Uma resposta relevante baseada na sua especialidade e na consulta do usuário.",
                markdown=False 
            )
            self.specialist_agents[agent_name_key] = specialist_agent
            agent_list_for_team.append(specialist_agent)

        # 2. Criar a Equipe de Agentes (Master Agent)
        team_model_instance = Gemini(id=self.model_name, api_key=self.api_key)
        
        team_instructions = [
            "Você é um despachante de IA mestre para um sistema de chatbot do WhatsApp.",
            "Sua tarefa principal é analisar a solicitação do usuário (que pode incluir texto, uma imagem ou um arquivo de áudio) e o histórico da conversa.",
            "Com base na sua análise, encaminhe a tarefa para o agente especialista mais apropriado da sua equipe.",
            "Se a solicitação for complexa e envolver múltiplos tipos de mídia ou exigir uma síntese de diferentes informações, você pode precisar coordenar com o 'Multimodal Fusion Specialist' ou decidir qual especialista é o primário.",
            "Os membros da sua equipe e suas especialidades são:",
            f"- {self.specialist_agents['conversational'].name} (Role: {self.specialist_agents['conversational'].role}): Lida com conversas gerais, saudações, perguntas textuais, serve como fallback e pode solicitar assistência humana através dos marcadores [USER_REQUESTS_HUMAN_AGENT] ou [AI_NEEDS_ASSISTANCE].",
            f"- {self.specialist_agents['visual_analyzer'].name} (Role: {self.specialist_agents['visual_analyzer'].role}): Analisa o conteúdo de imagens.",
            f"- {self.specialist_agents['audio_processor'].name} (Role: {self.specialist_agents['audio_processor'].role}): Transcreve e analisa conteúdo de áudio.",
            f"- {self.specialist_agents['document_expert'].name} (Role: {self.specialist_agents['document_expert'].role}): Extrai informações e analisa documentos (quando o conteúdo do documento é fornecido como texto longo ou imagem).",
            f"- {self.specialist_agents['multimodal_fusion'].name} (Role: {self.specialist_agents['multimodal_fusion'].role}): Lida com solicitações que combinam explicitamente múltiplas mídias ou exigem uma síntese.",
            "REGRA DE ROTEAMENTO IMPORTANTE:",
            "1. Se a entrada contiver uma IMAGEM, encaminhe para o Visual Analyzer Specialist.",
            "2. Se a entrada contiver ÁUDIO, encaminhe para o Audio Processor Specialist.",
            "3. Se a entrada for APENAS TEXTO, encaminhe para o Conversational Specialist.",
            "4. Se a entrada tiver MÚLTIPLOS TIPOS de mídia (ex: texto E imagem), encaminhe para o Multimodal Fusion Specialist.",
            "5. Para análise de documentos (PDFs, etc., que são passados como imagem ou texto extraído), encaminhe para o Document Expert Specialist se a intenção do usuário for claramente sobre extrair informações de um documento.",
            "REGRAS DE ESCALONAMENTO:",
            " - Se a resposta do agente especialista contiver o marcador [USER_REQUESTS_HUMAN_AGENT] ou [AI_NEEDS_ASSISTANCE], sua resposta final DEVE preservar este marcador e o texto original da resposta do especialista.",
            "Antes de encaminhar, você pode adicionar um breve preâmbulo à consulta se ajudar o especialista a entender o contexto total (especialmente o histórico da conversa).",
            "A saída final deve ser a resposta do agente especialista escolhido, incluindo quaisquer marcadores de escalonamento."
            # "Você pode habilitar o show_reasoning=True na sua chamada run() se precisar depurar seu processo de decisão."
        ]

        self.master_team = Team(
            name="WhatsAppMasterAITeam",
            members=agent_list_for_team,
            model=team_model_instance,
            instructions=team_instructions,
            mode="route", # Começar com 'route' para simplicidade com base nas instruções.
                         # 'coordinate' pode ser explorado se 'route' não for suficiente.
            # Para 'coordinate', success_criteria, max_iterations, etc. podem ser necessários.
            # show_tool_calls=True, # Útil para depurar qual agente especialista é chamado pela equipe
            # stream_intermediate_steps=True, # Para depurar o processo de decisão da equipe
        )
        logger.info("AIService inicializado com Master Team e agentes especialistas.")

    def _prepare_input_for_team(self, main_content_parts: List[Any], conversation_history: List[Dict] = None) -> List[Any]:
        """Prepara a lista de conteúdo para a equipe, incluindo o histórico da conversa.
           O conteúdo pode ser uma mistura de strings (texto) e bytes (para imagens/áudio).
        """
        # Part é usado para o histórico, então o check ainda é relevante.
        if not GOOGLE_GEMINI_PARTS_AVAILABLE or not Part:
             raise RuntimeError("Google Gemini Parts (Part) não estão disponíveis para formatar o histórico.")

        final_input_for_team: List[Any] = []
        formatted_history = self._build_conversation_context(conversation_history or [])
        
        if formatted_history and formatted_history != "Nenhum histórico de conversa ainda.":
            # Agno/Gemini models usually expect history formatted clearly.
            # Sending it as a distinct text item before the main content.
            final_input_for_team.append(f"Contexto da conversa anterior:\n{formatted_history}")
            # Ou, se for necessário que seja um Part object:
            # final_input_for_team.append(Part(text=f"Contexto da conversa anterior:\n{formatted_history}"))
        
        # Adiciona as partes do conteúdo principal (texto, imagem, áudio)
        # main_content_parts já deve ser uma lista de strings e bytes.
        if isinstance(main_content_parts, list):
            final_input_for_team.extend(main_content_parts)
        # Caso main_content_parts seja um único item (string ou bytes), coloque-o numa lista
        # Esta situação deve ser menos comum com as refatorações anteriores que já preparam listas.
        elif isinstance(main_content_parts, (str, bytes)):
             final_input_for_team.append(main_content_parts)
        # Se por acaso ainda vier um Part (ex: de process_text_message se não for atualizado)
        elif Part and isinstance(main_content_parts, Part):
            final_input_for_team.append(main_content_parts) # Ou extrair .text/.data se necessário

        if not final_input_for_team:
            logger.warning("Nenhuma parte de conteúdo principal para enviar à equipe, enviando prompt padrão.")
            final_input_for_team.append("[Usuário não forneceu entrada explícita, por favor, responda apropriadamente ou peça por mais informações]")

        return final_input_for_team

    def _process_with_team(self, main_content_items: List[Any], conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Função helper para processar qualquer tipo de mensagem com a master_team."""
        start_time = time.time()
        escalation_type = None
        escalation_reason_detail = "" # Para capturar a justificativa da IA, se houver

        try:
            if not self.api_key: # Adicionado para checar se a API key está disponível
                return {'success': False, 'error': "GEMINI_API_KEY não configurada.", 'response': "Erro de configuração da IA."}

            input_for_team = self._prepare_input_for_team(main_content_items, conversation_history)
            
            logger.debug(f"Enviando para master_team.run() o seguinte input: {input_for_team}")
            
            team_response_obj = self.master_team.run(input_for_team)
            
            response_text = team_response_obj.content if hasattr(team_response_obj, 'content') else str(team_response_obj)
            
            # Verificar marcadores de escalonamento
            if "[USER_REQUESTS_HUMAN_AGENT]" in response_text:
                escalation_type = "user_explicit_request"
                # Tenta extrair um motivo se o bot adicionou algo após o marcador, embora o prompt diga para não fazer
                # response_text = response_text.replace("[USER_REQUESTS_HUMAN_AGENT]", "").strip() # Remover o marcador da resposta final ao usuário, se desejado
            elif "[AI_NEEDS_ASSISTANCE]" in response_text:
                escalation_type = "ai_needs_assistance"
                # Tenta extrair um motivo. Ex: "[AI_NEEDS_ASSISTANCE] Não consigo processar este tipo de solicitação complexa."
                # Isso é um pouco rudimentar; idealmente, a IA retornaria isso de forma estruturada.
                # Mas, por enquanto, podemos tentar pegar o texto após o marcador.
                parts = response_text.split("[AI_NEEDS_ASSISTANCE]", 1)
                if len(parts) > 1:
                    escalation_reason_detail = parts[1].strip()
                # response_text = response_text.replace("[AI_NEEDS_ASSISTANCE]", "").strip() # Remover o marcador, se desejado


            agent_name_reported = self.master_team.name 

            processing_time = int((time.time() - start_time) * 1000)
            result = {
                'success': True,
                'response': response_text, # A resposta ainda pode conter os marcadores para a lógica de webhook decidir o que fazer
                'model_used': self.model_name, 
                'agent_name': agent_name_reported,
                'processing_time': processing_time,
                'content_type': 'text',
                'escalation_type': escalation_type, # Novo campo
                'escalation_reason_detail': escalation_reason_detail if escalation_type else None # Novo campo
            }
            logger.info(f"Mensagem processada por {agent_name_reported} (Agno Team) em {processing_time}ms. Escalonamento: {escalation_type}. Resposta: {response_text[:100]}...")
            return result

        except Exception as e:
            logger.error(f"Falha ao processar mensagem com Agno Master Team: {str(e)}", exc_info=True)
            # Tenta obter mais detalhes se for um erro específico da API do Google/Gemini
            # if hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'):
            #     logger.error(f"Prompt Feedback: {e.response.prompt_feedback}")
            # if hasattr(e, 'message'): # Alguns erros da API Google vêm com 'message'
            #    logger.error(f"Detalhe do erro API: {e.message}")

            return {
                'success': False,
                'error': str(e),
                'response': "Desculpe, a equipe de IA encontrou um problema ao processar sua solicitação. 😥",
                'processing_time': int((time.time() - start_time) * 1000)
            }

    def process_text_message(self, text: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        if not GOOGLE_GEMINI_PARTS_AVAILABLE or not Part:
            return {'success': False, 'error': "Google Gemini Parts não disponíveis.", 'response': "Erro de configuração da IA."}
        main_content_parts = [text]
        return self._process_with_team(main_content_parts, conversation_history)
    
    def process_image_message(self, image_data: bytes, text_prompt: str = None, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        # GOOGLE_GEMINI_PARTS_AVAILABLE check might still be relevant if we fall back to manual Part creation, 
        # but ideally agno handles this. For now, let's assume agno's model handles byte inputs.
        # if not GOOGLE_GEMINI_PARTS_AVAILABLE or not Part or not InlineData:
        #      return {'success': False, 'error': "Google Gemini Parts não disponíveis para imagem.", 'response': "Erro de configuração da IA."}

        main_parts_for_image_request = []
        image_accompanying_text = "Analise esta imagem."
        if text_prompt:
            image_accompanying_text = f"Sobre esta imagem: {text_prompt}"
        main_parts_for_image_request.append(image_accompanying_text) # Pass text directly

        # Pass image_data (bytes) directly. Agno should handle converting this for Gemini.
        # We might need to provide mime_type if agno doesn't infer it or if Gemini needs it explicitly via agno.
        # For now, let's try with just bytes, as agno aims for simplicity.
        main_parts_for_image_request.append(image_data)

        # Old way: manual Part creation
        # import PIL.Image
        # import io
        # try:
        #     image = PIL.Image.open(io.BytesIO(image_data))
        #     mime_type = PIL.Image.MIME.get(image.format)
        #     if not mime_type:
        #         if image.format.lower() in ['jpeg', 'jpg']: mime_type = 'image/jpeg'
        #         elif image.format.lower() == 'png': mime_type = 'image/png'
        #         # ... other mime types
        #         else:
        #             logger.warning(f"Mime_type não determinado para imagem: {image.format}. Usando application/octet-stream.")
        #             mime_type = 'application/octet-stream'
        #     main_parts_for_image_request.append(Part(inline_data=InlineData(mime_type=mime_type, data=image_data)))
        # except Exception as img_ex:
        #     logger.error(f"Erro ao processar dados da imagem com PIL para Agno Team: {img_ex}")
        #     return {'success': False, 'error': f"Erro de processamento de imagem: {img_ex}", 'response': "Não foi possível processar a imagem fornecida."}
            
        return self._process_with_team(main_parts_for_image_request, conversation_history)

    def process_audio_message(self, audio_data: bytes, conversation_history: List[Dict] = None, mime_type: str = "audio/opus") -> Dict[str, Any]:
        # if not GOOGLE_GEMINI_PARTS_AVAILABLE or not Part or not InlineData:
        #     return {'success': False, 'error': "Google Gemini Parts não disponíveis para áudio.", 'response': "Erro de configuração da IA."}

        main_parts_for_audio_request = []
        audio_accompanying_text = "Analise este áudio e transcreva-o se for fala, ou descreva-o se for música/som."
        main_parts_for_audio_request.append(audio_accompanying_text) # Pass text directly
        
        # Pass audio_data (bytes) directly. Agno should handle this.
        # The mime_type might be passed to agno's model if it has a specific parameter, or packaged with the data.
        # For now, relying on agno's intelligence or default handling.
        # If specific mime_type handling is needed, agno docs should clarify how to pass it with raw bytes.
        main_parts_for_audio_request.append(audio_data)
        # We might need to pass mime_type too, e.g. by making the item a tuple or dict: (audio_data, mime_type) or {"data": audio_data, "mime_type": mime_type}
        # This depends on how agno.models.google.Gemini expects raw bytes with mime types.
        # The agno Gemini audio examples seem to just pass bytes or file path.

        # Old way:
        # main_parts_for_audio_request.append(Part(inline_data=InlineData(mime_type=mime_type, data=audio_data)))
        
        return self._process_with_team(main_parts_for_audio_request, conversation_history)
            
    def process_multimodal_message(self, content_items: List[Dict], conversation_history: List[Dict] = None) -> Dict[str, Any]:
        # if not GOOGLE_GEMINI_PARTS_AVAILABLE or not Part or not InlineData:
        #     return {'success': False, 'error': "Google Gemini Parts não disponíveis para multimodal.", 'response': "Erro de configuração da IA."}

        parts_for_multimodal_request: List[Any] = [] # Can now contain str and bytes

        for item in content_items:
            item_type = item.get('type')
            item_data = item.get('data')
            item_text_prompt = item.get('text_prompt')

            if item_text_prompt:
                parts_for_multimodal_request.append(item_text_prompt)

            if item_type == 'text' and isinstance(item_data, str):
                parts_for_multimodal_request.append(item_data)
            elif item_type == 'image' and isinstance(item_data, bytes):
                # Pass image bytes directly. Agno should handle it.
                # Mime type detection via PIL might be needed if agno requires it separately for raw bytes.
                parts_for_multimodal_request.append(item_data)
                # Old way:
                # import PIL.Image
                # import io
                # try:
                #     image = PIL.Image.open(io.BytesIO(item_data))
                #     mime_type = PIL.Image.MIME.get(image.format) or 'application/octet-stream'
                #     if mime_type == 'application/octet-stream': logger.warning(f"Usando mime_type genérico para imagem {image.format} em multimodal.")
                #     parts_for_multimodal_request.append(Part(inline_data=InlineData(mime_type=mime_type, data=item_data)))
                # except Exception as img_ex:
                #     logger.error(f"Erro ao processar imagem em multimodal para Agno Team: {img_ex}")
                #     parts_for_multimodal_request.append(f"[Erro ao processar imagem: {img_ex}]") # Pass error as text
            elif item_type == 'audio' and isinstance(item_data, bytes):
                # Pass audio bytes directly. Agno should handle it.
                # audio_mime_type = item.get('mime_type', 'audio/opus') # This might be needed if agno expects it.
                parts_for_multimodal_request.append(item_data)
                # Old way:
                # parts_for_multimodal_request.append(Part(inline_data=InlineData(mime_type=audio_mime_type, data=item_data)))
            else:
                logger.warning(f"Item multimodal desconhecido ou malformado ignorado: tipo {item_type}")

        if not parts_for_multimodal_request:
             logger.warning("Nenhum item processável em process_multimodal_message.")
             return {'success': False, 'error': "Nenhum conteúdo multimodal válido fornecido.", 'response': "Não entendi sua mensagem com múltiplos tipos de mídia."}

        return self._process_with_team(parts_for_multimodal_request, conversation_history)

    def _build_conversation_context(self, conversation_history: List[Dict]) -> str:
        """Builds a formatted string from conversation history."""
        if not conversation_history:
            return "Nenhum histórico de conversa ainda."
        
        context_parts = []
        for entry in conversation_history:
            speaker = "Usuário" if entry.get('sender_type') == 'user' else "Assistente"
            message = entry.get('message_text', entry.get('ai_response', '')) # Adaptar conforme a estrutura do seu histórico
            
            # Tenta lidar com mensagens que podem ser objetos complexos (ex: da Agno)
            if not isinstance(message, str):
                if hasattr(message, 'content'): # Comum em respostas da Agno
                    message = message.content
                elif isinstance(message, dict) and 'text' in message: # Se for um dict com 'text'
                    message = message['text']
                else:
                    message = str(message) # Fallback para string

            context_parts.append(f"{speaker}: {message}")
        
        return "\n".join(context_parts)
    
    def generate_summary(self, conversation_history: List[Dict]) -> str:
        """Genera um resumo da conversa usando a MasterTeam com um prompt específico."""
        if not GOOGLE_GEMINI_PARTS_AVAILABLE or not Part: # Adicionado para checar Part
            logger.error("Google Gemini Parts não disponíveis para gerar resumo.")
            return "Erro de configuração da IA ao tentar gerar resumo."
        if not self.api_key: # Adicionado para checar API Key
             logger.error("GEMINI_API_KEY não configurada para gerar resumo.")
             return "Erro de configuração da IA (sem API key) ao tentar gerar resumo."


        start_time = time.time()
        try:
            if not conversation_history:
                return "Não há conversa para resumir."

            context = self._build_conversation_context(conversation_history)
            # Instrução para a equipe focar na tarefa de resumo
            # O prompt original do agente conversacional é muito genérico para um bom resumo direto pela equipe.
            # Precisamos ser explícitos sobre a tarefa de resumo para a equipe.
            summary_prompt_for_team = [
                Part(text=f"Você é o {self.master_team.name}. Sua tarefa atual é APENAS resumir o seguinte histórico de conversa. Use o 'Conversational Specialist' ou o 'Multimodal Fusion Specialist' para esta tarefa de resumo, se necessário. O histórico é:

{context}

Por favor, gere um resumo conciso desta conversa em um parágrafo.")
            ]
            
            # Usamos _process_with_team que já lida com a chamada à equipe
            # Passamos None para conversation_history aqui porque o histórico já está no prompt
            summary_result_dict = self._process_with_team(summary_prompt_for_team, conversation_history=None) 

            if summary_result_dict['success']:
                summary = summary_result_dict['response']
                processing_time = int((time.time() - start_time) * 1000) # Recalcular ou pegar do dict
                logger.info(f"Resumo gerado pela Agno Team em {processing_time}ms")
                return summary
            else:
                logger.error(f"Falha ao gerar resumo com Agno Team: {summary_result_dict.get('error')}")
                return "Erro ao gerar resumo com a equipe de IA."

        except Exception as e:
            logger.error(f"Exceção ao gerar resumo com Agno Team: {e}", exc_info=True)
            return "Erro excepcional ao gerar resumo."
