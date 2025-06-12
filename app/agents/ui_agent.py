"""
Agente especializado en la interfaz de usuario.
Maneja la presentación de información, mapas y clima.
"""
from typing import Dict, List, Any, Optional
import folium
from .interfaces import IUIAgent, AgentContext, AgentType
from .base_agent import BaseAgent

class UIAgent(BaseAgent, IUIAgent):
    """
    Agente que maneja la presentación de información en la interfaz.
    """
    
    def __init__(self):
        """Inicializa el agente de UI"""
        super().__init__(AgentType.UI)
        self.map_center = (21.5, -79.5)  # Centro aproximado de Cuba
        self.map_zoom = 7
        
        # Configuración de colores para tipos de lugares
        self.marker_colors = {
            "ciudad": "red",
            "museo": "blue",
            "playa": "green",
            "hotel": "purple",
            "monumento": "orange",
            "lugar": "darkblue"
        }
        
    async def process(self, context: AgentContext) -> AgentContext:
        """
        Procesa el contexto para actualizar la UI.
        """
        try:
            # Mostrar información del clima si está disponible
            if context.weather_info:
                weather_html = await self.show_weather(context.weather_info)
                if weather_html:
                    context.metadata["weather_html"] = weather_html
                
            # Mostrar mapa si hay ubicaciones
            if context.locations:
                map_html = await self.show_map(context.locations)
                if map_html:
                    context.metadata["map_html"] = map_html
            
            self.update_context_confidence(context, 0.9 if context.locations or context.weather_info else 0.5)
            return context
            
        except Exception as e:
            self.set_error(context, f"Error updating UI: {str(e)}")
            return context
            
    def create_map(self) -> folium.Map:
        """
        Crea un nuevo mapa base de Cuba.
        """
        return folium.Map(
            location=self.map_center,
            zoom_start=self.map_zoom,
            tiles="CartoDB positron",  # Estilo más limpio y moderno
            prefer_canvas=True,  # Mejor rendimiento
            control_scale=True,  # Añadir escala
            width="100%",
            height="100%"
        )
        
    async def show_map(self, locations: List[Dict[str, Any]]) -> Optional[str]:
        """
        Muestra un mapa con las ubicaciones especificadas.
        """
        try:
            m = self.create_map()
            
            for location in locations:
                if "lat" not in location or "lon" not in location:
                    continue
                    
                # Obtener color según tipo
                color = self.marker_colors.get(
                    location.get("type", "lugar").lower(),
                    "gray"
                )
                  # Crear popup con información
                popup_html = f"""
                <div style="
                    min-width: 250px;
                    font-family: system-ui, -apple-system, sans-serif;
                    padding: 1rem;
                ">
                    <h4 style="
                        margin: 0 0 0.5rem 0;
                        color: #1a73e8;
                        font-size: 1.2rem;
                    ">{location["name"]}</h4>
                    <p style="
                        margin: 0.5rem 0;
                        padding: 0.3rem 0.6rem;
                        background: #f0f3f9;
                        border-radius: 4px;
                        font-size: 0.9rem;
                    "><strong>Tipo:</strong> {location.get("type", "Lugar")}</p>
                    {f'<p style="margin: 0.5rem 0; line-height: 1.4;">{location.get("description", "")}</p>' if "description" in location else ""}
                </div>
                """
                
                # Añadir marcador
                folium.Marker(
                    [location["lat"], location["lon"]],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=location["name"],
                    icon=folium.Icon(color=color, icon='info-sign')
                ).add_to(m)
            
            # El mapa se retorna como HTML y Streamlit lo mostrará
            return m._repr_html_()
            
        except Exception as e:
            self.logger.error(f"Error showing map: {str(e)}")
            return self.create_fallback_html(locations)
            
    def create_fallback_html(self, locations: List[Dict[str, Any]]) -> str:
        """
        Crea una representación HTML simple cuando el mapa no está disponible.
        """
        location_list = [
            f"• {loc['name']} ({loc.get('type', 'lugar')})"
            for loc in locations
        ]
        return f"""
        <div style="padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
            <h3>📍 Ubicaciones mencionadas:</h3>
            <ul>{''.join([f'<li>{loc}</li>' for loc in location_list])}</ul>
            <small>Instala folium para ver el mapa interactivo: <code>pip install folium</code></small>
        </div>
        """
        
    async def show_weather(self, weather_info: Dict[str, Any]) -> Optional[str]:
        """
        Muestra información del clima formateada.
        """
        if not weather_info:
            return None
            
        ciudad = weather_info.get("ciudad", "")
        descripcion = weather_info.get("descripcion", "")
        temperatura = weather_info.get("temperatura", "")
        humedad = weather_info.get("humedad", "")
        viento = weather_info.get("viento", "")
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
