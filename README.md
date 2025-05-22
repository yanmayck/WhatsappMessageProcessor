# 🤖 WhatsApp AI System com Gemini 2.0

Sistema completo de chatbot WhatsApp com IA multimodal usando Gemini 2.0 Flash Experimental.

## 🚀 Funcionalidades

- **5 Agentes IA Especializados** com Gemini 2.0
- **Processamento Multimodal**: texto, imagem, áudio e documentos
- **Webhook Público** para receber mensagens do WhatsApp
- **Dashboard Web** para monitorar conversas
- **Banco PostgreSQL** para persistir dados
- **Google Cloud Storage** para arquivos de mídia
- **Sistema Personalizável** de prompts e comportamentos

## 📋 Pré-requisitos

- Python 3.11+
- PostgreSQL (ou usar o banco do Replit)
- Conta Google Cloud (para storage)
- API Key do Gemini 2.0
- WhatsApp Business API

## 🔧 Instalação

### 1. Clone o repositório
```bash
git clone [URL_DO_SEU_REPOSITORIO]
cd whatsapp-ai-system
```

### 2. Crie ambiente virtual
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows
```

### 3. Instale dependências
```bash
pip install -r requirements.txt
```

### 4. Configure variáveis de ambiente
Crie arquivo `.env`:
```env
# Gemini AI
GEMINI_API_KEY=sua_chave_gemini_aqui

# WhatsApp API (waho.com ou similar)
WHATSAPP_API_URL=https://api.waho.com
WHATSAPP_API_TOKEN=seu_token_whatsapp
WHATSAPP_PHONE_NUMBER_ID=seu_numero_id

# Webhook
WEBHOOK_VERIFY_TOKEN=seu_token_verificacao

# Google Cloud Storage
GOOGLE_CLOUD_PROJECT_ID=seu_projeto_gcp
GOOGLE_CLOUD_BUCKET_NAME=seu_bucket
GOOGLE_APPLICATION_CREDENTIALS=caminho/para/credentials.json

# Database
DATABASE_URL=postgresql://usuario:senha@localhost/whatsapp_ai

# Flask
SESSION_SECRET=chave_secreta_aleatoria
```

## 🏃‍♂️ Como Executar

### Desenvolvimento
```bash
python main.py
```

### Produção
```bash
gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
```

## 🌐 Configurar Webhook Público

### Opção 1: Ngrok (Recomendado)
```bash
# Instale ngrok: https://ngrok.com/download
ngrok http 5000
```

### Opção 2: Script automático
```bash
python setup_ngrok.py
```

## 🎨 Personalização

### Agentes de IA
Edite `ai_config.py` para personalizar:
- Personalidade dos agentes
- Prompts especializados
- Configurações de resposta
- Estilos de comunicação

### Exemplo de personalização:
```python
AGENT_PERSONALITIES['conversational']['personality'] = """
Você é um assistente super animado! 🎉
Use muitos emojis e seja muito empolgado!
"""
```

## 📊 Dashboard

Acesse `http://localhost:5000` para:
- Monitorar conversas em tempo real
- Ver estatísticas do sistema
- Gerenciar mensagens e respostas
- Analisar performance da IA

## 🗄️ Banco de Dados

### Tabelas principais:
- `conversations` - Conversas do WhatsApp
- `messages` - Mensagens recebidas/enviadas
- `ai_responses` - Respostas geradas pela IA
- `media_files` - Arquivos de mídia

### Migração manual (se necessário):
```sql
-- Execute os comandos SQL em services/database_setup.sql
```

## 🤖 Agentes Especializados

1. **Conversational** 💬 - Chat natural e amigável
2. **Visual Analyzer** 👁️ - Análise detalhada de imagens
3. **Audio Processor** 🎧 - Processamento de áudio e música
4. **Document Expert** 📄 - Análise de documentos e PDFs
5. **Multimodal Fusion** 🔗 - Combinação de múltiplas mídias

## 📱 Configuração WhatsApp

1. Registre webhook: `https://seu-dominio.com/webhook/whatsapp`
2. Configure token de verificação
3. Teste enviando mensagem

## 🔒 Segurança

- ✅ Tokens em variáveis de ambiente
- ✅ Validação de webhook
- ✅ Sanitização de inputs
- ✅ Rate limiting (recomendado)

## 🚨 Solução de Problemas

### Erro de conexão com banco:
```bash
# Verifique variável DATABASE_URL
echo $DATABASE_URL
```

### Erro da API Gemini:
```bash
# Verifique sua chave API
python -c "import os; print('GEMINI_API_KEY' in os.environ)"
```

### Webhook não recebe mensagens:
- Verifique se ngrok está rodando
- Confirme token de verificação
- Teste URL manualmente

## 📚 Estrutura do Projeto

```
whatsapp-ai-system/
├── main.py              # Ponto de entrada
├── app.py               # Configuração Flask
├── config.py            # Configurações gerais
├── ai_config.py         # Configuração da IA
├── models.py            # Modelos do banco
├── setup_ngrok.py       # Script para webhook
├── services/            # Serviços especializados
│   ├── ai_service.py    # IA Gemini 2.0
│   ├── whatsapp_service.py
│   ├── cloud_storage.py
│   └── media_processor.py
├── routes/              # Rotas da API
│   ├── webhook.py       # Webhook WhatsApp
│   └── dashboard.py     # Interface web
├── templates/           # HTML templates
└── static/              # CSS/JS
```

## 🔄 Próximos Passos

1. Configure suas chaves API
2. Teste com mensagens simples
3. Configure processamento de mídia
4. Personalize agentes de IA
5. Deploy em produção

## 📞 Suporte

Para dúvidas e suporte:
- Verifique logs do sistema
- Teste conexões das APIs
- Consulte documentação do Gemini 2.0

---

🎯 **Sistema criado com Flask + Gemini 2.0 + PostgreSQL + Google Cloud**