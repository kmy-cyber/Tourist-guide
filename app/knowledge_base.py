from typing import List
from .data_managers.vector_store import VectorStore
from .data_managers.data_ingestion import DataIngestionCoordinator
import os
import logging
import json

logger = logging.getLogger(__name__)

class TourismKB:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.vector_store = VectorStore(os.path.join(data_dir, 'vectors'))
        self.ingestion_coordinator = DataIngestionCoordinator(data_dir)
        self._initialize_data()

    def _initialize_data(self):
        """Initialize data if needed"""
        vector_dir = os.path.join(self.data_dir, 'vectors')
        # Si no existe el directorio de vectores o está vacío, ejecutar ingestión
        if not os.path.exists(vector_dir) or not os.listdir(vector_dir):
            logger.info("Vector store empty or not found. Running initial data ingestion...")
            try:
                self.ingestion_coordinator.run_ingestion()
                logger.info("Initial data ingestion completed successfully")
            except Exception as e:
                logger.error(f"Error during initial data ingestion: {str(e)}")

    def search(self, query: str, limit: int = 3) -> List[dict]:
        """
        Realizar búsqueda semántica en la base de conocimientos
        """
        try:
            # Buscar en el vector store
            results = self.vector_store.search(
                query=query,
                n_results=limit,
                filters=None
            )
            
            # Transformar resultados al formato esperado
            formatted_results = []
            for result in results:
                if not isinstance(result, dict) or 'metadata' not in result:
                    logger.warning(f"Invalid result format: {result}")
                    continue
                    
                metadata = result.get('metadata', {})
                if not metadata:
                    logger.warning(f"Result has no metadata: {result}")
                    continue
                    
                formatted_results.append({
                    "id": metadata.get('source', 'unknown'),
                    "data": {
                        "description": result.get('document', ''),
                        "name": metadata.get('name', ''),
                        "type": metadata.get('type', ''),
                        "location": metadata.get('location', {}),
                        "source_info": metadata.get('source_info', {}),
                    }
                })
                
            return formatted_results

        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            return []
            
    async def async_search(self, query: str, limit: int = 3) -> List[dict]:
        """
        Versión asíncrona de la búsqueda semántica
        """
        return self.search(query, limit)

    def refresh_data(self):
        """Actualizar la base de conocimientos con nuevos datos"""
        try:
            logger.info("Starting data refresh...")
            temp_vector_dir = os.path.join(self.data_dir, 'vectors_temp')
            temp_vector_store = VectorStore(temp_vector_dir)
            
            self.ingestion_coordinator.vector_store = temp_vector_store
            self.ingestion_coordinator.run_ingestion()
            
            if os.path.exists(self.vector_store.persist_dir):
                import shutil
                shutil.rmtree(self.vector_store.persist_dir)
            shutil.move(temp_vector_dir, self.vector_store.persist_dir)
            
            self.vector_store = VectorStore(self.vector_store.persist_dir)
            logger.info("Data refresh completed successfully")
        except Exception as e:
            logger.error(f"Error during data refresh: {str(e)}")
            raise
