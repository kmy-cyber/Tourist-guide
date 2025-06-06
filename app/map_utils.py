"""
Utilidades para manejo de mapas y ubicaciones en la aplicación.
"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import folium
import re
import time
import logging

logger = logging.getLogger(__name__)

@dataclass
class Location:
    """Clase para representar una ubicación en el mapa."""
    name: str
    lat: float
    lon: float
    description: str = ""
    type: str = "lugar"

class MapManager:
    """Gestiona la creación y actualización de mapas interactivos."""
    
    def __init__(self):
        """Inicializa el gestor de mapas."""
        self.markers: List[Location] = []
        self.center_lat = 21.5  # Centro aproximado de Cuba
        self.center_lon = -79.5
        self._location_cache: Dict[str, Tuple[float, float]] = {}
        self._geolocator = Nominatim(user_agent="cuba_tourism_guide")

    def geocode_location(self, name: str) -> Optional[Tuple[float, float]]:
        """
        Geocodifica una ubicación usando Nominatim con caché.
        """
        # Revisar primero el caché
        if name in self._location_cache:
            return self._location_cache[name]
        
        try:
            # Añadir "Cuba" al query para mejorar precisión
            location = self._geolocator.geocode(f"{name}, Cuba", timeout=10)
            if location:
                coords = (location.latitude, location.longitude)
                self._location_cache[name] = coords
                return coords
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            logger.warning(f"Error geocoding {name}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error geocoding {name}: {str(e)}")
        
        return None

    def add_location(self, location: Location):
        """Añade una ubicación al mapa."""
        self.markers.append(location)

    def add_place(self, place_name: str, description: str = "", place_type: str = "lugar") -> bool:
        """
        Añade cualquier lugar al mapa usando geocodificación.
        """
        coords = self.geocode_location(place_name)
        if coords:
            lat, lon = coords
            self.add_location(Location(
                name=place_name,
                lat=lat,
                lon=lon,
                description=description,
                type=place_type
            ))
            return True
        return False

    def create_map(self) -> folium.Map:
        """Crea un mapa con las ubicaciones marcadas."""
        try:
            # Crear mapa centrado en Cuba
            m = folium.Map(
                location=[self.center_lat, self.center_lon],
                zoom_start=7,
                tiles="OpenStreetMap"
            )

            # Añadir marcadores para cada ubicación
            for marker in self.markers:
                # Color según el tipo de lugar
                color_map = {
                    "ciudad": "red",
                    "museo": "blue",
                    "playa": "green",
                    "hotel": "purple",
                    "monumento": "orange",
                    "lugar": "darkblue"
                }
                color = color_map.get(marker.type.lower(), "gray")
                
                folium.Marker(
                    [marker.lat, marker.lon],
                    popup=folium.Popup(
                        f"<b>{marker.name}</b><br>{marker.description}",
                        max_width=300
                    ),
                    tooltip=marker.name,
                    icon=folium.Icon(color=color, icon='info-sign')
                ).add_to(m)

            return m
            
        except Exception as e:
            logger.error(f"Error creating map: {str(e)}")
            return self._create_fallback_html()

    def _create_fallback_html(self) -> str:
        """Crea una representación HTML simple cuando no se puede crear el mapa."""
        locations = [f"• {marker.name} ({marker.type})" for marker in self.markers]
        return f"""
        <div style="padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
            <h3>📍 Ubicaciones mencionadas:</h3>
            <ul>{''.join([f'<li>{loc}</li>' for loc in locations])}</ul>
            <small>No se pudo cargar el mapa interactivo.</small>
        </div>
        """

def extract_locations_from_response(response: str) -> List[Dict[str, str]]:
    """
    Extrae ubicaciones mencionadas en la respuesta, identificando el tipo de lugar.
    """
    # Patrones para identificar diferentes tipos de lugares
    patterns = [
        (r"(?:ciudad de |municipio de |la ciudad |el municipio )?(?P<ciudad>La Habana|Santiago de Cuba|Camagüey|Holguín|Santa Clara|Bayamo|Cienfuegos|Pinar del Río|Matanzas|Ciego de Ávila|Las Tunas|Sancti Spíritus|Guantánamo|Artemisa|Mayabeque)", "ciudad"),
        (r"(?:museo|Museo) (?:de )?(?P<museo>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con))", "museo"),
        (r"(?:playa|Playa) (?:de )?(?P<playa>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con))", "playa"),
        (r"(?:hotel|Hotel) (?P<hotel>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con))", "hotel"),
        (r"(?:monumento|Monumento|fortaleza|Fortaleza|castillo|Castillo) (?:de )?(?P<monumento>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con))", "monumento")
    ]
    
    locations = []
    seen = set()  # Evitar duplicados
    
    for pattern, place_type in patterns:
        matches = re.finditer(pattern, response, re.MULTILINE)
        for match in matches:
            for group_name, value in match.groupdict().items():
                if value and value.strip() and value not in seen:
                    locations.append({
                        "name": value.strip(),
                        "type": place_type
                    })
                    seen.add(value)
    
    return locations
