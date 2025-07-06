"""
Agente especializado en la interfaz de usuario.
Maneja la presentación de información, mapas y clima.
"""
import logging
from typing import Dict, List, Any, Optional
from app.weather.weather import WeatherInfo
import folium
from pyvis.network import Network
from .interfaces import IUIAgent, AgentContext, AgentType
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# --- Agente de UI (con Grafo de Conocimiento Mejorado) ---
class UIAgent(BaseAgent, IUIAgent):
    """Agente BDI para generar componentes de la interfaz de usuario."""
    
    def __init__(self):
        super().__init__(AgentType.UI)

    def update_beliefs(self, context: AgentContext):
        super().update_beliefs(context)
        self.beliefs['locations'] = context.locations
        self.beliefs['weather_info'] = context.weather_info
        self.beliefs['knowledge'] = context.knowledge
        self.beliefs['query'] = context.query

    def generate_desires(self):
        self.desires = []
        if self.beliefs.get('locations'): self.desires.append('create_map')
        if self.beliefs.get('weather_info'): self.desires.append('create_weather_cards')
        if self.beliefs.get('knowledge'): self.desires.append('create_knowledge_graph')

    def generate_intentions(self):
        self.intentions = []
        if 'create_map' in self.desires: self.intentions.append(self.intend_to_create_map)
        if 'create_weather_cards' in self.desires: self.intentions.append(self.intend_to_create_weather_cards)
        if 'create_knowledge_graph' in self.desires: self.intentions.append(self.intend_to_create_knowledge_graph)

    async def intend_to_create_map(self, context: AgentContext) -> AgentContext:
        map_html = await self.show_map(self.beliefs.get('locations', []))
        if map_html: context.ui_elements['map_html'] = map_html
        return context

    async def intend_to_create_weather_cards(self, context: AgentContext) -> AgentContext:
        weather_html = await self.show_weather(self.beliefs.get('weather_info', {}))
        if weather_html: context.ui_elements['weather_html'] = weather_html
        return context

    async def intend_to_create_knowledge_graph(self, context: AgentContext) -> AgentContext:
        graph_html = await self.show_knowledge_graph(self.beliefs.get('knowledge', []), self.beliefs.get('query'))
        if graph_html: context.ui_elements['knowledge_graph_html'] = graph_html
        return context

    async def show_map(self, locations: List[Dict[str, Any]]) -> Optional[str]:
        if not locations: return None
        m = folium.Map(location=[21.5, -79.5], zoom_start=6, tiles="CartoDB positron")
        for loc in locations:
            if loc and 'lat' in loc and 'lon' in loc:
                folium.Marker([loc['lat'], loc['lon']], popup=f"<b>{loc.get('name')}</b>", tooltip=loc.get('name')).add_to(m)
        return m._repr_html_()

    async def show_weather(self, weather_info: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """
        Muestra información del clima formateada. Ahora espera un diccionario de diccionarios.
        """
        if not weather_info:
            return None
        
        weather_html = ""
        for city, info in weather_info.items():
            # Pasa el diccionario 'info' a la función de renderizado
            city_html = await self.show_weather_info(info)
            if city_html:
                weather_html += f"<div style='margin-bottom: 1rem;'>{city_html}</div>"
        
        if not weather_html:
            return None
        
        return f"<div>{weather_html}</div>"

    async def show_weather_info(self, weather_info: Dict[str, Any]) -> Optional[str]:
        """
        Muestra información del clima formateada a partir de un diccionario.
        """
        if not weather_info:
            return None
                
        # CORRECCIÓN: Usar .get() para acceder a los datos del diccionario
        ciudad = weather_info.get('city', 'N/A')
        descripcion = weather_info.get('description', 'No disponible')
        temperatura = weather_info.get('current_temp', 'N/A')
        humedad = weather_info.get('humidity', 'N/A')
        viento = weather_info.get('wind_speed', 'N/A')

        # Get weather emoji based on description
        weather_emoji = "🌤️"  # default
        if descripcion:
            desc_lower = descripcion.lower()
            if "lluv" in desc_lower or "precip" in desc_lower:
                weather_emoji = "🌧️"
            elif "nub" in desc_lower or "nublad" in desc_lower:
                weather_emoji = "☁️"
            elif "sol" in desc_lower or "desp" in desc_lower:
                weather_emoji = "☀️"
            elif "torm" in desc_lower:
                weather_emoji = "⛈️"
                
        weather_html = f"""
        <div style="
            padding: 1.5rem;
            border-radius: 10px;
            background: linear-gradient(135deg, #00B4DB, #0083B0);
            color: white;
            font-family: system-ui, -apple-system, sans-serif;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        ">
            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1rem;
            ">
                <h3 style="margin: 0; font-size: 1.5rem;">{weather_emoji} {ciudad}</h3>
                <span style="font-size: 2rem; font-weight: bold;">{temperatura}°C</span>
            </div>
            <p style="
                margin: 0.5rem 0;
                padding: 0.5rem;
                background: rgba(255,255,255,0.1);
                border-radius: 5px;
            ">{descripcion}</p>
            <div style="
                display: flex;
                justify-content: space-around;
                margin-top: 1rem;
                text-align: center;
            ">
                <div>
                    <div style="font-size: 1.5rem;">💧</div>
                    <div style="font-size: 0.9rem;">Humedad</div>
                    <div style="font-weight: bold;">{humedad}%</div>
                </div>
                <div>
                    <div style="font-size: 1.5rem;">🌬️</div>
                    <div style="font-size: 0.9rem;">Viento</div>
                    <div style="font-weight: bold;">{viento} km/h</div>
                </div>
            </div>
        </div>
        """
        
        return weather_html
    
    async def show_knowledge_graph(self, knowledge_items: List[Dict[str, Any]], query: str) -> Optional[str]:
        """
        Genera un grafo de conocimiento interactivo con una lógica de construcción corregida y robusta.
        """
        if not knowledge_items:
            self.logger.warning("No se recibieron items de conocimiento para construir el grafo.")
            return None

        self.logger.info(f"Construyendo grafo con {len(knowledge_items)} items de conocimiento.")

        try:
            net = Network(height="510px", width="100%", notebook=True, cdn_resources='in_line', directed=True)
            net.set_options("""
            var options = {
              "nodes": {
                "font": { "color": "var(--text-color)", "strokeWidth": 3, "strokeColor": "var(--background-color)" },
                "scaling": { "min": 15, "max": 35 },
                "shape": "dot"
              },
              "edges": {
                "color": { "inherit": "to", "opacity": 0.5 },
                "smooth": { "type": "dynamic" }
              },
              "physics": { "enabled": true, "barnesHut": { "gravitationalConstant": -8000 } }
            }
            """)

            net.add_node(query, label=query, size=35, color="#FF5733", title=f"Consulta: '{query}'")
            added_nodes = {query}

            for item in knowledge_items:
                # CORRECCIÓN: Extraer los datos de la clave 'metadata' en lugar de 'data'.
                data = item.get('metadata')
                if not isinstance(data, dict):
                    self.logger.warning(f"Item de conocimiento saltado por formato de 'metadata' incorrecto: {item}")
                    continue

                item_id = data.get('id', data.get('name'))
                item_name = data.get('name')
                item_type = data.get('type', 'desconocido')
                
                if not item_id or not item_name:
                    continue

                if item_id not in added_nodes:
                    net.add_node(item_id, label=item_name, title=f"Tipo: {item_type}", group=item_type, size=20)
                    added_nodes.add(item_id)
                
                net.add_edge(query, item_id, title="resultado de")

                location_info = data.get('location')
                if isinstance(location_info, dict) and (loc_name := location_info.get('name')):
                    if loc_name not in added_nodes:
                        net.add_node(loc_name, label=loc_name, title="Ubicación", group="location", shape="box", color="#4169E1", size=15)
                        added_nodes.add(loc_name)
                    net.add_edge(item_id, loc_name, title="ubicado en")

            self.logger.info(f"Grafo de conocimiento creado con {len(net.nodes)} nodos y {len(net.edges)} aristas.")
            return net.generate_html(name='knowledge_graph.html', local=True)

        except Exception as e:
            self.logger.error(f"Falló la creación del grafo de conocimiento: {e}", exc_info=True)
            return None
