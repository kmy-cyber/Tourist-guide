import requests
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging
import os

logger = logging.getLogger(__name__)

class WeatherInfo:
    def __init__(self, city: str, data: Dict):
        self.city = city
        self.current_temp = data['main']['temp']
        self.feels_like = data['main']['feels_like']
        self.description = data['weather'][0]['description']
        self.humidity = data['main']['humidity']
        self.wind_speed = data['wind']['speed']
        self.timestamp = datetime.fromtimestamp(data['dt'])
    
class WeatherAgent:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('OPENWEATHER_API_KEY', 'aa312bf7e5f2def3551a65b859f5e3ad')
        self.weather_url = 'https://api.openweathermap.org/data/2.5/weather'
        
    def get_weather_info(self, city: str) -> Optional[WeatherInfo]:
        """
        Obtiene información del clima actual para una ciudad
        
        Args:
            city (str): Nombre de la ciudad
            
        Returns:
            WeatherInfo object o None si no se encuentra la ciudad
        """
        logger.info(f"Solicitando información del clima para ciudad: {city}")
        try:
            data = self._get_current_weather(city)
            if not data:
                return None
            return WeatherInfo(city, data)
        except Exception as e:
            logger.error(f"Error obteniendo el clima para {city}: {e}")
            return None

    def _get_current_weather(self, city: str) -> Optional[Dict]:
        """Obtiene el clima actual de la API de OpenWeather"""
        try:
            response = requests.get(
                self.weather_url,
                params={
                    "q": f"{city},CU",
                    "appid": self.api_key,
                    "units": "metric",
                    "lang": "es"
                },
                timeout=10  # Aumentamos el timeout a 10 segundos
            )
            
            if response.status_code != 200:
                logger.error(f"Error HTTP al obtener clima: {response.status_code} - {response.text}")
                return None
                
            return response.json()
            
        except requests.Timeout:
            logger.error(f"Timeout al obtener clima para {city}")
            return None
        except Exception as e:
            logger.error(f"Error en _get_current_weather: {str(e)}")
            return None
