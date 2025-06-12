"""
Base de conocimiento del sistema turístico.
"""
from typing import List, Dict, Any
from .data_managers.vector_store import VectorStore
from .data_managers.data_ingestion import DataIngestionCoordinator
import os
import logging
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
import shutil

logger = logging.getLogger(__name__)

class TourismKB:
    """Base de conocimiento del sistema turístico"""

    def __init__(self, data_dir: str):
        """
        Inicializa la base de conocimiento.
        
        Args:
            data_dir: Directorio base para los datos
        """
        self.data_dir = data_dir
        self.vector_store = VectorStore(os.path.join(data_dir, 'vectors'))
        self.ingestion_coordinator = DataIngestionCoordinator(data_dir)
        self._executor = ThreadPoolExecutor(max_workers=4)
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

    async def search(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Realizar búsqueda semántica en la base de conocimientos.
        
        Args:
            query: Consulta a buscar
            limit: Límite de resultados
            
        Returns:
            Lista de resultados encontrados
        """
        try:
            # Ejecutar búsqueda en un thread separado para no bloquear
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                self._executor,
                lambda: self.vector_store.search(
                    query=query,
                    n_results=limit,
                    filters=None
                )
            )
            
            # Transformar resultados
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
                    "source": metadata.get('source', 'unknown'),
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
            logger.error(f"Error during search: {str(e)}", exc_info=True)
            return []

    async def refresh_data(self):
        """
        Actualizar la base de conocimientos con nuevos datos de manera asíncrona.
        """
        try:
            logger.info("Starting data refresh...")
            # Create a new vector store instance for the update
            temp_vector_dir = os.path.join(self.data_dir, 'vectors_temp')
            temp_vector_store = VectorStore(temp_vector_dir)
            
            # Run ingestion with new vector store in a separate thread
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self._executor,
                lambda: self._run_ingestion(temp_vector_store)
            )
            
            # If successful, replace old vector store
            if os.path.exists(self.vector_store.persist_dir):
                await loop.run_in_executor(
                    self._executor,
                    lambda: shutil.rmtree(self.vector_store.persist_dir)
                )
            
            await loop.run_in_executor(
                self._executor,
                lambda: shutil.move(temp_vector_dir, self.vector_store.persist_dir)
            )
            
            # Update vector store reference
            self.vector_store = VectorStore(self.vector_store.persist_dir)
            
            logger.info("Data refresh completed successfully")
            
        except Exception as e:
            logger.error(f"Error during data refresh: {str(e)}", exc_info=True)
            raise

    def _run_ingestion(self, vector_store: VectorStore):
        """
        Ejecuta la ingestión de datos en un nuevo vector store.
        
        Args:
            vector_store: Vector store temporal para la nueva ingestión
        """
        self.ingestion_coordinator.vector_store = vector_store
        self.ingestion_coordinator.run_ingestion()
