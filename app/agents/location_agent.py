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

# --- Agente de Ubicación ---
class LocationAgent(BaseAgent, ILocationAgent):
    """Agente BDI para extraer y geocodificar ubicaciones."""
    
    def __init__(self):
        super().__init__(AgentType.LOCATION)
        self.geolocator = Nominatim(user_agent="cuba_guide_bdi")
        self.coordinator = None

    def set_coordinator(self, coordinator):
        self.coordinator = coordinator

    def update_beliefs(self, context: AgentContext):
        super().update_beliefs(context)
        self.beliefs['response_text'] = context.response

    def generate_desires(self):
        self.desires = []
        if self.beliefs.get('response_text'):
            self.desires.append('find_and_geocode_locations')

    def generate_intentions(self):
        self.intentions = []
        if 'find_and_geocode_locations' in self.desires:
            self.intentions.append(self.intend_to_extract_and_geocode)

    async def intend_to_extract_and_geocode(self, context: AgentContext) -> AgentContext:
        self.logger.info("Executing intention: Extract and Geocode Locations.")
        if not self.beliefs.get('response_text'):
            return context
        locations = await self.extract_locations(self.beliefs['response_text'])
        geocoded_locations = []
        for loc in locations:
            coords = await self.get_coordinates(loc['name'])
            if coords:
                loc.update(coords)
                geocoded_locations.append(loc)
        context.locations = geocoded_locations
        return context

    async def extract_locations(self, text: str) -> List[Dict[str, Any]]:
        if not self.coordinator: return []
        llm_agent = self.coordinator.get_agent(AgentType.LLM)
        if not llm_agent: return []
        # CORRECCIÓN: Se usan dobles llaves para escapar el JSON en la f-string.
        prompt = f"From the text below, extract all Cuban place names (cities, beaches, museums, etc.). Respond ONLY with a JSON list of objects, like so: [{{'name': 'Varadero', 'type': 'beach'}}]. Text: '{text}'"
        response = await llm_agent.generate_response("You are a JSON-generating entity.", prompt)
        try:
            # Limpiar la respuesta del LLM para asegurar que sea un JSON válido
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            
            return json.loads(clean_response)
        except json.JSONDecodeError:
            self.logger.warning(f"Failed to decode JSON from LLM response for location extraction: {response}")
            return []

    async def get_coordinates(self, location: str) -> Optional[Dict[str, float]]:
        try:
            geo_loc = self.geolocator.geocode(f"{location}, Cuba", timeout=10)
            if geo_loc:
                return {"lat": geo_loc.latitude, "lon": geo_loc.longitude}
        except Exception as e:
            self.logger.warning(f"Geocoding failed for {location}: {e}")
        return None
