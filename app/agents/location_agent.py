"""
Agente especializado en el manejo de ubicaciones y geocodificación.
"""
from typing import Dict, List, Optional, Any, Tuple
import re
import json
import asyncio
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
        self.coordinator = None  # Referencia al coordinador para acceder a otros agentes
        
        # Patrones mejorados para extraer ubicaciones como fallback
        self._location_patterns = [
            (r"(?i)(?:ciudad de |municipio de |la ciudad |el municipio )?(?P<ciudad>La Habana|Habana|Santiago de Cuba|Camagüey|Holguín|Santa Clara|Bayamo|Cienfuegos|Pinar del Río|Matanzas|Ciego de Ávila|Las Tunas|Sancti Spíritus|Guantánamo|Artemisa|Mayabeque|Trinidad|Varadero|Viñales)", "ciudad"),
            (r"(?i)(?:museo|Museo) (?:de |del |la )?(?P<museo>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con|ubicado|situado))", "museo"),
            (r"(?i)(?:playa|Playa) (?:de |del |la )?(?P<playa>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con|ubicada|situada))", "playa"),
            (r"(?i)(?:hotel|Hotel) (?P<hotel>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con|ubicado|situado))", "hotel"),
            (r"(?i)(?:monumento|Monumento|fortaleza|Fortaleza|castillo|Castillo|catedral|Catedral|iglesia|Iglesia) (?:de |del |la )?(?P<monumento>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con|ubicado|situado))", "monumento"),
            (r"(?i)(?:parque|Parque) (?:Nacional |nacional )?(?:de |del |la )?(?P<parque>[A-ZÁ-Úa-zá-ú\s]+?)(?=[\.,]|\s(?:es|está|se|que|y|o|en|con|ubicado|situado))", "parque")
        ]
        
        # Coordenadas conocidas para lugares principales de Cuba
        self._known_coordinates = {
            "La Habana": {"lat": 23.1136, "lon": -82.3666},
            "Habana": {"lat": 23.1136, "lon": -82.3666},
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
            "Mayabeque": {"lat": 22.9615, "lon": -82.1513},
            "Trinidad": {"lat": 21.8019, "lon": -79.9847},
            "Varadero": {"lat": 23.1542, "lon": -81.2537},
            "Viñales": {"lat": 22.6167, "lon": -83.7083}
        }
        
    def set_coordinator(self, coordinator):
        """Establece la referencia al coordinador"""
        self.coordinator = coordinator
        
    async def initialize(self) -> None:
        """Inicializa el geocodificador"""
        try:
            self._geolocator = Nominatim(
                user_agent="cuba_tourism_guide_v2",
                timeout=10
            )
            # Precarga las coordenadas conocidas en el caché
            self._location_cache.update(self._known_coordinates)
            self.logger.info("LocationAgent initialized with geocoder and coordinate cache")
            self.logger.info(f"Preloaded {len(self._location_cache)} known coordinates")
        except Exception as e:
            self.logger.error(f"Failed to initialize geolocator: {str(e)}")
            self.logger.info("Will use coordinate cache only")
            # Aún podemos usar las coordenadas conocidas
            self._location_cache.update(self._known_coordinates)
        
    async def process(self, context: AgentContext) -> AgentContext:
        """
        Procesa el contexto para extraer y geocodificar ubicaciones.
        """
        try:
            # Usamos la respuesta generada por el LLM como fuente principal
            text_to_analyze = context.response or context.query
            
            if not text_to_analyze.strip():
                self.logger.warning("No text available for location extraction")
                return context
                
            self.logger.info(f"Extracting locations from: {text_to_analyze[:100]}...")
            
            # 1. Extracción principal con LLM (más precisa)
            locations = await self.extract_locations_with_llm(text_to_analyze)
            
            # 2. Geocodificar todas las ubicaciones encontradas
            geocoded_locations = []
            if locations:
                geocoded_locations = await self.geocode_locations(locations)
            
            # 3. Actualizar contexto
            context.locations = geocoded_locations
            
            # Calcular confianza basada en el éxito de la geocodificación
            confidence = 0.9 if geocoded_locations else (0.6 if locations else 0.3)
            self.update_context_confidence(context, confidence)
            
            self.logger.info(f"Found {len(geocoded_locations)} geocoded locations")
            return context
            
        except Exception as e:
            error_msg = f"Error processing locations: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.set_error(context, error_msg)
            return context
    
    async def extract_locations_with_llm(self, text: str) -> List[Dict[str, Any]]:
        """
        Usa LLM para extraer ubicaciones del texto de forma más precisa.
        
        Args:
            text: Texto de donde extraer ubicaciones
            
        Returns:
            Lista de ubicaciones extraídas con su tipo
        """
        if not self.coordinator:
            self.logger.warning("No coordinator available for LLM extraction")
            return []
            
        llm_agent = self.coordinator.get_agent(AgentType.LLM)
        if not llm_agent:
            self.logger.warning("No LLM agent available for location extraction")
            return []

        try:
            # Construir un prompt específico para extracción de ubicaciones
            system_prompt = """Eres un asistente experto en identificar ubicaciones en Cuba.
Tu tarea es extraer todas las ubicaciones mencionadas en el texto y clasificarlas por tipo.
Devuelve solo un array JSON con el siguiente formato para cada ubicación encontrada:
[{"name": "nombre de la ubicación", "type": "tipo de ubicación"}]

Los tipos de ubicación pueden ser:
- ciudad: ciudades y municipios
- playa: playas y balnearios
- museo: museos y galerías
- hotel: hoteles y alojamientos
- monumento: monumentos históricos, fortalezas, castillos, iglesias
- parque: parques naturales o urbanos
- otro: otros lugares de interés

Solo incluye ubicaciones que existen en Cuba y asegúrate de que el nombre sea específico.
Si el texto no menciona ninguna ubicación, devuelve un array vacío []."""

            # Generar respuesta con el LLM
            response = await llm_agent.generate_response(
                system_prompt=system_prompt,
                user_prompt=text
            )

            # Intentar parsear la respuesta JSON
            try:
                if response.strip().startswith('[') and response.strip().endswith(']'):
                    locations = json.loads(response)
                    if isinstance(locations, list):
                        # Filtrar y validar cada ubicación
                        validated_locations = []
                        for loc in locations:
                            if isinstance(loc, dict) and 'name' in loc and 'type' in loc:
                                name = loc['name'].strip()
                                if len(name) > 2:  # Evitar nombres muy cortos
                                    validated_locations.append({
                                        'name': name,
                                        'type': loc['type'].lower()
                                    })
                        
                        self.logger.info(f"LLM extraction found {len(validated_locations)} locations")
                        return validated_locations
            except json.JSONDecodeError as e:
                self.logger.error(f"Error parsing LLM response as JSON: {str(e)}")
            except Exception as e:
                self.logger.error(f"Error processing LLM response: {str(e)}")

            # Si algo falla, usar extracción por patrones como fallback
            self.logger.info("Falling back to pattern-based extraction")
            return await self.extract_locations(text)

        except Exception as e:
            self.logger.error(f"Error in LLM location extraction: {str(e)}")
            return await self.extract_locations(text)
    
    async def extract_locations(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrae ubicaciones usando patrones de regex como fallback.
        
        Args:
            text: Texto de donde extraer ubicaciones
            
        Returns:
            Lista de ubicaciones extraídas
        """
        locations = []
        seen = set()
        
        for pattern, location_type in self._location_patterns:
            matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                for group_name, value in match.groupdict().items():
                    if value and value.strip():
                        name = value.strip()
                        # Evitar duplicados y nombres muy cortos
                        if name not in seen and len(name) > 2:
                            locations.append({
                                "name": name,
                                "type": location_type
                            })
                            seen.add(name)
        
        self.logger.info(f"Pattern extraction found {len(locations)} locations")
        return locations
    
    async def geocode_locations(self, locations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Geocodifica una lista de ubicaciones de manera eficiente.
        
        Args:
            locations: Lista de ubicaciones a geocodificar
            
        Returns:
            Lista de ubicaciones con coordenadas
        """
        geocoded_locations = []
        
        # Procesar ubicaciones en lotes para mejorar eficiencia
        for location in locations:
            coords = await self.get_coordinates(location["name"])
            if coords:
                location.update(coords)
                geocoded_locations.append(location)
                self.logger.info(f"Geocoded: {location['name']} -> {coords}")
            else:
                self.logger.warning(f"Failed to geocode: {location['name']}")
                
        return geocoded_locations
        
    # Helper methods for get_coordinates
    def _check_cache(self, location_key: str) -> Optional[Dict[str, float]]:
        """Check location cache including common variants"""
        variants = [
            location_key,
            location_key.replace("La Habana", "Habana"),
            location_key.replace("Habana", "La Habana")
        ]
        
        for variant in variants:
            if variant in self._location_cache:
                self.logger.debug(f"Cache hit for variant '{variant}' of '{location_key}'")
                coords = self._location_cache[variant]
                self._location_cache[location_key] = coords  # Cache original variant
                return coords
        return None

    def _check_known_locations(self, location_key: str) -> Optional[Dict[str, float]]:
        """Check against known location coordinates with fuzzy matching"""
        for known_location, coords in self._known_coordinates.items():
            if (known_location.lower() in location_key.lower() or 
                location_key.lower() in known_location.lower()):
                self.logger.info(f"Fuzzy match: '{location_key}' -> '{known_location}'")
                self._location_cache[location_key] = coords
                return coords
        return None

    def _store_geocoding_result(self, location_key: str, error_msg: Optional[str] = None, 
                              result: Optional[Any] = None, coords: Optional[Dict[str, float]] = None):
        """Store geocoding result or failure in cache"""
        details = {
            "name": location_key,
            "city": None,
            "region": None,
            "country": "Cuba",
            "address": None,
            "coordinates": coords,
            "geocoding_attempted": True,
            "geocoding_error": error_msg
        }
        
        if result and hasattr(result, 'raw'):
            details.update({
                "name": result.raw.get("name", location_key),
                "city": result.raw.get("city"),
                "region": result.raw.get("state"),
                "address": result.address,
            })
        
        self._location_cache[location_key] = details

    def _is_valid_cuba_coords(self, coords: Dict[str, float]) -> bool:
        """Verify coordinates are within Cuba's bounding box"""
        return (19.0 <= coords["lat"] <= 24.0 and 
                -85.0 <= coords["lon"] <= -74.0)

    async def _try_geocode_query(self, query: str, location_key: str) -> Tuple[Optional[Dict[str, float]], Optional[str]]:
        """Try to geocode a single query"""
        try:
            self.logger.debug(f"Geocoding query: {query}")
            result = self._geolocator.geocode(
                query,
                timeout=15,
                exactly_one=True,
                country_codes=['cu']
            )
            
            if result:
                coords = {
                    "lat": round(result.latitude, 6),
                    "lon": round(result.longitude, 6)
                }
                
                if self._is_valid_cuba_coords(coords):
                    self._location_cache[location_key] = coords
                    self.logger.info(f"Successfully geocoded: {location_key}")
                    self._store_geocoding_result(location_key, result=result, coords=coords)
                    return coords, None
                error_msg = f"Coordinates outside Cuba: {coords}"
                self.logger.warning(f"{error_msg} for {location_key}")
                return None, error_msg
                    
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            error_msg = f"Geocoding timeout/unavailable: {str(e)}"
            self.logger.debug(f"{error_msg} for query '{query}'")
            return None, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(f"{error_msg} geocoding {location_key}")
            return None, error_msg
        
        return None, "No results found"

    async def get_coordinates(self, location: str) -> Optional[Dict[str, float]]:
        """
        Obtiene coordenadas para una ubicación usando caché o geocodificación.
        
        Args:
            location: Nombre de la ubicación a geocodificar
            
        Returns:
            Dict con lat/lon si se encuentra, None si no
        """
        if not location or not isinstance(location, str):
            return None

        location_key = location.strip()
        if not location_key:
            return None

        # 1. Check cache
        if coords := self._check_cache(location_key):
            return coords

        # 2. Check known locations if no geocoder
        if not self._geolocator:
            self.logger.warning(f"No geolocator available for: {location_key}")
            return self._check_known_locations(location_key)

        # 3. Try geocoding with variants
        search_queries = [
            f"{location_key}, Cuba",
            f"{location_key}, La Habana, Cuba" if "Habana" not in location_key else f"{location_key}, Cuba",
            location_key
        ]
        
        last_error = None
        for query in search_queries:
            coords, error = await self._try_geocode_query(query, location_key)
            if coords:
                return coords
            last_error = error

        # Store failed attempt
        self._store_geocoding_result(location_key, error_msg=last_error)
        self.logger.warning(f"Failed to geocode: {location_key}")
        return None