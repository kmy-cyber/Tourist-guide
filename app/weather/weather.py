import requests
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class WeatherInfo:
    city: str
    current_temp: float
    feels_like: float
    description: str
    daily_forecast: List[Dict]
    
class WeatherAgent:
    def __init__(self, api_key: str = 'none'):
        self.api_key = api_key
        self.geocoding_url = 'http://api.openweathermap.org/geo/1.0/direct'
        self.weather_url = 'https://api.openweathermap.org/data/3.0/onecall'

    def get_weather_info(self, city: str, time_range: str = 'today') -> Optional[WeatherInfo]:
        """
        Get weather information for a given city and time range
        
        Args:
            city (str): Name of the city in Cuba
            time_range (str): One of 'today', 'tomorrow', 'weekend', 'week'
            
        Returns:
            WeatherInfo object or None if city not found
        """
        try:
            lat, lon = self._get_coordinates(city)
            weather_data = self._get_weather(lat, lon)
            
            if not weather_data or 'current' not in weather_data:
                return None
                
            return WeatherInfo(
                city=city,
                current_temp=weather_data['current']['temp'],
                feels_like=weather_data['current']['feels_like'],
                description=weather_data['current']['weather'][0]['description'],
                daily_forecast=self._filter_forecast(weather_data['daily'], time_range)
            )
        except Exception as e:
            print(f"Error getting weather for {city}: {e}")
            return None

    def _get_coordinates(self, city: str) -> Tuple[float, float]:
        """Get coordinates for a city in Cuba"""
        params = {
            'q': f'{city},CU',
            'limit': 1,
            'appid': self.api_key
        }
        response = requests.get(self.geocoding_url, params=params)
        data = response.json()

        if not data:
            raise ValueError(f'Ciudad {city} no encontrada en Cuba.')

        return data[0]['lat'], data[0]['lon']

    def _get_weather(self, lat: float, lon: float) -> Dict:
        """Get weather data from OpenWeather API"""
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'lang': 'es',
            'units': 'metric',
            'exclude': 'minutely,hourly,alerts'
        }
        response = requests.get(self.weather_url, params=params)
        return response.json()

    def _filter_forecast(self, daily_data: List[Dict], time_range: str) -> List[Dict]:
        """Filter forecast data based on requested time range"""
        if time_range == 'today':
            return daily_data[:1]
        elif time_range == 'tomorrow':
            return daily_data[1:2]
        elif time_range == 'weekend':
            # Get upcoming weekend days
            today = datetime.now()
            days_ahead = 5 - today.weekday()  # Days until Saturday
            if days_ahead <= 0:
                days_ahead += 7
            weekend_days = [today + timedelta(days=i) for i in range(days_ahead, days_ahead + 2)]
            return [day for day in daily_data if datetime.fromtimestamp(day['dt']).date() in [w.date() for w in weekend_days]]
        else:  # week
            return daily_data[:7]

    def generate_weather_summary(self, weather_info: WeatherInfo) -> str:
        """
        Generate a natural language summary of weather information
        """
        if not weather_info:
            return "Lo siento, no pude obtener la información del clima para esa ubicación."

        # Formato base del resumen
        summary = [
            f"🌡️ Clima actual en {weather_info.city}:",
            f"Temperatura: {weather_info.current_temp}°C",
            f"Sensación térmica: {weather_info.feels_like}°C",
            f"Condiciones: {weather_info.description.capitalize()}",
            "\n📅 Pronóstico:"
        ]

        # Agregar pronóstico diario
        for day in weather_info.daily_forecast:
            date = datetime.fromtimestamp(day['dt']).strftime('%d/%m/%Y')
            temp = day['temp']['day']
            desc = day['weather'][0]['description']
            summary.append(f"- {date}: {temp}°C, {desc}")

        # Detectar condiciones especiales
        risks = []
        for day in weather_info.daily_forecast:
            temp = day['temp']['day']
            desc = day['weather'][0]['description'].lower()
            
            if temp > 35:
                risks.append("⚠️ Calor extremo")
            if 'lluvia' in desc or 'tormenta' in desc:
                risks.append("🌧️ Posibilidad de lluvia")
            if 'tormenta' in desc:
                risks.append("⛈️ Riesgo de tormentas")

        if risks:
            summary.append("\n⚠️ Alertas y consideraciones:")
            summary.extend(list(set(risks)))  # Eliminar duplicados

        return "\n".join(summary)
