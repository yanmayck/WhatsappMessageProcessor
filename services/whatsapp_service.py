import requests
import logging
from typing import Dict, Any, Optional
from config import Config
import json

# Imports para descriptografia
import base64
import hashlib
import hmac
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import HKDF
from Crypto.Hash import SHA256

logger = logging.getLogger(__name__)

# Constantes para descriptografia baseadas no código fornecido
# Mapeia messageType (ou um derivado) para o appInfo da HKDF
MEDIA_TYPE_APP_INFO = {
    'image': "WhatsApp Image Keys",
    'video': "WhatsApp Video Keys",
    'audio': "WhatsApp Audio Keys",
    'document': "WhatsApp Document Keys",
    # Adicione outros tipos se necessário, ex: 'sticker'
    'imageMessage': "WhatsApp Image Keys",
    'videoMessage': "WhatsApp Video Keys",
    'audioMessage': "WhatsApp Audio Keys",
    'documentMessage': "WhatsApp Document Keys",
    'stickerMessage': "WhatsApp Sticker Keys", # Exemplo, confirmar string exata
}


def _aes_unpad(s: bytes) -> bytes:
    """Remove PKCS#7 padding."""
    return s[:-s[-1]]

def _aes_decrypt(key: bytes, ciphertext: bytes, iv: bytes) -> bytes:
    """Decrypt using AES CBC."""
    cipher = AES.new(key, AES.MODE_CBC, iv)
    plaintext = cipher.decrypt(ciphertext)
    # Re-habilitando o unpad, pois a validação do MAC é a abordagem correta.
    return _aes_unpad(plaintext)

def _validate_mac(mac_key: bytes, file_data: bytes, mac: bytes) -> bool:
    """Valida o HMAC-SHA256 do arquivo."""
    hasher = hmac.new(mac_key, digestmod=hashlib.sha256)
    hasher.update(file_data)
    # O MAC do WhatsApp é truncado para 10 bytes.
    return hmac.compare_digest(hasher.digest()[:10], mac)

