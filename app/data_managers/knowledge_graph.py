"""
Módulo para la gestión de un Grafo de Conocimiento (Knowledge Graph).
Utiliza networkx para modelar y persistir las relaciones entre entidades turísticas.
"""
import networkx as nx
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class KnowledgeGraph:
    """
    Gestiona la creación, persistencia y consulta de un grafo de conocimiento
    que relaciona entidades como lugares, ciudades, tipos de actividad, etc.
    """
    def __init__(self, graph_path: str):
        """
        Inicializa el gestor del grafo de conocimiento.

        Args:
            graph_path: Ruta al archivo donde se guardará el grafo (ej: 'data/kg.graphml').
        """
        self.graph_path = graph_path
        self.graph = nx.MultiDiGraph()  # Grafo dirigido que permite múltiples aristas
        self.load_graph()

    def load_graph(self):
        """Carga el grafo desde un archivo si existe."""
        if os.path.exists(self.graph_path):
            try:
                self.graph = nx.read_graphml(self.graph_path)
                logger.info(f"Knowledge Graph cargado desde {self.graph_path} con {self.graph.number_of_nodes()} nodos y {self.graph.number_of_edges()} aristas.")
            except Exception as e:
                logger.error(f"No se pudo cargar el Knowledge Graph: {e}")
        else:
            logger.info("No se encontró un Knowledge Graph existente. Se creará uno nuevo.")

    def save_graph(self):
        """Guarda el estado actual del grafo en un archivo."""
        try:
            nx.write_graphml(self.graph, self.graph_path)
            logger.info(f"Knowledge Graph guardado en {self.graph_path}")
        except Exception as e:
            logger.error(f"Error al guardar el Knowledge Graph: {e}")

    def add_entity(self, node_id: str, node_type: str, properties: Dict[str, Any]):
        """
        Añade una entidad (nodo) al grafo. Si ya existe, actualiza sus propiedades.
        """
        if not self.graph.has_node(node_id):
            self.graph.add_node(node_id, type=node_type, **properties)
        else:
            # Actualiza las propiedades del nodo existente
            nx.set_node_attributes(self.graph, {node_id: properties})

    def add_relationship(self, source_id: str, target_id: str, rel_type: str, properties: Dict[str, Any] = None):
        """
        Añade una relación (arista) entre dos entidades.
        """
        if self.graph.has_node(source_id) and self.graph.has_node(target_id):
            self.graph.add_edge(source_id, target_id, key=rel_type, type=rel_type, **(properties or {}))

    def build_from_data(self, items: List[Dict[str, Any]]):
        """
        Construye o actualiza el grafo a partir de una lista de datos procesados.
        """
        logger.info(f"Construyendo grafo desde {len(items)} items...")
        for item in items:
            try:
                item_id = item.get('id')
                item_name = item.get('name')
                item_type = item.get('type', 'desconocido')
                
                if not item_id or not item_name:
                    continue

                # Añadir la entidad principal
                self.add_entity(item_id, node_type=item_type, properties={'name': item_name, 'description': item.get('description', '')})

                # Relacionar con su tipo
                self.add_entity(item_type, node_type='EntityType', properties={'name': item_type.capitalize()})
                self.add_relationship(item_id, item_type, 'IS_A')

                # Relacionar con su ubicación
                location_info = item.get('location')
                if location_info and isinstance(location_info, dict):
                    loc_name = location_info.get('name')
                    if loc_name:
                        self.add_entity(loc_name, node_type='Location', properties={'name': loc_name})
                        self.add_relationship(item_id, loc_name, 'LOCATED_IN')

            except Exception as e:
                logger.warning(f"No se pudo procesar el item {item.get('id')} para el grafo: {e}")
        
        self.save_graph()

    def find_related_entities(self, node_id: str, depth: int = 1) -> List[Dict[str, Any]]:
        """
        Encuentra entidades relacionadas con un nodo hasta una profundidad dada.
        """
        if not self.graph.has_node(node_id):
            return []

        related_nodes = set()
        # Usamos una búsqueda en anchura (BFS) para encontrar vecinos
        queue = [(node_id, 0)]
        visited = {node_id}

        while queue:
            current_node, current_depth = queue.pop(0)
            if current_depth >= depth:
                continue

            for neighbor in self.graph.neighbors(current_node):
                if neighbor not in visited:
                    visited.add(neighbor)
                    edge_data = self.graph.get_edge_data(current_node, neighbor)
                    # Tomamos la primera relación si hay varias
                    rel_type = list(edge_data.keys())[0] if edge_data else 'RELATED_TO'
                    
                    node_data = self.graph.nodes[neighbor]
                    related_nodes.add(tuple({
                        'id': neighbor,
                        'name': node_data.get('name', neighbor),
                        'type': node_data.get('type', 'Unknown'),
                        'relationship': rel_type
                    }.items()))
                    queue.append((neighbor, current_depth + 1))
        
        return [dict(t) for t in related_nodes]

