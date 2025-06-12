"""
Agente especializado en obtener y procesar información del clima.
"""
from typing import Optional, Dict, Any
from .base_agent import BaseAgent
from .interfaces import IWeatherAgent, AgentContext, AgentType
from ..weather.weather_service import WeatherService

class WeatherAgent(BaseAgent, IWeatherAgent):
    """Agente que maneja la información del clima"""
    
    def __init__(self):
        """Inicializa el agente del clima"""
        super().__init__(AgentType.WEATHER)
        self.weather_service = WeatherService()
        
    async def process(self, context: AgentContext) -> AgentContext:
        """
        Procesa el contexto para obtener información del clima.
        
        Args:
            context: Contexto actual
            
        Returns:
            Contexto actualizado con información del clima
        """
        try:
            # Obtener información del clima para cada ubicación
            for location in context.locations:
                weather_info = await self.get_weather(location["name"])
                if weather_info:
                    context.weather_info[location["name"]] = weather_info
                    self.add_source(context, f"OpenWeather - {location['name']}")
            
            if context.weather_info:
                self.update_context_confidence(context, 0.8, weight=0.3)
            
            return context
            
        except Exception as e:
            self.set_error(context, f"Error getting weather: {str(e)}")
            return context
            
    async def get_weather(self, location: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene información del clima para una ubicación.
        
        Args:
            location: Nombre de la ubicación
            
        Returns:
            Información del clima o None si no se encuentra
        """
        try:
            if weather_report := await self.weather_service.get_weather_async(location):
                return {
                    "ciudad": location,
                    "report": weather_report
                }
        except Exception as e:
            self.logger.warning(f"Error getting weather for {location}: {str(e)}")
            
        return None
