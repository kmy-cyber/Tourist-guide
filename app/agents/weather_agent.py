"""
Agente especializado en información meteorológica.
"""
from typing import Optional
from .base_agent import BaseAgent
from .interfaces import IWeatherAgent, AgentContext
from ..weather.weather_service import WeatherService
import re

class WeatherAgent(BaseAgent, IWeatherAgent):
    """Agente que maneja información meteorológica"""
    
    def __init__(self):
        """Inicializa el agente del clima"""
        super().__init__()
        self.weather_service = WeatherService()
        
        # Lista de ciudades conocidas para detección
        self.known_cities = [
            "La Habana", "Santiago de Cuba", "Camagüey", "Holguín", 
            "Santa Clara", "Bayamo", "Cienfuegos", "Pinar del Río",
            "Matanzas", "Ciego de Ávila", "Las Tunas", "Sancti Spíritus",
            "Guantánamo", "Artemisa", "Mayabeque"
        ]
    
    def _extract_city(self, text: str) -> Optional[str]:
        """
        Extrae el nombre de una ciudad del texto si está presente.
        """
        text = text.lower()
        for city in self.known_cities:
            if city.lower() in text:
                return city
        return None
    
    async def get_weather(self, location: str) -> Optional[str]:
        """
        Obtiene la información del clima para una ubicación.
        
        Args:
            location: Nombre de la ubicación
            
        Returns:
            Información del clima formateada o None si no está disponible
        """
        try:
            weather_info = await self.weather_service.get_weather_async(location)
            if weather_info:
                return f"""### 🌤️ Clima en {location}
{weather_info}"""
            return None
        except Exception as e:
            self.logger.error(f"Error getting weather for {location}: {str(e)}")
            return None
    
    async def _process_impl(self, context: AgentContext) -> AgentContext:
        """
        Procesa el contexto buscando información meteorológica relevante.
        """
        # Extraer ciudad del contexto
        city = self._extract_city(context.query)
        
        if city:
            weather_info = await self.get_weather(city)
            if weather_info:
                # Guardar información del clima en metadata
                context.metadata['weather_info'] = weather_info
                context.sources.append(f"OpenWeather - {city}")
                context.confidence = max(context.confidence, 0.8)
        
        return context
