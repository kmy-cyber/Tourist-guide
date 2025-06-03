from datetime import datetime
from typing import Optional
import logging
from .weather import WeatherAgent, WeatherInfo

logger = logging.getLogger(__name__)

class WeatherService:
    """Service class to handle weather-related API calls and processing"""
    
    def __init__(self):
        self.weather_agent = WeatherAgent()
        self.logger = logging.getLogger(__name__)

    def get_weather_report(self, city: str) -> Optional[str]:
        """
        Obtiene un reporte del clima formateado para una ciudad
        
        Args:
            city (str): Nombre de la ciudad en Cuba
            
        Returns:
            str: Reporte del clima formateado en HTML o None si no se encuentra la ciudad
        """
        self.logger.info(f"Solicitando reporte del clima para ciudad: {city}")
        try:
            # Obtener información del clima usando el agente
            weather_info = self.weather_agent.get_weather_info(city)
            
            if not weather_info:
                self.logger.warning(f"No se encontró información del clima para {city}")
                return None
                
            self.logger.info(f"Reporte del clima generado exitosamente para {city}")
            # Generar resumen amigable
            return self.weather_agent.generate_weather_summary(weather_info)
            
        except Exception as e:
            self.logger.error(f"Error obteniendo el reporte del clima para {city}: {e}")
            return None

    async def get_weather_async(self, city: str) -> Optional[str]:
        """Versión asíncrona del reporte del clima"""
        self.logger.info(f"[Async] Solicitando reporte del clima para ciudad: {city}")
        return self.get_weather_report(city)