"""
Agente especializado en obtener y procesar información del clima.
"""
from typing import Optional, Dict, Any

from app.weather.weather import WeatherInfo
from .base_agent import BaseAgent
from .interfaces import IWeatherAgent, AgentContext, AgentType
from ..weather.weather_service import WeatherService

# --- Agente del Clima ---
class WeatherAgent(BaseAgent, IWeatherAgent):
    """Agente BDI para obtener información del clima."""
    
    def __init__(self):
        super().__init__(AgentType.WEATHER)
        self.weather_service = WeatherService()

    def update_beliefs(self, context: AgentContext):
        super().update_beliefs(context)
        self.beliefs['locations'] = context.locations

    def generate_desires(self):
        self.desires = []
        if self.beliefs.get('locations'):
            self.desires.append('fetch_weather_for_locations')

    def generate_intentions(self):
        self.intentions = []
        if 'fetch_weather_for_locations' in self.desires:
            self.intentions.append(self.intend_to_fetch_weather)

    async def intend_to_fetch_weather(self, context: AgentContext) -> AgentContext:
        self.logger.info("Executing intention: Fetch Weather.")
        weather_info = {}
        for loc in self.beliefs.get('locations', []):
            city_name = loc.get('name')
            if city_name:
                weather_dict = await self.get_weather(city_name)
                if weather_dict:
                    weather_info[city_name] = weather_dict
        context.weather_info = weather_info
        return context

    async def get_weather(self, location: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene el clima y se asegura de devolver un diccionario simple.
        """
        try:
            report: Optional[WeatherInfo] = await self.weather_service.get_weather_async(location)
            if report:
                # CORRECCIÓN: Convertir explícitamente el objeto WeatherInfo a un diccionario.
                return {
                    "city": report.city,
                    "current_temp": report.current_temp,
                    "feels_like": report.feels_like,
                    "description": report.description,
                    "humidity": report.humidity,
                    "wind_speed": report.wind_speed,
                    "timestamp": report.timestamp.isoformat()
                }
        except Exception as e:
            self.logger.warning(f"Could not get weather for {location}: {e}")
        return None
