"""
Agente de conocimiento proactivo bajo el modelo BDI.
Maneja la búsqueda y actualización de la base de conocimiento turístico.
"""
import logging
from typing import List, Dict, Any

from .base_agent import BaseAgent
from .interfaces import IKnowledgeAgent, AgentContext, AgentType
from ..knowledge_base import TourismKB
from ..data_managers.dynamic_crawler import SimpleCrawlerIntegration

logger = logging.getLogger(__name__)

class KnowledgeAgent(BaseAgent, IKnowledgeAgent):
    """
    Agente de conocimiento proactivo.
    - Creencias: Estado de la KB, consultas sin respuesta.
    - Deseos: Encontrar información relevante, mantener la KB completa.
    - Intenciones: Buscar en la KB, usar crawler, refrescar la KB.
    """
    
    def __init__(self, data_dir: str):
        super().__init__(AgentType.KNOWLEDGE)
        self.data_dir = data_dir
        self.tourism_kb: TourismKB = None
        self.dynamic_crawler = SimpleCrawlerIntegration()
        
        # Creencias iniciales
        self.beliefs['is_kb_initialized'] = False
        self.beliefs['failed_queries_count'] = 0

    async def initialize(self) -> None:
        """Inicializa la base de conocimiento."""
        try:
            self.tourism_kb = TourismKB(self.data_dir)
            # Aquí podrías añadir una verificación de si la KB está vacía
            self.beliefs['is_kb_initialized'] = True
            logger.info("KnowledgeAgent initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing KnowledgeAgent: {str(e)}")
            raise

    # --- Implementación del Ciclo BDI ---

    def update_beliefs(self, context: AgentContext):
        """El agente percibe el contexto y actualiza sus creencias."""
        super().update_beliefs(context) # Hereda la actualización básica
        if context.knowledge_gap_detected:
            self.beliefs['failed_queries_count'] += 1

    def generate_desires(self):
        """Basado en sus creencias, el agente decide qué quiere lograr."""
        self.desires = []
        # Deseo principal: si hay una consulta, encontrar información para ella.
        if self.beliefs.get('current_query'):
            self.desires.append('find_info_for_query')
        
        # Deseo proactivo: si muchas consultas han fallado, desea refrescar su conocimiento.
        if self.beliefs['failed_queries_count'] > 5:
            self.desires.append('refresh_knowledge_base')

    def generate_intentions(self):
        """El agente se compromete a un plan de acción para cumplir sus deseos."""
        self.intentions = []
        if 'find_info_for_query' in self.desires:
            self.intentions.append(self.intend_to_search_and_enhance)
        if 'refresh_knowledge_base' in self.desires:
            self.intentions.append(self.intend_to_refresh_knowledge)

    # --- Implementación de las Intenciones (Acciones) ---

    async def intend_to_search_and_enhance(self, context: AgentContext) -> AgentContext:
        """
        Intención: Buscar en la KB local y, si no se encuentra nada,
        usar el crawler dinámico para "mejorar" el conocimiento sobre la marcha.
        """
        query = context.query
        if not query:
            return context

        self.logger.info(f"Executing intention: Search knowledge for '{query[:50]}...'")
        results = await self.search_knowledge(query)
        
        if results:
            context.knowledge = results
            self.update_context_confidence(context, self._calculate_confidence(results))
            for result in results:
                self.add_source(context, result.get("source", "Unknown Source"))
            self.logger.info(f"Found {len(results)} items in local KB.")
        else:
            self.logger.warning("No local knowledge found. Activating dynamic crawler.")
            # Crear una respuesta vacía para que el crawler la mejore
            initial_data = {'type': 'destination', 'name': query, 'description': ''}
            enhancement_result = await self.dynamic_crawler.process_query(query, initial_data)
            
            if enhancement_result.get('enhanced'):
                enhanced_data = enhancement_result.get('response', {})
                context.knowledge.append({
                    "id": enhanced_data.get('name', 'dynamic_result').replace(' ', '_').lower(),
                    "source": "dynamic_crawler",
                    "data": enhanced_data
                })
                self.update_context_confidence(context, enhancement_result.get('confidence', 0.8))
                self.logger.info("Dynamic crawler enhanced the response.")
            else:
                context.knowledge_gap_detected = True
                self.logger.warning("Dynamic crawler could not find new information.")

        return context

    async def intend_to_refresh_knowledge(self, context: AgentContext) -> AgentContext:
        """
        Intención proactiva: Refrescar la base de conocimiento completa
        porque se han detectado demasiadas brechas de información.
        """
        self.logger.info("Executing proactive intention: Refreshing knowledge base.")
        try:
            await self.refresh_knowledge()
            self.beliefs['failed_queries_count'] = 0  # Reiniciar el contador
            self.logger.info("Knowledge base refreshed successfully.")
        except Exception as e:
            self.logger.error(f"Failed to execute intention to refresh knowledge: {e}")
        return context

    # --- Métodos de soporte (sin cambios) ---

    async def search_knowledge(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        # El código de este método no necesita cambios
        if not self.tourism_kb: return []
        return await self.tourism_kb.search(query, limit=limit)

    async def refresh_knowledge(self) -> None:
        # El código de este método no necesita cambios
        self.logger.info("Refreshing knowledge base... (implementation details omitted)")
        # Lógica de _get_fresh_data, _process_raw_data, _update_vector_store, etc.

    def _calculate_confidence(self, results: List[Dict[str, Any]]) -> float:
        """
        Calcula el nivel de confianza basado en la calidad y cantidad de resultados.
        
        Args:
            results: Lista de resultados encontrados
            
        Returns:
            Nivel de confianza entre 0.0 y 1.0
        """
        if not results:
            return 0.0
            
        # Factores de confianza
        total_reliability = 0.0
        valid_results = 0
        
        for result in results:
            data = result.get('data', {})
            source_info = data.get('source_info', {})
            reliability = source_info.get('reliability', 0.5)
            
            if reliability > 0:
                total_reliability += reliability
                valid_results += 1
        
        if valid_results == 0:
            return 0.3  # Confianza mínima si hay resultados pero sin info de confiabilidad
            
        # Confianza promedio de las fuentes
        avg_reliability = total_reliability / valid_results
        
        # Ajustar por cantidad de resultados (más resultados = mayor confianza)
        quantity_factor = min(valid_results / 3.0, 1.0)  # Máximo boost en 3 resultados
        
        # Confianza final
        final_confidence = avg_reliability * (0.7 + 0.3 * quantity_factor)
        
        return round(min(final_confidence, 1.0), 2)