class WhatsAppService:
    def __init__(self):
        self.server_url = Config.EVOLUTION_API_URL
        self.instance_name = Config.EVOLUTION_INSTANCE_NAME
        self.api_key = Config.EVOLUTION_API_KEY
        
        self.headers = {
            'apikey': self.api_key,
            'Content-Type': 'application/json'
        }
        # Headers para download de mídia, podem não precisar de apikey se URL for pré-assinado
        self.media_download_headers = {
            # 'apikey': self.api_key, # A Evolution API pode gerar URLs que não precisam disso
        }
    
    def _get_full_url(self, endpoint: str) -> str:
        """Constructs full URL including schema if not present in server_url."""
        if self.server_url.startswith("http://") or self.server_url.startswith("https://"):
            return f"{self.server_url}{endpoint}"
        # Assumir https como padrão se nenhum esquema for fornecido
        return f"https://{self.server_url}{endpoint}"
    
    def send_text_message(self, to_number: str, text: str, delay: int = 1200, quoted_message_id: Optional[str] = None) -> Optional[str]:
        """Send a text message via the Evolution API."""
        # Endpoint para Evolution API: /message/sendText/{instanceName}
        # Nota: O URL base auto-adiciona http/https se não estiver presente.
        # O exemplo original tinha 'https://' + server_url, o que pode causar https://http://...
        # Ajustado para usar _get_full_url
        endpoint = f"/message/sendText/{self.instance_name}"
        url = self._get_full_url(endpoint)
            
        # Garante que o número de telefone tenha o sufixo correto para a API
        if '@' not in to_number:
            to_number_jid = f"{to_number}@s.whatsapp.net"
        else:
            to_number_jid = to_number
            
        payload = {
            "number": to_number_jid,
            "text": text,
            "options": { 
                "delay": delay, 
                "presence": "composing" 
            },
        }

        if quoted_message_id:
            payload["options"]["quoted"] = {
                 "id": quoted_message_id,
                 "remoteJid": to_number_jid
            }
            # TODO: Validar se a estrutura de citação acima está correta para esta versão da API.

        try:
            logger.debug(f"Sending text message to {to_number}. URL: {url}, Payload: {payload}")
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            
            # Verificar o conteúdo da resposta, mesmo se o status não for de erro
            response_data = {}
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON from response. Status: {response.status_code}, Body: {response.text}")
                # Se não for possível decodificar, lançar o erro original do status
                response.raise_for_status()
                return None # Fallback

            # Checar por status de erro dentro da resposta JSON
            if response.status_code >= 400 or response_data.get('status') == 'error':
                 logger.error(f"Error from Evolution API. Status: {response.status_code}, Response: {response_data}")
                 # Lançar um erro para ser pego pelo bloco except abaixo
                 response.raise_for_status()

            message_id = response_data.get('key', {}).get('id')
            
            if message_id:
                logger.info(f"Text message sent successfully to {to_number}, message_id: {message_id}")
            else:
                logger.warning(f"Text message sent to {to_number}, but no message_id was found in the response: {response_data}")
            return message_id
            
        except requests.exceptions.RequestException as e:
            # Este log agora será mais detalhado, incluindo a resposta da API se disponível
            error_details = str(e)
            if e.response is not None:
                error_details = f"Status: {e.response.status_code}, Response: {e.response.text}"
            logger.error(f"Failed to send text message to {to_number}: {error_details}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending text message to {to_number}: {str(e)}", exc_info=True)
            return None
    
    def download_media(self, media_url: str, media_key_b64: str, original_message_type: str) -> Optional[bytes]:
        """
        Downloads and decrypts media from Evolution API.
        original_message_type é o tipo da mensagem como vem no webhook (ex: 'imageMessage', 'audioMessage')
        """
        if not media_url or not media_key_b64 or not original_message_type:
            logger.error("media_url, media_key_b64, and original_message_type are required for download and decryption.")
            return None

        app_info_str = MEDIA_TYPE_APP_INFO.get(original_message_type)
        if not app_info_str:
            logger.error(f"Unsupported media type for decryption app_info: {original_message_type}")
            return None
    
        app_info_bytes = app_info_str.encode('utf-8')

        try:
            logger.info(f"Downloading .enc file from: {media_url}")
            # Usar self.media_download_headers (que pode ser vazio ou ter apikey)
            enc_response = requests.get(media_url, headers=self.media_download_headers, timeout=30)
            enc_response.raise_for_status()
            encrypted_data = enc_response.content
            logger.info(f"Downloaded .enc file, size: {len(encrypted_data)} bytes")

            media_key_bytes = base64.b64decode(media_key_b64)
            
            # Derivar chaves usando HKDF da biblioteca pycryptodome para maior robustez.
            media_key_expanded = HKDF(
                master=media_key_bytes,
                key_len=80,
                salt=b'',
                hashmod=SHA256,
                context=app_info_bytes
            )

            # Separar as chaves: IV, Chave de Cifra e Chave de MAC
            iv = media_key_expanded[:16]
            cipher_key = media_key_expanded[16:48]
            mac_key = media_key_expanded[48:80]
            
            # Separar o arquivo em conteúdo cifrado e MAC (assinatura)
            file_content_to_decrypt = encrypted_data[:-10]
            mac_from_file = encrypted_data[-10:]

            # Validar o MAC antes de tentar descriptografar
            if not _validate_mac(mac_key, iv + file_content_to_decrypt, mac_from_file):
                error_msg = "MAC validation failed. File may be corrupted or decryption keys are incorrect."
                logger.error(error_msg)
                raise Exception(error_msg)

            logger.info("MAC validation successful.")

            decrypted_bytes = _aes_decrypt(cipher_key, file_content_to_decrypt, iv)
            
            if not decrypted_bytes:
                logger.warning(f"Decryption resulted in empty bytes for media from {media_url}. This may indicate a decryption key/logic issue.")

            logger.info(f"Media decrypted successfully. Decrypted size: {len(decrypted_bytes)}")
            return decrypted_bytes
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download .enc file from {media_url}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Failed to download or decrypt media (URL: {media_url}): {str(e)}", exc_info=True)
            return None
    
    def send_media_message(self, to_number: str, media_type: str, media_url_or_path: str, caption: Optional[str] = None, filename: Optional[str] = None) -> Optional[str]:
        """
        Send a media message (image, audio, video, document) via Evolution API.
        media_type: 'image', 'audio', 'video', 'document'
        media_url_or_path: URL público do arquivo ou caminho local se for upload multipart.
        """
        # TODO: Implementar com base na documentação da Evolution API.
        # Endpoints comuns: /message/sendMedia/{instanceName}, /message/sendImage/{instanceName}, etc.
        # Ou um endpoint genérico que determina o tipo pelo payload.
        # Precisa lidar com envio por URL e envio por upload de arquivo (multipart/form-data).
        
        # Exemplo de estrutura de payload para envio de imagem por URL (ADAPTAR):
        # endpoint = f"/message/sendImage/{self.instance_name}"
        # url = self._get_full_url(endpoint)
        # payload = {
        #     "number": to_number,
        #     "options": {"delay": 1200, "presence": "composing"},
        #     "imageMessage": {
        #         "url": media_url_or_path,
        #         "caption": caption if caption else "",
        #         "mimetype": "image/jpeg" # Ou determinar pelo arquivo/URL
        #     }
        # }
        
        logger.warning(f"send_media_message to {to_number} for type {media_type} is NOT YET FULLY IMPLEMENTED for Evolution API.")
        return None
    
    def mark_message_as_read(self, chat_id: str, message_id: str, participant_jid: Optional[str] = None) -> bool:
        """
        Mark messages as read for a specific chat using Evolution API.
        chat_id: O JID do chat (ex: 55xxxxxxxxxxx@s.whatsapp.net)
        message_id: O ID da mensagem (opcional, se não fornecido, marca todas como lidas)
        participant_jid: O JID do participante (opcional, para grupos)
        """
        # Endpoint da Evolution API: /chat/markasread/{instanceName}
        endpoint = f"/chat/markasread/{self.instance_name}"
        url = self._get_full_url(endpoint)
            
        payload = {
            "id": chat_id, # JID do chat
            # "messageId": message_id, # Opcional, Evolution parece usar 'id' do chat e implicitamente marca mensagens
            # "participant": participant_jid # Opcional
        }
        # A API da Evolution para "markasread" parece simples e foca no chat_id.
        # Não está claro se ela suporta marcar UMA mensagem específica como lida pelo ID da mensagem.
        # O payload de exemplo da documentação da Evolution API geralmente só tem o "id" do chat.
        # Se precisarmos marcar UMA mensagem, a abordagem pode ser diferente.
        # Por agora, vamos implementar como se marcasse o chat como lido.

        try:
            logger.debug(f"Marking chat {chat_id} as read. URL: {url}, Payload: {payload}")
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "success" or response.status_code == 200: # Verificar a resposta de sucesso
                logger.info(f"Chat {chat_id} marked as read successfully.")
                return True
            else:
                logger.warning(f"Marking chat {chat_id} as read might have failed. Response: {data}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to mark chat {chat_id} as read: {e.response.text if e.response else str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error marking chat {chat_id} as read: {str(e)}", exc_info=True)
            return False

    # get_media_info pode não ser necessário se os webhooks da Evolution fornecerem todos os detalhes
    # ou se o download direto da URL + descriptografia for suficiente.
    # Se a Evolution tiver um endpoint para obter metadados de mídia por um ID/key, ele pode ser adicionado aqui.
    # def get_media_info(self, media_key_or_id: str) -> Optional[Dict[str, Any]]:
    #     logger.warning("get_media_info not implemented for Evolution API yet.")
    #     return None
