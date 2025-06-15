# =================== SCRIPT DE ARQUIVO ÚNICO (VERSÃO FINAL CORRIGIDA) ===================

# Verificar autenticação do Google Cloud
Write-Host "Verificando autenticação do Google Cloud..."
try {
    $authStatus = gcloud auth list --filter=status:ACTIVE --format="value(account)"
    if (-not $authStatus) {
        Write-Host "Nenhuma conta ativa encontrada. Iniciando processo de login..."
        gcloud auth login
    } else {
        Write-Host "Conta ativa encontrada: $authStatus"
    }
} catch {
    Write-Host "Erro ao verificar autenticação: $_"
    exit 1
}

# Verificar configuração do projeto
Write-Host "Verificando configuração do projeto..."
try {
    $project = gcloud config get-value project
    if (-not $project) {
        Write-Host "Nenhum projeto configurado. Configurando projeto..."
        gcloud config set project watsapp-ia
    } else {
        Write-Host "Projeto atual: $project"
    }
} catch {
    Write-Host "Erro ao verificar configuração do projeto: $_"
    exit 1
}

# Habilitar APIs necessárias
Write-Host "Habilitando APIs necessárias..."
try {
    $apis = @(
        "run.googleapis.com",
        "cloudbuild.googleapis.com",
        "artifactregistry.googleapis.com"
    )
    
    foreach ($api in $apis) {
        Write-Host "Verificando API $api..."
        $status = gcloud services list --enabled --filter="name:$api" --format="value(name)"
        if (-not $status) {
            Write-Host "Habilitando API $api..."
            gcloud services enable $api
        } else {
            Write-Host "API $api já está habilitada"
        }
    }
} catch {
    Write-Host "Erro ao habilitar APIs: $_"
    exit 1
}

# Verificar permissões do usuário
Write-Host "Verificando permissões do usuário..."
try {
    $requiredRoles = @(
        "roles/run.admin",
        "roles/cloudsql.client",
        "roles/cloudbuild.builds.builder",
        "roles/artifactregistry.writer"
    )
    
    $currentRoles = gcloud projects get-iam-policy $project --format="value(bindings.role)" --flatten="bindings[].members" --filter="bindings.members:$authStatus"
    
    foreach ($role in $requiredRoles) {
        if ($currentRoles -notcontains $role) {
            Write-Host "Adicionando role $role ao usuário..."
            gcloud projects add-iam-policy-binding $project --member="user:$authStatus" --role=$role
        }
    }
} catch {
    Write-Host "Erro ao verificar permissões: $_"
    exit 1
}

# 1. Definição das Variáveis de Ambiente (exatamente como antes)
$envVars = @(
  # --- Configuração Essencial ---
  "SECRET_KEY=YoWyRnc6_4U5uudTPYELdFmM2lrRDarr7BTKq13ug6k",
  
  # --- Cloud SQL Configuration ---
  "INSTANCE_CONNECTION_NAME=watsapp-ia:southamerica-east1:whatsapp-ia-ideallys",
  "DB_USER=yan",
  "DB_PASS=cabecadepicles",
  "DB_NAME=whatsapp_prod",
  "PRIVATE_IP=False",

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
  "COMPANY_DEFAULT_ADDRESS=Rua 17 Q 11 lt 30-B, JARDIM JUSARA, CALDAS NOVAS, GOIAS",
  "KNOWLEDGE_BASE_FILE=knowledge_base.txt",
  "IGNORE_LIST_NUMBERS=5511999998888,15551234567",

  # --- Personalização da IA ---
  "AI_NAME=Ideallys Assistente",
  "AI_PERSONALITY_DESCRIPTION=Atencioso, eficiente e sempre pronto para ajudar com soluções digitais inteligentes.",
  "AI_BUSINESS_CONTEXT=A Ideallys é uma empresa especializada em criação de sites, marketing digital (tráfego pago e orgânico) e atendimento automatizado via inteligência artificial multimodal. Nosso principal produto é uma IA que entende texto, áudio, imagem e vídeo, personaliza o atendimento para cada cliente e armazena o histórico de mensagens. Em breve, ofereceremos planos com relatórios, insights sobre produtos e demandas regionais.",
  "AI_RESPONSE_STYLE=Responda em parágrafos curtos.",

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

# --- Abordagem recomendada: Usar um arquivo YAML temporário ---
$yamlFilePath = Join-Path $PSScriptRoot "temp-env-vars-for-deploy.yaml"

# 2. Gere o conteúdo do arquivo YAML a partir da lista de variáveis
$yamlContent = @()
foreach ($var in $envVars) {
    $parts = $var.Split('=', 2)
    if ($parts.Length -eq 2) {
        $key = $parts[0]
        $value = $parts[1]
        $escapedValue = $value.Replace("'", "''")
        $yamlContent += "${key}: '$escapedValue'"
    }
}

# 3. Salve o conteúdo no arquivo YAML
Set-Content -Path $yamlFilePath -Value ($yamlContent -join [System.Environment]::NewLine) -Encoding UTF8

Write-Host "Arquivo de variáveis de ambiente temporário criado em '$yamlFilePath'"

# 4. Execute o comando gcloud, passando o caminho para o arquivo YAML
Write-Host "Iniciando o deploy no Google Cloud Run..."
try {
    # Tentar o deploy com retry
    $maxRetries = 3
    $retryCount = 0
    $success = $false

    while (-not $success -and $retryCount -lt $maxRetries) {
        try {
            Write-Host "Tentativa de deploy $($retryCount + 1) de $maxRetries..."
            $buildOutput = gcloud run deploy whatsapp-ai-service `
                --source . `
                --region southamerica-east1 `
                --allow-unauthenticated `
                --add-cloudsql-instances=watsapp-ia:southamerica-east1:whatsapp-ia-ideallys `
                --env-vars-file="$yamlFilePath" `
                --verbosity=debug 2>&1
            
            Write-Host $buildOutput
            
            # Check if build failed
            if ($LASTEXITCODE -ne 0) {
                Write-Host "Build failed. Fetching build logs..."
                # Extract build ID from the operation
                $buildId = $buildOutput | Select-String -Pattern "operations/([a-f0-9-]+)" | ForEach-Object { $_.Matches.Groups[1].Value }
                if ($buildId) {
                    Write-Host "Build ID: $buildId"
                    Write-Host "Fetching build logs..."
                    gcloud builds log --stream $buildId
                } else {
                    Write-Host "Could not find build ID in output. Trying to get latest failed build..."
                    $latestBuild = gcloud builds list --filter="status=FAILURE" --limit=1 --format="value(id)" 2>&1
                    if ($latestBuild) {
                        Write-Host "Latest failed build ID: $latestBuild"
                        gcloud builds log --stream $latestBuild
                    }
                }
                throw "Build failed. See logs above for details."
            }
            $success = $true
        } catch {
            $retryCount++
            if ($retryCount -lt $maxRetries) {
                Write-Host "Erro no deploy. Aguardando 30 segundos antes da próxima tentativa..."
                Start-Sleep -Seconds 30
            } else {
                Write-Host "Todas as tentativas de deploy falharam. Último erro: $_"
                throw
            }
        }
    }
} catch {
    Write-Host "Erro durante o deploy: $_"
    exit 1
} finally {
    # 5. Limpe o arquivo temporário após o deploy (mesmo que falhe)
    Write-Host "Removendo o arquivo temporário..."
    Remove-Item -Path $yamlFilePath -ErrorAction SilentlyContinue
}