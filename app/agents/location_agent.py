"""
Agente especializado en el manejo de ubicaciones y geocodificación.
"""
from typing import Dict, List, Optional, Any
import re
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from .interfaces import ILocationAgent, AgentContext, AgentType
from .base_agent import BaseAgent

class LocationAgent(BaseAgent, ILocationAgent):
    """
    Agente que maneja la extracción y geocodificación de ubicaciones.
    """
    
    def __init__(self):
        """Inicializa el agente de ubicaciones"""
        super().__init__(AgentType.LOCATION)
        self._geolocator = None
        self._location_cache: Dict[str, Dict[str, float]] = {}
        
        # Patrones para extraer ubicaciones
        self._location_patterns = [
            (r"(?:ciudad de |municipio de |la ciudad |el municipio )?(?P<ciudad>La Habana|Santiago de Cuba|Camagüey|Holguín|Santa Clara|Bayamo|Cienfuegos|Pinar del Río|Matanzas|Ciego de Ávila|Las Tunas|Sancti Spíritus|Guantánamo|Artemisa|Mayabeque)", "ciudad"),
            (r"(?:museo|Museo) (?:de )?(?P<museo>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con))", "museo"),
            (r"(?:playa|Playa) (?:de )?(?P<playa>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con))", "playa"),
            (r"(?:hotel|Hotel) (?P<hotel>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con))", "hotel"),
            (r"(?:monumento|Monumento|fortaleza|Fortaleza|castillo|Castillo) (?:de )?(?P<monumento>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con))", "monumento")
        ]
        
        # Coordenadas conocidas como fallback
        self._known_coordinates = {
            "La Habana": {"lat": 23.1136, "lon": -82.3666},
            "Santiago de Cuba": {"lat": 20.0217, "lon": -75.8283},
            "Camagüey": {"lat": 21.3808, "lon": -77.9169},
            "Holguín": {"lat": 20.8872, "lon": -76.2631},
            "Santa Clara": {"lat": 22.4067, "lon": -79.9647},
            "Bayamo": {"lat": 20.3797, "lon": -76.6433},
            "Cienfuegos": {"lat": 22.1492, "lon": -80.4469},
            "Pinar del Río": {"lat": 22.4175, "lon": -83.6981},
            "Matanzas": {"lat": 23.0511, "lon": -81.5772},
            "Ciego de Ávila": {"lat": 21.8401, "lon": -78.7619},
            "Las Tunas": {"lat": 20.9617, "lon": -76.9511},
            "Sancti Spíritus": {"lat": 21.9269, "lon": -79.4425},
            "Guantánamo": {"lat": 20.1453, "lon": -75.2061},
            "Artemisa": {"lat": 22.8164, "lon": -82.7597},
            "Mayabeque": {"lat": 22.9615, "lon": -82.1513}
        }
        
    async def initialize(self) -> None:
        """Inicializa el geocodificador"""
        self._geolocator = Nominatim(user_agent="cuba_tourism_guide")
        # Precarga las coordenadas conocidas en el caché
        self._location_cache.update(self._known_coordinates)
        
    async def process(self, context: AgentContext) -> AgentContext:
        """
        Procesa el contexto para extraer y geocodificar ubicaciones.
        """
        try:
            locations = []
            text_to_analyze = context.response or context.query
            
            # Primero intentamos extraer con LLM para mayor precisión
            llm_locations = await self.extract_locations_with_llm(text_to_analyze)
            if llm_locations:
                locations.extend(llm_locations)
                
            # Como fallback, usamos extracción basada en patrones
            if not locations:
                pattern_locations = await self.extract_locations(text_to_analyze)
                locations.extend(pattern_locations)
            
            # Geocodificar las ubicaciones encontradas
            geocoded_locations = []
            for location in locations:
                # Intentar obtener coordenadas primero del cache/conocidas
                if coords := await self.get_coordinates(location["name"]):
                    location.update(coords)
                    geocoded_locations.append(location)
                    
            # Actualizar contexto solo con ubicaciones que tienen coordenadas
            context.locations = geocoded_locations
            self.update_context_confidence(context, 0.9 if geocoded_locations else 0.5)
            return context
            
        except Exception as e:
            self.set_error(context, f"Error processing locations: {str(e)}")
            return context
            
    async def extract_locations(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrae ubicaciones mencionadas en un texto.
        """
        locations = []
        seen = set()
        
        for pattern, location_type in self._location_patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                for group_name, value in match.groupdict().items():
                    if value and value.strip() and value not in seen:
                        locations.append({
                            "name": value.strip(),
                            "type": location_type
                        })
                        seen.add(value)
        
        return locations
        
    async def get_coordinates(self, location: str) -> Optional[Dict[str, float]]:
        """
        Obtiene coordenadas para una ubicación usando caché o geocodificación.
        """
        # Revisar caché
        if location in self._location_cache:
            return self._location_cache[location]
            
        if not self._geolocator:
            return None
            
        try:
            # Geocodificar con contexto de Cuba
            result = self._geolocator.geocode(
                f"{location}, Cuba",
                timeout=10,
                exactly_one=True
            )
            
            if result:
                coords = {
                    "lat": result.latitude,
                    "lon": result.longitude
                }
                self._location_cache[location] = coords
                return coords
                
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            self.logger.warning(f"Geocoding failed for {location}: {str(e)}")
            
        return None
    
    async def extract_locations_with_llm(self, text: str) -> List[Dict[str, Any]]:
        """
        Usa LLM para extraer ubicaciones del texto de forma más precisa.
        
        Args:
            text: Texto de donde extraer ubicaciones
            
        Returns:
            Lista de ubicaciones extraídas con su tipo
        """
        system_prompt = """
        Eres un experto en identificar y extraer nombres de lugares en Cuba.
        Analiza el texto y extrae todas las ubicaciones mencionadas, clasificándolas por tipo.
        Formatea la respuesta como una lista JSON donde cada elemento tiene:
        - name: Nombre completo del lugar
        - type: Tipo de lugar (ciudad, museo, playa, hotel, monumento, lugar)
        Solo incluye lugares que estés seguro que existen en Cuba.
        """
        
        try:
            # Obtenemos agente LLM del coordinador
            llm_agent = await self.get_llm_agent()
            if not llm_agent:
                return []
                
            # Generamos respuesta con el LLM
            locations_text = await llm_agent.generate_response(
                system_prompt=system_prompt,
                user_prompt=text
            )
            
            # Intentamos parsear la respuesta como JSON
            try:
                import json
                locations = json.loads(locations_text)
                if isinstance(locations, list):
                    return locations
            except:
                self.logger.warning("No se pudo parsear la respuesta del LLM como JSON")
                return []
                
        except Exception as e:
            self.logger.error(f"Error extrayendo ubicaciones con LLM: {str(e)}")
            return []
        
    async def get_llm_agent(self) -> Optional['ILLMAgent']:
        """Gets the LLM agent from the coordinator if available"""
        if not hasattr(self, 'coordinator'):
            return None
        return self.coordinator.get_agent(AgentType.LLM)
