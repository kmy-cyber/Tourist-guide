"""
Agente especializado en la interfaz de usuario.
Maneja la presentación de información, mapas y clima.
"""
import logging
from typing import Dict, List, Any, Optional
from app.weather.weather import WeatherInfo
import folium
from .interfaces import IUIAgent, AgentContext, AgentType
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# --- Agente de UI ---
class UIAgent(BaseAgent, IUIAgent):
    """Agente BDI para generar componentes de la interfaz de usuario."""
    
    def __init__(self):
        super().__init__(AgentType.UI)

    def update_beliefs(self, context: AgentContext):
        super().update_beliefs(context)
        self.beliefs['locations'] = context.locations
        self.beliefs['weather_info'] = context.weather_info

    def generate_desires(self):
        self.desires = []
        if self.beliefs.get('locations'):
            self.desires.append('create_map')
        if self.beliefs.get('weather_info'):
            self.desires.append('create_weather_cards')

    def generate_intentions(self):
        self.intentions = []
        if 'create_map' in self.desires:
            self.intentions.append(self.intend_to_create_map)
        if 'create_weather_cards' in self.desires:
            self.intentions.append(self.intend_to_create_weather_cards)

    async def intend_to_create_map(self, context: AgentContext) -> AgentContext:
        self.logger.info("Executing intention: Create Map.")
        map_html = await self.show_map(self.beliefs.get('locations', []))
        if map_html:
            context.ui_elements['map_html'] = map_html
        return context

    async def intend_to_create_weather_cards(self, context: AgentContext) -> AgentContext:
        self.logger.info("Executing intention: Create Weather Cards.")
        weather_html = await self.show_weather(self.beliefs.get('weather_info', {}))
        if weather_html:
            context.ui_elements['weather_html'] = weather_html
        return context

    async def show_map(self, locations: List[Dict[str, Any]]) -> Optional[str]:
        if not locations: return None
        # El tileset 'CartoDB positron' es neutro y funciona bien en ambos modos.
        # Para un modo oscuro verdadero, se podría usar 'CartoDB dark_matter'.
        m = folium.Map(location=[21.5, -79.5], zoom_start=6, tiles="CartoDB positron")
        for loc in locations:
            if loc and 'lat' in loc and 'lon' in loc:
                folium.Marker(
                    [loc['lat'], loc['lon']], 
                    popup=f"<b>{loc.get('name', 'Ubicación')}</b>",
                    tooltip=loc.get('name', '')
                ).add_to(m)
        return m._repr_html_()

    async def show_weather(self, weather_info: Dict[str, Any]) -> Optional[str]:
        """
        Genera el HTML para las tarjetas del clima usando variables de tema de Streamlit
        para adaptarse a los modos claro y oscuro.
        """
        if not weather_info: return None
        
        # CSS que utiliza las variables de tema de Streamlit
        style = """
        <style>
            .weather-card {
                background-color: var(--background-color);
                border: 1px solid var(--secondary-background-color);
                color: var(--text-color);
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 10px;
                font-family: var(--font);
            }
            .weather-city {
                font-weight: bold;
                font-size: 1.1em;
                color: var(--primary-color);
            }
            .weather-temp {
                font-size: 1.5em;
                margin: 5px 0;
            }
            .weather-desc {
                font-style: italic;
            }
            .weather-details {
                font-size: 0.9em;
                margin-top: 10px;
            }
        </style>
        """
        
        cards_html = ""
        for city, info in weather_info.items():
            temp = info.get('current_temp', 'N/A')
            desc = info.get('description', 'No disponible').capitalize()
            humidity = info.get('humidity', 'N/A')
            wind = info.get('wind_speed', 'N/A')
            
            emoji = "☀️"
            if "lluvia" in desc.lower() or "rain" in desc.lower(): emoji = "🌧️"
            elif "nube" in desc.lower() or "cloud" in desc.lower(): emoji = "☁️"
            elif "tormenta" in desc.lower() or "storm" in desc.lower(): emoji = "⛈️"

            cards_html += f"""
            <div class="weather-card">
                <div class="weather-city">{city} {emoji}</div>
                <div class="weather-temp">{temp}°C</div>
                <div class="weather-desc">{desc}</div>
                <div class="weather-details">
                    <span>💧 Humedad: {humidity}%</span> | <span>💨 Viento: {wind} km/h</span>
                </div>
            </div>
            """
        
        return f"<div>{style}{cards_html}</div>"
