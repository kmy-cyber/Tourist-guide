"""
Base de conocimiento del sistema turístico.
"""
from typing import List, Dict, Any
from .data_managers.vector_store import VectorStore
import os
import logging

logger = logging.getLogger(__name__)

class TourismKB:
    """Base de conocimiento simplificada"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.vector_store = VectorStore(os.path.join(data_dir, 'vectors'))

    async def search(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Búsqueda simplificada"""
        try:
            # Búsqueda directa en vector store
            results = self.vector_store.search(query=query, k=limit)
            
            # Formatear resultados para el sistema
            formatted_results = []
            for result in results:
                metadata = result.get('metadata', {})
                formatted_results.append({
                    "id": result.get('id', 'unknown'),
                    "source": metadata.get('source_info', {}).get('type', 'unknown'),
                    "data": {
                        "name": metadata.get('name', ''),
                        "description": metadata.get('description', ''),
                        "type": metadata.get('type', ''),
                        "location": metadata.get('location', {}),
                        "source_info": metadata.get('source_info', {}),
                    }
                })
                
            return formatted_results

        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            return []
