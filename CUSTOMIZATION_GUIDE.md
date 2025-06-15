# Guia de Configuração e Deploy da IA para WhatsApp

Este guia é um tutorial completo para configurar, personalizar e implantar seu assistente de IA. Vamos passar por cada etapa, desde a obtenção de chaves de API até a configuração final para produção no Google Cloud Run.

---

## Passo 1: Configuração Essencial com o Arquivo `.env`

Toda a configuração da sua aplicação é gerenciada por **variáveis de ambiente**. Para o desenvolvimento local, você usará um arquivo chamado `.env` na raiz do projeto. Este arquivo centraliza todas as suas senhas, chaves de API e personalizações.

**IMPORTANTE:** O arquivo `.env` contém informações sensíveis e **nunca** deve ser enviado para um repositório Git. Nós já configuramos o arquivo `.gitignore` para ignorá-lo.

### Como Criar seu Arquivo `.env`

1.  Crie um novo arquivo na raiz do seu projeto chamado `.env`.
2.  Copie e cole o conteúdo abaixo neste novo arquivo. Este é o seu template de configuração.

```env
# =================================================================
# Arquivo de Variáveis de Ambiente
# Preencha com seus próprios valores.
# =================================================================

# --- Configuração Essencial do Flask ---
SECRET_KEY="a-very-long-and-random-secret-key"

# --- Conexão com Banco de Dados ---
DATABASE_URL="sqlite:///whatsapp_ai.db"

# --- Configurações da Evolution API (Seu WhatsApp) ---
EVOLUTION_API_URL="http://localhost:8080"
EVOLUTION_API_KEY=""
EVOLUTION_INSTANCE_NAME="my-instance"

# --- Configuração do Webhook ---
WEBHOOK_VERIFY_TOKEN="your-webhook-verify-token"

# --- Chaves de API de Serviços Google ---
GEMINI_API_KEY=""
GOOGLE_MAPS_API_KEY=""

# --- Google Cloud Storage (Opcional, para salvar mídias) ---
GOOGLE_CLOUD_PROJECT_ID=""
GOOGLE_CLOUD_BUCKET_NAME=""

# --- Configurações de Negócio ---
COMPANY_DEFAULT_ADDRESS="Avenida Paulista, 1000, São Paulo, SP, Brasil"
KNOWLEDGE_BASE_FILE="knowledge_base.txt"
IGNORE_LIST_NUMBERS="5511999998888"

# --- Personalização da IA ---
AI_NAME="Assistente Virtual"
AI_PERSONALITY_DESCRIPTION="Amigável, prestativa e um pouco informal. Use emojis com moderação para criar uma conexão com o cliente. Evite jargões técnicos."
AI_BUSINESS_CONTEXT="Somos uma empresa que vende produtos e serviços de alta qualidade."
AI_RESPONSE_STYLE="Responda em parágrafos curtos para facilitar a leitura no celular. Use listas de tópicos para detalhar informações."

# --- Configuração de Notificações (Pushover, opcional) ---
PUSHOVER_APP_TOKEN=""
DEFAULT_PUSHOVER_USER_KEY=""

# --- Configurações Avançadas ---
LOGGING_LEVEL="INFO"
ENABLE_ASYNC_PROCESSING="True"
MAX_PROCESSING_THREADS="5"
INTERNAL_TASK_TOKEN="a-secret-internal-task-token"

# --- Vector Database (Opcional, para RAG avançado) ---
VECTOR_DB_ENABLED="False"
VECTOR_DB_PROVIDER="chroma" 
VECTOR_DB_URL=""
VECTOR_DB_API_KEY=""
VECTOR_DB_ENVIRONMENT=""
VECTOR_DB_INDEX_NAME="company-info"

# --- Modelo de Embedding (Opcional, para RAG avançado) ---
EMBEDDING_MODEL_PROVIDER="google"
EMBEDDING_MODEL_NAME="textembedding-gecko@003"

# --- Extensões de Arquivo Permitidas ---
ALLOWED_EXTENSIONS_IMAGE=".jpg,.jpeg,.png,.gif,.webp"
ALLOWED_EXTENSIONS_AUDIO=".mp3,.wav,.ogg,.m4a,.opus"
ALLOWED_EXTENSIONS_VIDEO=".mp4,.avi,.mov,.webm"
ALLOWED_EXTENSIONS_DOCUMENT=".pdf,.doc,.docx,.txt"

# --- Variáveis Opcionais de Desenvolvimento ---
# Estas variáveis são úteis apenas para o desenvolvimento local e não devem ser configuradas em produção.
# Elas ativam o modo de depuração do Flask, que reinicia o servidor automaticamente a cada mudança no código
# e mostra erros detalhados no navegador.
# FLASK_DEBUG=True
# FLASK_ENV=development
```

