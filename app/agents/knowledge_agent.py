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
        
        self.beliefs['new_knowledge_to_persist'] = context.metadata.get('new_knowledge')

    def generate_desires(self):
        """Basado en sus creencias, el agente decide qué quiere lograr."""
        self.desires = []
        # Deseo principal: si hay una consulta, encontrar información para ella.
        if self.beliefs.get('current_query'):
            self.desires.append('find_info_for_query')
        
        if self.beliefs.get('new_knowledge_to_persist'):
            self.desires.append('persist_new_knowledge')
        
        # Deseo proactivo: si muchas consultas han fallado, desea refrescar su conocimiento.
        if self.beliefs['failed_queries_count'] > 5:
            self.desires.append('refresh_knowledge_base')

    def generate_intentions(self):
        """El agente se compromete a un plan de acción para cumplir sus deseos."""
        self.intentions = []
        if 'find_info_for_query' in self.desires:
            self.intentions.append(self.intend_to_search_and_enhance)
        if 'persist_new_knowledge' in self.desires:
            self.intentions.append(self.intend_to_persist_knowledge) # NUEVA INTENCIÓN
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
                formatted_result = {
                    "id": enhanced_data.get('name', 'dynamic_result').replace(' ', '_').lower(),
                    "source": "dynamic_crawler",
                    "data": enhanced_data
                }

                context.knowledge.append(formatted_result)
                
                # Marca la información como "nueva" en los metadatos para que la recoja en el próximo ciclo.
                context.metadata['new_knowledge'] = [formatted_result]

                self.update_context_confidence(context, enhancement_result.get('confidence', 0.8))
                self.logger.info("Dynamic crawler enhanced the response.")
            else:
                context.knowledge_gap_detected = True
                self.logger.warning("Dynamic crawler could not find new information.")

        return context

    async def intend_to_persist_knowledge(self, context: AgentContext) -> AgentContext:
        """
        NUEVA INTENCIÓN: Persiste el nuevo conocimiento en la KB híbrida.
        """
        new_knowledge = self.beliefs.get('new_knowledge_to_persist')
        if not new_knowledge:
            return context

        self.logger.info(f"Ejecutando intención: Persistiendo {len(new_knowledge)} nuevo(s) item(s) de conocimiento.")
        try:
            self.tourism_kb.update_kb(new_knowledge)
            self.logger.info("Nuevo conocimiento persistido correctamente en la KB híbrida.")
            context.metadata.pop('new_knowledge', None) # Limpiar para no repetir
        except Exception as e:
            self.logger.error(f"Falló la intención de persistir conocimiento: {e}")
        
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
        """
        Actualiza la base de conocimiento de forma simplificada.
        Este es el método principal para refrescar todos los datos.
        """
        logger.info("Starting simplified knowledge refresh...")
        
        try:
            # 1. Obtener datos frescos de múltiples fuentes
            fresh_data = await self._get_fresh_data()
            
            if not fresh_data:
                logger.warning("No fresh data collected, using existing data")
                return
                
            # 2. Procesar y validar los datos
            processed_items = fresh_data
            
            if not processed_items:
                logger.warning("No valid items after processing")
                return
            
            # 3. Actualizar vector store con los datos procesados
            await self._update_vector_store(processed_items)

            logger.info(f"Knowledge refresh completed successfully with {len(processed_items)} items")
            
        except Exception as e:
            logger.error(f"Error refreshing knowledge: {str(e)}")
            raise

    async def _get_fresh_data(self) -> List[Dict]:
        """
        Obtiene datos frescos de fuentes confiables.
        Combina datos estáticos con crawlers esenciales.
        """
        all_data = []
        
        # 1. Datos estáticos conocidos (siempre disponibles, alta confiabilidad)
        static_data = self._get_static_tourism_data()
        all_data.extend(static_data)
        logger.info(f"Added {len(static_data)} static tourism items")
        
        # 2. Crawler de TripAdvisor CSV (local, rápido)
        try:
            csv_crawler = TripAdvisorCSVCrawler()
            csv_data = await csv_crawler.crawl()
            if csv_data:
                all_data.extend(csv_data)
                logger.info(f"Added {len(csv_data)} items from TripAdvisor CSV")
        except Exception as e:
            logger.warning(f"TripAdvisor CSV crawler failed: {e}")
        
        # 3. Crawler de Habana Cultural (museos)
        try:
            museum_crawler = HabCulturalMuseosCrawler()
            museum_data = await museum_crawler.crawl()
            if museum_data:
                all_data.extend(museum_data)
                logger.info(f"Added {len(museum_data)} items from Habana Cultural")
        except Exception as e:
            logger.warning(f"Habana Cultural crawler failed: {e}")
        
        logger.info(f"Total fresh data collected: {len(all_data)} items")
        return all_data

    

    def _get_static_tourism_data(self) -> List[Dict]:
        """
        Datos estáticos conocidos de Cuba con alta confiabilidad.
        Estos datos siempre están disponibles como fallback.
        """
        return [
            {
                "id": "habana_vieja",
                "name": "La Habana Vieja",
                "type": "destination",
                "description": "Centro histórico de La Habana, declarado Patrimonio de la Humanidad por la UNESCO. Conserva la arquitectura colonial española mejor preservada de América.",
                "location": {
                    "name": "La Habana", 
                    "address": "Centro Histórico, La Habana",
                    "coordinates": {"lat": 23.1367, "lon": -82.3589}
                },
                "source": "static_data",
                "rating": 4.8
            },
            {
                "id": "capitolio_nacional",
                "name": "Capitolio Nacional",
                "type": "monument",
                "description": "Emblemático edificio neoclásico que fue sede del gobierno cubano. Inspirado en el Capitolio de Washington, es uno de los símbolos más reconocibles de La Habana.",
                "location": {
                    "name": "La Habana",
                    "address": "Paseo de Martí, La Habana",
                    "coordinates": {"lat": 23.1351, "lon": -82.3599}
                },
                "source": "static_data",
                "rating": 4.6
            },
            {
                "id": "malecon_habana",
                "name": "El Malecón",
                "type": "attraction",
                "description": "Paseo marítimo más famoso de La Habana, de 8 km de longitud. Lugar de encuentro tradicional de habaneros y turistas para disfrutar del atardecer.",
                "location": {
                    "name": "La Habana",
                    "address": "Malecón, La Habana",
                    "coordinates": {"lat": 23.1478, "lon": -82.3829}
                },
                "source": "static_data",
                "rating": 4.7
            },
            {
                "id": "playa_varadero",
                "name": "Playa de Varadero",
                "type": "beach",
                "description": "Una de las mejores playas del mundo, con 20 km de arena blanca y aguas cristalinas. Principal destino de sol y playa de Cuba.",
                "location": {
                    "name": "Varadero",
                    "address": "Península de Hicacos, Matanzas",
                    "coordinates": {"lat": 23.1543, "lon": -81.2513}
                },
                "source": "static_data",
                "rating": 4.9
            },
            {
                "id": "valle_vinales",
                "name": "Valle de Viñales",
                "type": "nature",
                "description": "Paisaje único de mogotes y plantaciones de tabaco, Patrimonio de la Humanidad. Conocido por sus formaciones kársticas y cultivo de tabaco tradicional.",
                "location": {
                    "name": "Viñales",
                    "address": "Pinar del Río",
                    "coordinates": {"lat": 22.6196, "lon": -83.7113}
                },
                "source": "static_data",
                "rating": 4.8
            },
            {
                "id": "trinidad_colonial",
                "name": "Trinidad",
                "type": "destination",
                "description": "Ciudad colonial perfectamente conservada, Patrimonio de la Humanidad. Conocida por sus calles empedradas y arquitectura del siglo XVIII.",
                "location": {
                    "name": "Trinidad",
                    "address": "Sancti Spíritus",
                    "coordinates": {"lat": 21.8019, "lon": -79.9847}
                },
                "source": "static_data",
                "rating": 4.7
            },
            {
                "id": "museo_revolucion",
                "name": "Museo de la Revolución",
                "type": "museum",
                
                "description": "Principal museo histórico de Cuba, ubicado en el antiguo Palacio Presidencial. Exhibe la historia de la Revolución Cubana.",
                "location": {
                    "name": "La Habana",
                    "address": "Refugio 1, La Habana",
                    "coordinates": {"lat": 23.1394, "lon": -82.3570}
                },
                "source": "static_data",
                "rating": 4.3
            },
            {
                "id": "catedral_habana",
                "name": "Catedral de La Habana",
                "type": "monument",
                "description": "Catedral de San Cristóbal, joya del barroco cubano del siglo XVIII. Una de las catedrales más bellas de América Latina.",
                "location": {
                    "name": "La Habana",
                    "address": "Plaza de la Catedral, La Habana Vieja",
                    "coordinates": {"lat": 23.1412, "lon": -82.3532}
                },
                "source": "static_data",
                "rating": 4.5
            }
        ]

    def _process_raw_data(self, raw_data: List[Dict]) -> List[Dict]:
        """
        Procesa y valida los datos crudos para asegurar calidad.
        
        Args:
            raw_data: Lista de datos sin procesar
            
        Returns:
            Lista de datos procesados y validados
        """
        processed = []
        seen_ids = set()
        
        for item in raw_data:
            try:
                # Validación básica obligatoria
                if not item.get('name') or not item.get('description'):
                    continue
                
                # Generar ID único si no existe
                item_id = item.get('id', self._generate_id(item['name']))
                
                # Evitar duplicados
                # if item_id in seen_ids:
                #     continue
                # seen_ids.add(item_id)
                
                # Estructura estandarizada
                processed_item = {
                    'id': item_id,
                    'name': str(item['name']).strip(),
                    'description': str(item['description']).strip(),
                    'type': item.get('type', 'destination'),
                    'location': self._standardize_location(item.get('location', {})),
                    'rating': float(item.get('rating', 0)) if item.get('rating') else None,
                    'source_info': {
                        'url': item.get('source_url', ''),
                        'reliability': self._calculate_source_reliability(item.get('source', 'unknown')),
                        'type': item.get('source', 'unknown'),
                        'last_updated': datetime.now().isoformat()
                    },
                    'metadata': {
                        'original_data': item,
                        'processed_at': datetime.now().isoformat()
                    }
                }
                
                processed.append(processed_item)
                
            except Exception as e:
                logger.warning(f"Error processing item '{item.get('name', 'unknown')}': {e}")
                continue
        
        logger.info(f"Processed {len(processed)} valid items from {len(raw_data)} raw items")
        return processed

    def _standardize_location(self, location_data: Any) -> Dict:
        """Estandariza datos de ubicación"""
        if isinstance(location_data, str):
            return {"name": location_data, "address": location_data, "coordinates": None}
        elif isinstance(location_data, dict):
            return {
                "name": location_data.get('name', ''),
                "address": location_data.get('address', location_data.get('name', '')),
                "coordinates": location_data.get('coordinates')
            }
        return {"name": "", "address": "", "coordinates": None}

    

    def _calculate_source_reliability(self, source: str) -> float:
        """Calcula confiabilidad basada en la fuente"""
        reliability_map = {
            'static_data': 0.9,
            'tripadvisor.com': 0.8,
            'habanacultural.ohc.cu': 0.7,
            'sitiosturisticos.es': 0.6,
            'cuba.travel': 0.8,
            'unknown': 0.5
        }

        if not isinstance(source, str):
            return 0.5

        return reliability_map.get(source.lower(), 0.5)

    def _generate_id(self, name: str) -> str:
        """Genera ID único basado en el nombre"""
        import re
        clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', name.lower())
        return '_'.join(clean_name.split())

    async def _update_vector_store(self, items: List[Dict]) -> None:
        """
        Actualiza el vector store con los nuevos datos.
        Recrea completamente el store para asegurar consistencia.
        """
        if not items:
            logger.warning("No items to update in vector store")
            return
            
        logger.info(f"Updating vector store with {len(items)} items...")
        
        try:
            # Crear nuevo vector store temporal
            temp_dir = os.path.join(self.data_dir, 'vectors_temp')
            temp_store = VectorStore(temp_dir)
            
            # Agrupar items por colección para mejor organización
            collections = {'museums': [], 'excursions': [], 'destinations': []}
            
            for item in items:
                collection_name = self._get_collection_name(item['type'])
                
                # Preparar texto para embedding
                location = item.get('location', {})
                location_name = location.get('name', '') if isinstance(location, dict) else str(location)
                
                text_parts = [
                    str(item.get('name', '')),
                    str(item.get('description', '')),
                    f"Tipo: {item.get('type', 'desconocido')}",
                    f"Ubicación: {location_name}"
                ]
                
                # Usamos un separador para que el modelo entienda mejor la estructura.
                text_for_embedding = " | ".join(filter(None, text_parts))

                logger.info(f"text_for_embedding: {text_for_embedding[:100]}...")
                
                # Preparar item para vector store
                vector_item = {
                    'id': item['id'],
                    'text': text_for_embedding,
                    'metadata': item
                }
                
                collections[collection_name].append(vector_item)
            
            # Almacenar cada colección
            for collection_name, collection_items in collections.items():
                if collection_items:
                    temp_store.add_texts(collection_name, collection_items)
                    logger.info(f"Added {len(collection_items)} items to {collection_name} collection")
            
            # Reemplazar vector store actual de forma atómica
            vectors_dir = os.path.join(self.data_dir, 'vectors')
            if os.path.exists(vectors_dir):
                backup_dir = os.path.join(self.data_dir, 'vectors_backup')
                if os.path.exists(backup_dir):
                    shutil.rmtree(backup_dir)
                shutil.move(vectors_dir, backup_dir)
            
            shutil.move(temp_dir, vectors_dir)
            
            # Actualizar referencia en TourismKB
            if self.tourism_kb:
                self.tourism_kb.vector_store = VectorStore(vectors_dir)
            
            for collection_name, collection_items in collections.items():
                self.tourism_kb.vector_store.store(collection_name, collection_items, regenerate_embeddings=True)
            
            logger.info("Vector store updated successfully")
            
        except Exception as e:
            logger.error(f"Error updating vector store: {str(e)}")
            # Restaurar backup si existe
            backup_dir = os.path.join(self.data_dir, 'vectors_backup')
            if os.path.exists(backup_dir):
                vectors_dir = os.path.join(self.data_dir, 'vectors')
                if os.path.exists(vectors_dir):
                    shutil.rmtree(vectors_dir)
                shutil.move(backup_dir, vectors_dir)
                logger.info("Restored vector store from backup")
            raise

    

    def _get_collection_name(self, item_type: str) -> str:
        """
        Mapea tipos de items a nombres de colecciones.
        
        Args:
            item_type: Tipo del item
            
        Returns:
            Nombre de la colección correspondiente
        """
        type_mapping = {
            'museum': 'museums', 
            'museo': 'museums',
            'gallery': 'museums',
            'galeria': 'museums',
            'excursion': 'excursions', 
            'tour': 'excursions',
            'trip': 'excursions',
            'viaje': 'excursions',
        }
        return type_mapping.get(item_type.lower(), 'destinations')

    async def _ensure_initial_data(self) -> None:
        """Asegura que hay datos iniciales en el vector store"""
        try:
            # Verificar si el vector store tiene datos
            vectors_dir = os.path.join(self.data_dir, 'vectors')
            if not os.path.exists(vectors_dir) or not os.listdir(vectors_dir):
                logger.info("No initial data found, creating initial dataset...")
                
                # Usar datos estáticos como base inicial
                static_data = self._get_static_tourism_data()
                processed_data = self._process_raw_data(static_data)
                await self._update_vector_store(processed_data)
                
                logger.info("Initial data created successfully")
            else:
                logger.info("Existing data found in vector store")
                
        except Exception as e:
            logger.error(f"Error ensuring initial data: {str(e)}")

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
