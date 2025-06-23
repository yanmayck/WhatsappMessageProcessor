import uvicorn
import os
from app import app # Import the FastAPI app instance directly

# Adicionado para permitir rodar o servidor de desenvolvimento com python main.py
if __name__ == '__main__':
    # Usa a porta da variável de ambiente PORT ou 8080 como padrão
    # debug=True é útil para desenvolvimento
    port = int(os.environ.get('PORT', 8080))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True, log_level="debug")