---

## Passo 2: Obtendo suas Chaves de API e Credenciais

Agora, vamos preencher as variáveis no seu arquivo `.env`.

### Configuração da Evolution API (Obrigatório)

Estas são as credenciais para conectar o sistema à sua API do WhatsApp.
*   `EVOLUTION_API_URL`: A URL da sua instância da Evolution API (ex: `http://localhost:8080`).
*   `EVOLUTION_API_KEY`: A chave de API global (`GLOBAL_API_KEY`) da sua Evolution API.
*   `EVOLUTION_INSTANCE_NAME`: O nome da instância que você criou na Evolution API para este bot.

### Google Gemini API Key (Obrigatório)

Esta é a chave para o cérebro da IA.
1.  Acesse o **Google AI Studio**: [https://aistudio.google.com/](https://aistudio.google.com/)
2.  Faça login com sua conta Google.
3.  Clique em **"Get API key"** (Obter chave de API) no menu à esquerda.
4.  Clique em **"Create API key in new project"**.
5.  Copie a chave gerada e cole no campo `GEMINI_API_KEY` do seu arquivo `.env`.

### Meta/WhatsApp Webhook (Obrigatório)

*   `WEBHOOK_VERIFY_TOKEN`: Este é um token que **você cria**. Pode ser qualquer texto secreto (ex: `um-token-bem-seguro-12345`). Você vai inseri-lo aqui no `.env` e também no painel de desenvolvedores da Meta quando for configurar o webhook do seu número de WhatsApp.

### Google Maps API Key (Opcional, para cálculo de frete)

Necessário para a função de cálculo de distância e frete.
1.  Acesse o **Google Cloud Console**: [https://console.cloud.google.com/](https://console.cloud.google.com/)
2.  Crie um novo projeto ou selecione um existente.
3.  No menu de navegação, vá para **"APIs & Services" > "Library"**.
4.  Pesquise e ative as seguintes APIs:
    *   **Geocoding API**
    *   **Directions API**
5.  Vá para **"APIs & Services" > "Credentials"**.
6.  Clique em **"+ CREATE CREDENTIALS" > "API key"**.
7.  Copie a chave gerada e cole no campo `GOOGLE_MAPS_API_KEY`.
    *   **Importante:** É altamente recomendável restringir sua chave de API para evitar uso indevido.

### Google Cloud Storage (Opcional, para salvar mídias)

Use para armazenar arquivos de mídia (áudios, imagens) na nuvem.
1.  No Google Cloud Console, selecione seu projeto.
2.  Vá para **"Cloud Storage" > "Buckets"**.
3.  Clique em **"CREATE BUCKET"** e siga os passos. Escolha um nome único.
4.  Após criar o bucket, você precisará do:
    *   `GOOGLE_CLOUD_PROJECT_ID`: O ID do seu projeto, visível no painel do Google Cloud.
    *   `GOOGLE_CLOUD_BUCKET_NAME`: O nome do bucket que você acabou de criar.

### URL do Banco de Dados de Produção (Google Cloud SQL)

Para produção, você precisará de um banco de dados robusto. Existem dois métodos para conectar seu Cloud Run ao Cloud SQL: via **IP Público** (mais simples) ou via **Cloud SQL Auth Proxy** (mais seguro e recomendado pelo Google).

#### Método 1: Conexão via IP Público (Simples, mas menos seguro)

Neste método, você expõe seu banco de dados à internet e se conecta a ele por um endereço de IP.

1.  **Crie a instância** no Google Cloud SQL (PostgreSQL).
2.  **Defina a senha** do usuário `postgres`.
3.  Na aba **"CONNECTIONS"** da sua instância, habilite o **"Public IP"**.
4.  Em **"Authorized networks"**, adicione `0.0.0.0/0` para permitir conexões de qualquer lugar. **Isso não é o ideal para segurança!**
5.  Monte a URL no formato: `postgresql://postgres:SUA_SENHA@IP_PUBLICO:5432/postgres`
6.  Use essa URL na sua variável `DATABASE_URL`.

---

#### Método 2: Conexão via Cloud SQL Auth Proxy (Recomendado e mais seguro)

Este é o método que você já está usando e é a melhor prática. Ele cria um túnel seguro e privado entre o Cloud Run e o Cloud SQL, sem expor seu banco de dados.

**Passo A: Crie a Instância e Encontre as Credenciais**

1.  **Acesse o Google Cloud SQL** e clique em **"CREATE INSTANCE"**.
2.  Escolha **PostgreSQL**, defina um **ID de instância** (ex: `whatsapp-bot-db`) e uma **senha** para o usuário `postgres`.
3.  **Não é necessário habilitar o IP Público** para este método.
4.  Você precisará das seguintes informações:
    *   **Nome do Projeto (Project ID):** `watsapp-ia`
    *   **Região:** `southamerica-east1`
    *   **ID da Instância:** `whatsapp-ia-ideallys`
    *   **Usuário do Banco:** `yan`
    *   **Senha do Banco:** `cabecadepicles`
    *   **Nome do Banco:** `whatsapp-ia-ideallys`

**Passo B: Monte a URL de Conexão Segura**

A URL usa um formato especial que informa à aplicação para usar o túnel seguro.
*   **Formato:** `postgresql+psycopg2://<USUARIO>:<SENHA>@/<NOME_DO_BANCO>?host=/cloudsql/<PROJETO>:<REGIAO>:<INSTANCIA>`
*   **Seu Exemplo (Correto):** `postgresql+psycopg2://yan:cabecadepicles@/whatsapp-ia-ideallys?host=/cloudsql/watsapp-ia:southamerica-east1:whatsapp-ia-ideallys`
    *   **Nota:** O `@localhost` ou `@` depois da senha é opcional e pode ser omitido, como no seu exemplo.

**Passo C: Configure a Conexão no Cloud Run (O Passo Crucial)**

Para que a URL acima funcione, você precisa "ligar" o túnel.

1.  Ao criar ou editar seu serviço no Google Cloud Run, vá para a aba **"CONNECTIONS"**.
2.  Na seção **Cloud SQL**, clique em **"ADD CONNECTION"**.
3.  Selecione a sua instância do Cloud SQL na lista (ex: `watsapp-ia:southamerica-east1:whatsapp-ia-ideallys`).
4.  Salve a configuração.

Agora, quando você fizer o deploy e passar a sua `DATABASE_URL` especial, o Cloud Run saberá exatamente como se conectar ao seu banco de dados de forma segura.

---

## Passo 3: Personalizando o Comportamento da IA

Você pode moldar a personalidade e o contexto do seu assistente diretamente no arquivo `.env`.

*   `AI_NAME`: O nome do seu assistente (ex: "Sofia", "Assistente ACME").
*   `AI_BUSINESS_CONTEXT`: Uma descrição clara do seu negócio. Isso dá à IA o contexto sobre quem ela representa.
*   `AI_PERSONALITY_DESCRIPTION`: Define a personalidade e o tom da IA (ex: "Amigável e prestativo, use emojis").
*   `AI_RESPONSE_STYLE`: Regras sobre o formato das respostas (ex: "Responda em parágrafos curtos").

Para personalizações mais profundas (regras de negócio complexas, etc.), você pode editar os prompts diretamente no arquivo `services/ai_service.py`.

---

## Passo 4: Base de Conhecimento (RAG)

A IA pode responder perguntas com base em um arquivo de texto.

1.  O arquivo `.env` já aponta para `KNOWLEDGE_BASE_FILE="knowledge_base.txt"`.
2.  Abra o arquivo `knowledge_base.txt` e adicione informações sobre sua empresa, produtos, políticas, etc.
3.  Separe os tópicos com linhas em branco para melhor organização. A IA usará este conteúdo para responder perguntas de forma precisa.

---

## Passo 5: Implantação no Google Cloud Run

O Google Cloud Run é uma plataforma excelente e de baixo custo para hospedar esta aplicação. A configuração que fizemos com variáveis de ambiente torna o processo muito simples.

Você **não** envia seu arquivo `.env` para a nuvem. Em vez disso, você configura as variáveis diretamente no serviço do Cloud Run.

### Como Fazer o Deploy:

Existem duas maneiras de configurar suas variáveis de ambiente no Cloud Run: pela interface gráfica (mais fácil para começar) ou diretamente pela linha de comando (ótimo para automação).

#### Método 1: Via Interface Gráfica (Recomendado para iniciantes)

1.  **Use o deploy básico:** Execute o comando `gcloud run deploy` no seu terminal, na pasta do projeto. Substitua `meu-bot-whatsapp` pelo nome do seu serviço e `sua-regiao` pela sua região (ex: `us-central1`).
    ```sh
    gcloud run deploy meu-bot-whatsapp --source . --region sua-regiao --allow-unauthenticated
    ```
2.  **Acesse o painel:** Após o deploy, vá para o painel do Google Cloud Run.
3.  **Configure as variáveis:** Navegue até o seu serviço e clique em **"EDIT & DEPLOY NEW REVISION"**. Vá para a aba **"VARIABLES & SECRETS"**.
4.  **Adicione as variáveis:** Aqui, você irá recriar cada uma das variáveis do seu arquivo `.env` local. Para cada linha do seu `.env`, clique em **"ADD VARIABLE"** e insira o nome e o valor.
5.  **Salve:** Clique em "DEPLOY".

#### Método 2: Via Linha de Comando (Avançado)

Como você descobriu, é possível fornecer todas as variáveis de ambiente diretamente no comando de deploy. Isso é muito poderoso, pois garante que a aplicação e sua configuração sejam implantadas em uma única etapa.

O comando usa a flag `--set-env-vars`. O truque é fornecer todas as variáveis em uma única string, separadas por vírgulas.

**Atenção:** Nos exemplos abaixo, você só precisa substituir os valores de exemplo (`seu-valor-aqui`) pelos seus próprios valores do arquivo `.env`.

**Exemplo para PowerShell (Windows):**

Este script é a forma mais limpa. Ele cria uma lista com suas variáveis e depois as junta no formato que o Google Cloud precisa. Basta editar os valores na lista.

```powershell
# Edite os valores aqui. Use aspas se o valor tiver espaços.
$envVars = @(
  # --- Configuração Essencial ---
  "SECRET_KEY=YoWyRnc6_4U5uudTPYELdFmM2lrRDarr7BTKq13ug6k",
  "DATABASE_URL=postgresql://yan:cabecadepicles@localhost/whatsapp_prod?host=/cloudsql/watsapp-ia:southamerica-east1:whatsapp-ia-ideallys
",

  # --- Evolution API ---
  "EVOLUTION_API_URL=http://evolution.gerenciamentopetshop.top:8080",
  "EVOLUTION_API_KEY=A3AEE32A5C43-4C1A-A276-79B139761C23",
  "EVOLUTION_INSTANCE_NAME=ideallys_teste_debug",
  "WEBHOOK_VERIFY_TOKEN=seu-token-secreto-para-webhook",
  
  # --- Serviços Google ---
  "GEMINI_API_KEY=AIzaSyCEjNrRzH-0k2zxNegUSiiRsAITaY3iGqk",
  "GOOGLE_MAPS_API_KEY=AIzaSyCimlrKzXFepwQ2VpG2VaPAVy-sdruYWDw",
  "GOOGLE_CLOUD_PROJECT_ID=watsapp-ia",
  "GOOGLE_CLOUD_BUCKET_NAME=whatsapp-media-bucket-ideallys",

  # --- Configurações de Negócio ---
  "COMPANY_DEFAULT_ADDRESS='Rua 17 Q 11 lt 30-B, JARDIM JUSARA, CALDAS NOVAS, GOIAS'",
  "KNOWLEDGE_BASE_FILE=knowledge_base.txt",
  "IGNORE_LIST_NUMBERS=5511999998888,15551234567",

  # --- Personalização da IA ---
  AI_NAME = "Ideallys Assistente"
  AI_PERSONALITY_DESCRIPTION = "Atencioso, eficiente e sempre pronto para ajudar com soluções digitais inteligentes."
  AI_BUSINESS_CONTEXT = (
    "A Ideallys é uma empresa especializada em criação de sites, marketing digital (tráfego pago e orgânico) "
    "e atendimento automatizado via inteligência artificial multimodal. "
    "Nosso principal produto é uma IA que entende texto, áudio, imagem e vídeo, personaliza o atendimento para cada cliente "
    "e armazena o histórico de mensagens. Em breve, ofereceremos planos com relatórios, insights sobre produtos e demandas regionais."
  ),
  "AI_RESPONSE_STYLE='Responda em parágrafos curtos.'",

  # --- Notificações (Pushover) ---
  "PUSHOVER_APP_TOKEN=seu-pushover-app-token",
  "DEFAULT_PUSHOVER_USER_KEY=sua-pushover-user-key",

  # --- Configurações Avançadas ---
  "LOGGING_LEVEL=INFO",
  "ENABLE_ASYNC_PROCESSING=True",
  "MAX_PROCESSING_THREADS=5",
  "INTERNAL_TASK_TOKEN=um-token-interno-super-secreto",

  # --- Vector Database ---
  "VECTOR_DB_ENABLED=False",
  "VECTOR_DB_PROVIDER=chroma",
  "VECTOR_DB_URL=",
  "VECTOR_DB_API_KEY=",
  "VECTOR_DB_ENVIRONMENT=",
  "VECTOR_DB_INDEX_NAME=company-info",
  
  # --- Modelo de Embedding ---
  "EMBEDDING_MODEL_PROVIDER=google",
  "EMBEDDING_MODEL_NAME=textembedding-gecko@003",

  # --- Extensões de Arquivo Permitidas ---
  "ALLOWED_EXTENSIONS_IMAGE=.jpg,.jpeg,.png,.gif,.webp",
  "ALLOWED_EXTENSIONS_AUDIO=.mp3,.wav,.ogg,.m4a,.opus",
  "ALLOWED_EXTENSIONS_VIDEO=.mp4,.avi,.mov,.webm",
  "ALLOWED_EXTENSIONS_DOCUMENT=.pdf,.doc,.docx,.txt"
)

# Comando de deploy (não precisa editar esta parte)
# Substitua 'meu-bot-whatsapp' e 'sua-regiao'
gcloud run deploy whatsapp-ai-service `
  --source . `
  --region southamerica-east1 `
  --allow-unauthenticated `
  --set-env-vars=($envVars -join ',')
```

**Exemplo para CMD (Prompt de Comando do Windows):**

O CMD é mais limitado. A forma mais simples é colocar todas as variáveis em uma única linha longa dentro das aspas, separadas por vírgula. Use o caractere `^` (circunflexo) para quebrar as outras linhas do comando e manter a legibilidade.

```cmd
gcloud run deploy meu-bot-whatsapp ^
  --source . ^
  --region sua-regiao ^
  --allow-unauthenticated ^
  --set-env-vars="SECRET_KEY=seu-segredo,DATABASE_URL=postgresql+psycopg2://yan:cabecadepicles@/whatsapp-ia-ideallys?host=/cloudsql/watsapp-ia:southamerica-east1:whatsapp-ia-ideallys,EVOLUTION_API_URL=sua-url,EVOLUTION_API_KEY=sua-chave,EVOLUTION_INSTANCE_NAME=seu-nome,WEBHOOK_VERIFY_TOKEN=seu-token,GEMINI_API_KEY=sua-chave,GOOGLE_MAPS_API_KEY=sua-chave-maps,GOOGLE_CLOUD_PROJECT_ID=seu-id-gcp,GOOGLE_CLOUD_BUCKET_NAME=seu-bucket,COMPANY_DEFAULT_ADDRESS='Av. Exemplo, 123',KNOWLEDGE_BASE_FILE=knowledge_base.txt,IGNORE_LIST_NUMBERS=5511999998888,AI_NAME=NomeDoBot,AI_PERSONALITY_DESCRIPTION='Amigável e prestativo.',AI_BUSINESS_CONTEXT='Somos uma empresa que faz X, Y e Z.',AI_RESPONSE_STYLE='Responda em parágrafos curtos.',PUSHOVER_APP_TOKEN=seu-pushover-app-token,DEFAULT_PUSHOVER_USER_KEY=sua-pushover-user-key,LOGGING_LEVEL=INFO,ENABLE_ASYNC_PROCESSING=True,MAX_PROCESSING_THREADS=5,INTERNAL_TASK_TOKEN=um-token-interno-super-secreto,VECTOR_DB_ENABLED=False,VECTOR_DB_PROVIDER=chroma,VECTOR_DB_URL=,VECTOR_DB_API_KEY=,VECTOR_DB_ENVIRONMENT=,VECTOR_DB_INDEX_NAME=company-info,EMBEDDING_MODEL_PROVIDER=google,EMBEDDING_MODEL_NAME=textembedding-gecko@003,ALLOWED_EXTENSIONS_IMAGE=.jpg,.jpeg,.png,.gif,.webp,ALLOWED_EXTENSIONS_AUDIO=.mp3,.wav,.ogg,.m4a,.opus,ALLOWED_EXTENSIONS_VIDEO=.mp4,.avi,.mov,.webm,ALLOWED_EXTENSIONS_DOCUMENT=.pdf,.doc,.docx,.txt"
```
> **Nota para CMD:** Você precisa substituir os valores diretamente na string longa. Garanta que não haja quebras de linha reais *dentro* das aspas `""`.

Sua aplicação no Cloud Run irá ler essas variáveis de ambiente exatamente como ela lê o arquivo `.env` na sua máquina local. Isso garante que suas configurações de produção sejam seguras e separadas do seu código. 