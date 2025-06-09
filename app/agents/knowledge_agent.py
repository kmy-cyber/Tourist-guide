"""
Agente especializado en manejo de conocimiento turístico.
"""
from typing import List, Dict, Any
from .base_agent import BaseAgent
from .interfaces import IKnowledgeAgent, AgentContext
from ..data_managers.vector_store import VectorStore
from ..data_managers.data_ingestion import DataIngestionCoordinator
import os

class KnowledgeAgent(BaseAgent, IKnowledgeAgent):
    """Agente que maneja la base de conocimientos turísticos"""
    
    def __init__(self, data_dir: str):
        """
        Inicializa el agente de conocimiento.
        
        Args:
            data_dir: Directorio base para los datos
        """
        super().__init__()
        self.data_dir = data_dir
        self.vector_store = VectorStore(os.path.join(data_dir, 'vectors'))
        self.ingestion_coordinator = DataIngestionCoordinator(data_dir)
        self._initialize_data()
    
    def _initialize_data(self):
        """Inicializa los datos si es necesario"""
        vector_dir = os.path.join(self.data_dir, 'vectors')
        if not os.path.exists(vector_dir) or not os.listdir(vector_dir):
            self.logger.info("Vector store empty or not found. Running initial data ingestion...")
            try:
                self.ingestion_coordinator.run_ingestion()
                self.logger.info("Initial data ingestion completed successfully")
            except Exception as e:
                self.logger.error(f"Error during initial data ingestion: {str(e)}")
    
    async def search_knowledge(self, query: str) -> List[Dict[str, Any]]:
        """
        Realiza una búsqueda en la base de conocimientos.
        
        Args:
            query: Consulta a buscar
            
        Returns:
            Lista de resultados relevantes
        """
        try:
            results = self.vector_store.search(
                query=query,
                n_results=3,
                filters=None
            )
            
            return [
                {
                    "id": r.get('metadata', {}).get('source', 'unknown'),
                    "data": {
                        "description": r.get('document', ''),
                        "name": r.get('metadata', {}).get('name', ''),
                        "type": r.get('metadata', {}).get('type', ''),
                        "location": r.get('metadata', {}).get('location', {}),
                        "source_info": r.get('metadata', {}).get('source_info', {}),
                    }
                }
                for r in results
                if isinstance(r, dict) and 'metadata' in r
            ]
            
        except Exception as e:
            self.logger.error(f"Error during knowledge search: {str(e)}")
            return []
    
    async def _process_impl(self, context: AgentContext) -> AgentContext:
        """
        Procesa el contexto buscando información relevante.
        """
        results = await self.search_knowledge(context.query)
        
        if results:
            # Actualizar confianza basada en los resultados
            reliability_scores = {
                'high': 1.0,
                'medium': 0.8,
                'low': 0.6,
                'unknown': 0.5
            }
            
            total_score = sum(
                reliability_scores.get(
                    r['data']['source_info'].get('reliability', 'unknown'),
                    0.5
                )
                for r in results
            )
            context.confidence = min(total_score / len(results), 1.0)
            
            # Actualizar fuentes
            context.sources.extend(
                r['id'] for r in results
                if r['id'] not in context.sources
            )
            
            # Guardar resultados en metadata
            context.metadata['knowledge_results'] = results
        
        return context
