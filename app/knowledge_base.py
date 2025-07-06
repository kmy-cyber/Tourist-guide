"""
Base de conocimiento del sistema turístico.
Implementa una búsqueda híbrida combinando un VectorStore para la similitud
semántica y un KnowledgeGraph para la expansión de contexto relacional.
"""
import os
import logging
from typing import List, Dict, Any
from .data_managers.vector_store import VectorStore
from .data_managers.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)

class TourismKB:
    """
    Base de conocimiento híbrida que integra VectorStore y KnowledgeGraph.
    """

    def __init__(self, data_dir: str):
        """
        Inicializa la base de conocimiento.

        Args:
            data_dir: Directorio base donde se almacenan los datos.
        """
        self.vector_store = VectorStore(os.path.join(data_dir, 'vectors'))
        self.knowledge_graph = KnowledgeGraph(os.path.join(data_dir, 'kg.graphml'))

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Realiza una búsqueda híbrida:
        1. Usa el VectorStore para encontrar los resultados semánticamente más cercanos.
        2. Usa el KnowledgeGraph para expandir estos resultados con entidades relacionadas.
        """
        logger.info(f"Ejecutando búsqueda híbrida para: '{query}'")
        
        try:
            vector_results = self.vector_store.search(query=query, k=limit)
            logger.info(f"VectorStore encontró {len(vector_results)} resultados iniciales.")
        except Exception as e:
            logger.error(f"Error en la búsqueda del VectorStore: {e}")
            return []

        if not vector_results:
            return []

        final_results = []
        seen_ids = set()

        for result in vector_results:
            item_id = result.get('id')
            if not item_id or item_id in seen_ids:
                continue
            
            final_results.append(result)
            seen_ids.add(item_id)

            try:
                related_entities = self.knowledge_graph.find_related_entities(item_id, depth=1)
                logger.info(f"KnowledgeGraph encontró {len(related_entities)} entidades relacionadas para '{item_id}'.")
                
                for related in related_entities:
                    related_id = related.get('id')
                    if related_id not in seen_ids:
                        final_results.append({
                            "id": related_id,
                            "source": "knowledge_graph_expansion",
                            "data": {
                                "name": related.get('name'),
                                "description": f"Relacionado con {result.get('data', {}).get('name', 'N/A')} ({related.get('relationship')})",
                                "type": related.get('type'),
                                "location": {},
                                "source_info": {"type": "inferred"}
                            },
                            "similarity": result.get('similarity', 0) * 0.8
                        })
                        seen_ids.add(related_id)
            except Exception as e:
                logger.warning(f"Error al expandir el grafo para el nodo '{item_id}': {e}")

        final_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        
        # CORRECCIÓN: Devolver un número más generoso de resultados para asegurar que el grafo tenga datos.
        logger.info(f"Búsqueda híbrida completada con {len(final_results)} resultados totales.")
        return final_results[:15] # Devolver hasta 15 items para una visualización rica.

    def update_kb(self, items: List[Dict[str, Any]]):
        """
        Actualiza de forma coordinada el VectorStore y el KnowledgeGraph.
        """
        if not items:
            logger.warning("No hay items para actualizar la base de conocimiento.")
            return

        logger.info(f"Actualizando KB con {len(items)} items...")
        
        # 1. Procesar y añadir al VectorStore. Este método ahora estandariza
        #    y devuelve los datos procesados, listos para el grafo.
        processed_items = self.vector_store.add_items(items)
        if not processed_items:
            logger.error("VectorStore no procesó ningún item, la actualización del grafo se cancela.")
            return
        logger.info(f"VectorStore actualizado con {len(processed_items)} items.")

        # 2. Construir/Actualizar el KnowledgeGraph con los MISMOS datos procesados.
        #    Esto asegura que ambos componentes estén sincronizados.
        self.knowledge_graph.build_from_data(processed_items)
        logger.info("KnowledgeGraph actualizado con los datos procesados.")
