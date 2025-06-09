"""
Agente especializado en ubicaciones y mapas.
"""
from typing import List, Dict, Any, Optional, Tuple
from .base_agent import BaseAgent
from .interfaces import ILocationAgent, AgentContext
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import folium
import re

class LocationAgent(BaseAgent, ILocationAgent):
    """Agente que maneja ubicaciones y mapas"""
    
    def __init__(self):
        """Inicializa el agente de ubicaciones"""
        super().__init__()
        self._geolocator = Nominatim(user_agent="cuba_tourism_guide")
        self._location_cache: Dict[str, Tuple[float, float]] = {}
        
        # Coordenadas conocidas como fallback
        self._known_locations = {
            "La Habana": (23.1136, -82.3666),
            "Santiago de Cuba": (20.0217, -75.8283),
            "Camagüey": (21.3808, -77.9169),
            "Holguín": (20.8872, -76.2631),
            "Santa Clara": (22.4067, -79.9647),
            "Bayamo": (20.3797, -76.6433),
            "Cienfuegos": (22.1492, -80.4469),
            "Pinar del Río": (22.4175, -83.6981),
            "Matanzas": (23.0511, -81.5772),
            "Ciego de Ávila": (21.8401, -78.7619),
            "Las Tunas": (20.9617, -76.9511),
            "Sancti Spíritus": (21.9269, -79.4425),
            "Guantánamo": (20.1453, -75.2061),
            "Artemisa": (22.8164, -82.7597),
            "Mayabeque": (22.9615, -82.1513)
        }
    
    async def geocode_location(self, name: str) -> Optional[Tuple[float, float]]:
        """
        Geocodifica una ubicación usando caché y fallback.
        """
        # Revisar caché
        if name in self._location_cache:
            return self._location_cache[name]
        
        # Revisar coordenadas conocidas
        if name in self._known_locations:
            self._location_cache[name] = self._known_locations[name]
            return self._known_locations[name]
            
        try:
            # Añadir "Cuba" para mejorar precisión
            location = self._geolocator.geocode(f"{name}, Cuba", timeout=10)
            if location:
                coords = (location.latitude, location.longitude)
                self._location_cache[name] = coords
                return coords
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            self.logger.error(f"Error geocoding {name}: {str(e)}")
        
        return None
    
    async def extract_locations(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrae ubicaciones del texto.
        """
        patterns = [
            (r"(?:ciudad de |municipio de |la ciudad |el municipio )?(?P<ciudad>La Habana|Santiago de Cuba|Camagüey|Holguín|Santa Clara|Bayamo|Cienfuegos|Pinar del Río|Matanzas|Ciego de Ávila|Las Tunas|Sancti Spíritus|Guantánamo|Artemisa|Mayabeque)", "ciudad"),
            (r"(?:museo|Museo) (?:de )?(?P<museo>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con))", "museo"),
            (r"(?:playa|Playa) (?:de )?(?P<playa>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con))", "playa"),
            (r"(?:hotel|Hotel) (?P<hotel>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con))", "hotel"),
            (r"(?:monumento|Monumento|fortaleza|Fortaleza|castillo|Castillo) (?:de )?(?P<monumento>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con))", "monumento")
        ]
        
        locations = []
        seen = set()
        
        for pattern, place_type in patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                for group_name, value in match.groupdict().items():
                    if value and value.strip() and value not in seen:
                        locations.append({
                            "name": value.strip(),
                            "type": place_type
                        })
                        seen.add(value)
        
        return locations
    
    async def create_map(self, locations: List[Dict[str, Any]]) -> Any:
        """
        Crea un mapa con las ubicaciones proporcionadas.
        """
        # Centro aproximado de Cuba
        center_lat, center_lon = 21.5, -79.5
        
        # Crear mapa base
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=7,
            tiles="OpenStreetMap"
        )
        
        # Colores por tipo de lugar
        color_map = {
            "ciudad": "red",
            "museo": "blue",
            "playa": "green",
            "hotel": "purple",
            "monumento": "orange",
            "lugar": "darkblue"
        }
        
        # Añadir marcadores
        for loc in locations:
            coords = await self.geocode_location(loc["name"])
            if coords:
                lat, lon = coords
                color = color_map.get(loc["type"].lower(), "gray")
                
                folium.Marker(
                    [lat, lon],
                    popup=folium.Popup(
                        f"<b>{loc['name']}</b><br>Tipo: {loc['type']}",
                        max_width=300
                    ),
                    tooltip=loc["name"],
                    icon=folium.Icon(color=color, icon='info-sign')
                ).add_to(m)
        
        return m
    
    async def _process_impl(self, context: AgentContext) -> AgentContext:
        """
        Procesa el contexto extrayendo y mapeando ubicaciones.
        """
        # Extraer ubicaciones del query y de la respuesta si existe
        query_locations = await self.extract_locations(context.query)
        
        response = context.metadata.get('llm_response', '')
        if response:
            response_locations = await self.extract_locations(response)
            # Combinar ubicaciones sin duplicados
            seen = {loc["name"] for loc in query_locations}
            for loc in response_locations:
                if loc["name"] not in seen:
                    query_locations.append(loc)
                    seen.add(loc["name"])
        
        if query_locations:
            # Crear mapa y guardarlo en metadata
            map_obj = await self.create_map(query_locations)
            context.metadata['locations_map'] = map_obj
            context.metadata['extracted_locations'] = query_locations
        
        return context
