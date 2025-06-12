"""
Agente especializado en el manejo de conocimiento y búsqueda de información.
"""
from typing import List, Dict, Any, Optional
from .base_agent import BaseAgent
from .interfaces import IKnowledgeAgent, AgentContext, AgentType
from ..knowledge_base import TourismKB

class KnowledgeAgent(BaseAgent, IKnowledgeAgent):
    """Agente que maneja la búsqueda y gestión del conocimiento"""

    def __init__(self, data_dir: str):
        """
        Inicializa el agente de conocimiento.
        
        Args:
            data_dir: Directorio base de datos
        """
        super().__init__(AgentType.KNOWLEDGE)
        self.kb = TourismKB(data_dir)

    async def process(self, context: AgentContext) -> AgentContext:
        """
        Procesa una consulta buscando información relevante.
        
        Args:
            context: Contexto actual
            
        Returns:
            Contexto actualizado con la información encontrada
        """
        try:
            # Buscar información relevante
            results = await self.search_knowledge(context.query)
            
            # Actualizar contexto con los resultados
            if results:
                context.metadata["knowledge"] = results
                self.update_context_confidence(context, 0.8)
                
                # Extraer y añadir fuentes
                for result in results:
                    if isinstance(result, dict):
                        source = result.get("source", None)
                        if source:
                            self.add_source(context, str(source))
            
            return context
            
        except Exception as e:
            self.set_error(context, f"Error searching knowledge: {str(e)}")
            return context

    async def search_knowledge(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Busca información relevante en la base de conocimiento.
        
        Args:
            query: Consulta a buscar
            limit: Límite de resultados
            
        Returns:
            Lista de resultados encontrados
        """
        try:
            return await self.kb.search(query, limit)
        except Exception as e:
            self.logger.error(f"Error during knowledge search: {str(e)}")
            return []

    async def refresh_knowledge(self) -> None:
        """Actualiza la base de conocimiento"""
        try:
            await self.kb.refresh_data()
        except Exception as e:
            self.logger.error(f"Error refreshing knowledge: {str(e)}")
            raise
