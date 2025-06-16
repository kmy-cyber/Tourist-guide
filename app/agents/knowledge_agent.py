"""
Agente especializado en el manejo de conocimiento y búsqueda de información.
"""
from typing import List, Dict, Any
from .base_agent import BaseAgent
from .interfaces import IKnowledgeAgent, AgentContext, AgentType
from ..data_managers.crawler import CrawlerManager, CrawlerType
from ..data_managers.site_crawlers import BuenViajeCubaCrawler, CubaTravelCrawler, HabCulturalMuseosCrawler, HiCubaCrawler, SitiosTuristicosCrawler, ViajeHotelesCubaCrawler, VisitCubaGoCrawler
from ..data_managers.dynamic_crawler import SmartCrawler, SimpleCrawlerIntegration
import asyncio
import logging
import os
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class KnowledgeAgent(BaseAgent, IKnowledgeAgent):
    """Agente que maneja la búsqueda y gestión del conocimiento"""

    def __init__(self, data_dir: str):
        """
        Inicializa el agente de conocimiento.
        
        Args:
            data_dir: Directorio base de datos
        """
        super().__init__(AgentType.KNOWLEDGE)
        self.data_dir = data_dir
        self.cache_dir = os.path.join(data_dir, 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Inicializar el gestor de crawlers
        self.crawler_manager = CrawlerManager()
        
        # Registrar crawlers disponibles
        self._register_crawlers()
        
    def _register_crawlers(self):
        """Registra los crawlers disponibles"""
        
        # self.crawler_manager.register_crawler(CubaTravelCrawler())
        # self.crawler_manager.register_crawler(HiCubaCrawler())
        # self.crawler_manager.register_crawler(ViajeHotelesCubaCrawler())
        # self.crawler_manager.register_crawler(BuenViajeCubaCrawler())
        # self.crawler_manager.register_crawler(VisitCubaGoCrawler())
        # self.crawler_manager.register_crawler(SitiosTuristicosCrawler())
        self.crawler_manager.register_crawler(HabCulturalMuseosCrawler())


    async def process(self, context: AgentContext) -> AgentContext:
        """
        Procesa una consulta buscando información relevante.
        
        Args:
            context: Contexto actual
            
        Returns:
            Contexto actualizado con la información encontrada
        """
        try:
            # Buscar información en el caché o crawlers
            results = await self.search_knowledge(context.query)
            
            # Actualizar contexto con los resultados
            if results:
                context.metadata["knowledge"] = results
                self.update_context_confidence(context, self._calculate_confidence(results))
                
                # Extraer y añadir fuentes
                for result in results:
                    source = result.get("source", {}).get("name", "Unknown Source")
                    self.add_source(context, str(source))
            
            return context
            
        except Exception as e:
            self.set_error(context, f"Error searching knowledge: {str(e)}")
            return context

    async def search_knowledge(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Busca información relevante.
        
        Args:
            query: Consulta a buscar
            limit: Límite de resultados
            
        Returns:
            Lista de resultados encontrados
        """
        try:
            # Primero buscar en caché
            cached_results = await self._check_cache(query)
            if cached_results:
                return cached_results[:limit]
            
            # Si no hay caché, usar crawlers
            results = await self._search_with_crawlers(query)
            
            # Guardar en caché
            await self._save_to_cache(query, results)
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error during knowledge search: {str(e)}")
            return []

    async def refresh_knowledge(self) -> None:
        """Actualiza la base de conocimiento usando los crawlers"""

        logger.info("-------")
        
        try:
            # Ejecutar crawlers registrados
            results = await self.crawler_manager.run_crawlers()

            logger.info(f"crawlers registrados: {results}")
            
            if results["stats"]["total_items"] > 0:
                # Limpiar caché
                await self._clear_cache()
                logger.info("Knowledge refreshed successfully")
            else:
                logger.warning("No new data found during refresh")
                
        except Exception as e:
            logger.error(f"Error refreshing knowledge: {str(e)}")
            raise

    async def _check_cache(self, query: str) -> List[Dict[str, Any]]:
        """Busca resultados en el caché"""
        cache_file = os.path.join(self.cache_dir, f"{hash(query)}.json")
        
        if os.path.exists(cache_file):
            try:
                # Verificar si el caché es reciente (menos de 24 horas)
                if (datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))).days < 1:
                    async with asyncio.Lock():
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            return json.load(f)
            except Exception as e:
                logger.warning(f"Error reading cache: {str(e)}")
                
        return []

    async def _save_to_cache(self, query: str, results: List[Dict[str, Any]]):
        """Guarda resultados en el caché"""
        cache_file = os.path.join(self.cache_dir, f"{hash(query)}.json")
        
        try:
            async with asyncio.Lock():
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Error saving to cache: {str(e)}")

    async def _clear_cache(self):
        """Limpia el caché de búsquedas"""
        try:
            for file in os.listdir(self.cache_dir):
                if file.endswith('.json'):
                    os.remove(os.path.join(self.cache_dir, file))
            logger.info("Cache cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")

    async def _search_with_crawlers(self, query: str) -> List[Dict[str, Any]]:
        """Realiza búsqueda usando los crawlers disponibles y el crawler dinámico como respaldo"""
        results = []
        
        try:
            # Ejecutar crawlers específicos según el tipo de consulta
            crawler_types = self._determine_crawler_types(query)

            # crawler_results = await self.crawler_manager.run_crawlers(crawler_types)
            
            # if crawler_results and "data" in crawler_results:
            #     results.extend(self._format_crawler_results(crawler_results["data"]))
            
            # # Si no hay resultados, usar el crawler dinámico
            # if not results:
            #     logger.info("No se encontraron resultados con crawlers regulares. Usando crawler dinámico...")

            dynamic_crawler = SimpleCrawlerIntegration()
            try:
                # Crear datos iniciales vacíos que el crawler dinámico intentará completar
                initial_data = {
                    'query': query,
                    'type': crawler_types[0].value if crawler_types else 'destination',
                    'last_updated': datetime.now().isoformat()
                }
                
                # Procesar con el crawler dinámico
                enhanced_data = await dynamic_crawler.process_query(query, initial_data)
                if enhanced_data and enhanced_data.get('response'):
                    results.append(self._format_dynamic_result(enhanced_data['response']))
                    logger.info(f"Crawler dinámico encontró información. Confianza: {enhanced_data.get('confidence', 0):.2f}")
            finally:
                await dynamic_crawler.cleanup()
            
        except Exception as e:
            logger.error(f"Error in crawler search: {str(e)}")
            
        return results

    def _determine_crawler_types(self, query: str) -> List[CrawlerType]:
        """Determina qué tipos de crawlers usar según la consulta"""
        query_lower = query.lower()
        types = []
        
        if any(word in query_lower for word in ["museo", "museum", "galería", "exposición"]):
            types.append(CrawlerType.MUSEUM)
        if any(word in query_lower for word in ["excursión", "tour", "visita", "excursion"]):
            types.append(CrawlerType.EXCURSION)
        if any(word in query_lower for word in ["destino", "lugar", "sitio", "destination"]):
            types.append(CrawlerType.DESTINATION)
            
        return types or list(CrawlerType)  # Si no hay tipos específicos, usar todos

    def _format_crawler_results(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Formatea los resultados del crawler al formato estándar"""
        formatted = []
        
        for item in data:
            formatted.append({
                "source": {
                    "name": item.get("source", {}).get("name", "Unknown"),
                    "url": item.get("source", {}).get("url", ""),
                    "reliability": item.get("source", {}).get("reliability", 0.5),
                },
                "data": {
                    "name": item.get("name", ""),
                    "type": item.get("type", ""),
                    "description": item.get("description", ""),
                    "location": item.get("location", {}),
                    "metadata": item.get("metadata", {})
                }
            })
            
        return formatted

    def _format_dynamic_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Formatea el resultado del crawler dinámico al formato estándar"""
        return {
            "id": f"dynamic_{hash(str(data))}",
            "name": data.get("name", ""),
            "type": data.get("type", "destination"),
            "description": data.get("description", ""),
            "location": data.get("location", ""),
            "price": data.get("price", ""),
            "schedule": data.get("schedule", ""),
            "source": {
                "name": "Dynamic Crawler",
                "url": "internet_search",
                "reliability": 0.7,
                "crawl_date": datetime.now().isoformat()
            },
            "metadata": {
                "enhanced": True,
                "original_source": data.get("source", {})
            }
        }

    def _calculate_confidence(self, results: List[Dict[str, Any]]) -> float:
        """Calcula el nivel de confianza basado en los resultados"""
        if not results:
            return 0.0
            
        confidence_sum = sum(
            result.get("source", {}).get("reliability", 0.5)
            for result in results
        )
        
        return round(confidence_sum / len(results), 2)
