import logging
import os
import numpy as np
from typing import List, Optional

# Verificações de importação para FAISS e SentenceTransformers
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

logger = logging.getLogger(__name__)

class KnowledgeBaseService:
    def __init__(self, filepath: str, model_name: str = 'all-MiniLM-L6-v2'):
        if not FAISS_AVAILABLE:
            raise ImportError("FAISS is not installed. Please run 'pip install faiss-cpu'.")
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("SentenceTransformers is not installed. Please run 'pip install sentence-transformers'.")
        
        self.filepath = filepath
        self.model = None
        self.index = None
        self.chunks = []

        if not os.path.exists(filepath):
            logger.error(f"Knowledge base file not found at: {filepath}")
            raise FileNotFoundError(f"Knowledge base file not found: {filepath}")

        try:
            logger.info(f"Initializing Knowledge Base Service with model '{model_name}'...")
            self.model = SentenceTransformer(model_name)
            self._build_index()
            logger.info("Knowledge Base Service initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize SentenceTransformer model or build FAISS index: {e}", exc_info=True)
            # A aplicação pode continuar, mas a busca de conhecimento não funcionará.
            self.model = None

    def _load_and_chunk_document(self) -> None:
        """Loads the document and splits it into chunks."""
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Estratégia de divisão simples: dividir por seções e depois por linhas não vazias.
            # Isso funciona bem para o formato de markdown que estamos usando.
            sections = content.split('# ')
            for section in sections:
                if not section.strip():
                    continue
                lines = [line.strip() for line in section.split('\n') if line.strip()]
                # Juntar título da seção com suas linhas
                if lines:
                    full_section_text = "# " + " ".join(lines)
                    self.chunks.append(full_section_text)
            
            logger.info(f"Loaded and processed {len(self.chunks)} chunks from {self.filepath}")

        except Exception as e:
            logger.error(f"Error loading or chunking knowledge base file: {e}", exc_info=True)
            self.chunks = []

    def _build_index(self) -> None:
        """Builds the FAISS index from the document chunks."""
        self._load_and_chunk_document()
        
        if not self.chunks or not self.model:
            logger.warning("No chunks to index or model not loaded. Skipping FAISS index build.")
            return

        try:
            logger.info("Encoding document chunks into vectors...")
            # Codificar os trechos de texto em vetores
            embeddings = self.model.encode(self.chunks, convert_to_tensor=False)
            
            # Garantir que os embeddings sejam float32, como esperado pelo FAISS
            embeddings = np.array(embeddings).astype('float32')
            
            dimension = embeddings.shape[1]
            
            # Construir o índice FAISS
            self.index = faiss.IndexFlatL2(dimension)
            self.index.add(embeddings)
            
            logger.info(f"FAISS index built successfully with {self.index.ntotal} vectors.")

        except Exception as e:
            logger.error(f"Failed to build FAISS index: {e}", exc_info=True)
            self.index = None

    def search(self, query: str, k: int = 3) -> Optional[List[str]]:
        """
        Searches the knowledge base for the most relevant chunks.
        """
        if not self.index or not self.model:
            logger.warning("Cannot search: FAISS index or model is not available.")
            return None
        
        if not query or not query.strip():
            logger.debug("Skipping knowledge base search for empty query.")
            return None

        try:
            logger.debug(f"Searching knowledge base for query: '{query}'")
            # Codificar a consulta de busca para um vetor
            query_vector = self.model.encode([query], convert_to_tensor=False)
            query_vector = np.array(query_vector).astype('float32')
            
            # Realizar a busca no índice
            distances, indices = self.index.search(query_vector, k)
            
            # Obter os trechos de texto correspondentes
            results = [self.chunks[i] for i in indices[0] if i < len(self.chunks)]
            
            logger.info(f"Found {len(results)} relevant chunks for query.")
            return results

        except Exception as e:
            logger.error(f"Error during knowledge base search: {e}", exc_info=True)
            return None

    def reload(self) -> None:
        """Reloads the document and rebuilds the index."""
        logger.info("Reloading knowledge base and rebuilding index...")
        try:
            self._build_index()
            logger.info("Knowledge base reloaded successfully.")
        except Exception as e:
            logger.error(f"Failed to reload knowledge base: {e}", exc_info=True) 