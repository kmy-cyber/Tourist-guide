from datetime import datetime
from typing import Dict, Tuple, Optional, List
import requests
from .weather import WeatherAgent, WeatherInfo

class WeatherService:
    """Service class to handle weather-related API calls and processing"""
    
    def __init__(self):
        self.weather_agent = WeatherAgent()

    def get_weather_report(self, city: str, time_range: str = 'today') -> Optional[str]:
        """
        Get a formatted weather report for a city
        
        Args:
            city (str): Name of the city in Cuba
            time_range (str): One of 'today', 'tomorrow', 'weekend', 'week'
            
        Returns:
            str: Formatted weather report or None if city not found
        """
        try:
            # Get weather information using the agent
            weather_info = self.weather_agent.get_weather_info(city, time_range)
            
            if not weather_info:
                return None
                
            # Generate human-friendly summary
            return self.weather_agent.generate_weather_summary(weather_info)
            
        except Exception as e:
            print(f"Error getting weather report for {city}: {e}")
            return None

    async def get_weather_async(self, city: str, time_range: str = 'today') -> Optional[str]:
        """
        Async version of get_weather_report for use with async applications
        
        Args:
            city (str): Name of the city in Cuba
            time_range (str): One of 'today', 'tomorrow', 'weekend', 'week'
            
        Returns:
            str: Formatted weather report or None if city not found
        """
        return self.get_weather_report(city, time_range)