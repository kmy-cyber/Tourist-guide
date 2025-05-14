from typing import List, Dict
import scrapy
from scrapy.crawler import CrawlerProcess
from bs4 import BeautifulSoup
import requests
import json
import os
from datetime import datetime

class TourismSpider(scrapy.Spider):
    name = 'tourism_spider'
    allowed_domains = [
        'www.cubatravel.cu',
        'www.museoscuba.org',
        'www.ecured.cu',
        'www.artcubanacional.cult.cu',
        'www.cnpc.cult.cu'
    ]
    
    def __init__(self, *args, **kwargs):
        super(TourismSpider, self).__init__(*args, **kwargs)
        self.start_urls = [
            'https://www.cubatravel.cu/es/destinos',
            'https://www.cubatravel.cu/es/excursiones',
            'https://www.museoscuba.org',
            'https://www.ecured.cu/Categor%C3%ADa:Museos_de_Cuba',
            'https://www.artcubanacional.cult.cu/museos',
            'https://www.cnpc.cult.cu/excursiones'
        ]
        
    def parse(self, response):
        """Parse tourism data from allowed domains"""
        if 'cubatravel.cu' in response.url:
            if 'excursiones' in response.url:
                yield from self.parse_excursions(response)
            else:
                yield from self.parse_cubatravel(response)
        elif 'museoscuba.org' in response.url or 'artcubanacional.cult.cu' in response.url:
            yield from self.parse_museums(response)
        elif 'ecured.cu' in response.url:
            yield from self.parse_ecured(response)
        elif 'cnpc.cult.cu' in response.url:
            yield from self.parse_excursions(response)

    def parse_cubatravel(self, response):
        """Parse data from cubatravel.cu"""
        for destination in response.css('.destination-item'):
            yield {
                'type': 'destination',
                'name': destination.css('.title::text').get(),
                'description': destination.css('.description::text').get(),
                'location': destination.css('.location::text').get(),
                'coordinates': {
                    'latitude': destination.css('::attr(data-lat)').get(),
                    'longitude': destination.css('::attr(data-lng)').get()
                },
                'activities': destination.css('.activities li::text').getall(),
                'url': response.urljoin(destination.css('a::attr(href)').get()),
                'image_url': destination.css('img::attr(src)').get(),
                'source': 'cubatravel.cu',
                'crawl_date': datetime.now().isoformat()
            }

    def parse_museums(self, response):
        """Parse data from museum websites"""
        for museum in response.css('.museum-item, .museo-item'):
            yield {
                'type': 'museum',
                'name': museum.css('.name::text, .titulo::text').get(),
                'location': museum.css('.location::text, .direccion::text').get(),
                'schedule': museum.css('.schedule::text, .horario::text').get(),
                'price': museum.css('.price::text, .precio::text').get(),
                'description': museum.css('.description::text, .descripcion::text').get(),
                'collections': museum.css('.coleccion li::text').getall(),
                'services': museum.css('.servicios li::text').getall(),
                'accessibility': museum.css('.accesibilidad::text').get(),
                'url': response.urljoin(museum.css('a::attr(href)').get()),
                'image_url': museum.css('img::attr(src)').get(),
                'source': response.url.split('/')[2],
                'crawl_date': datetime.now().isoformat()
            }

    def parse_excursions(self, response):
        """Parse excursion data"""
        for excursion in response.css('.excursion-item, .tour-item'):
            yield {
                'type': 'excursion',
                'name': excursion.css('.title::text, .nombre::text').get(),
                'description': excursion.css('.description::text, .descripcion::text').get(),
                'duration': excursion.css('.duration::text, .duracion::text').get(),
                'price': excursion.css('.price::text, .precio::text').get(),
                'difficulty_level': excursion.css('.difficulty::text, .dificultad::text').get(),
                'included_services': excursion.css('.included li::text').getall(),
                'required_items': excursion.css('.required li::text').getall(),
                'meeting_point': excursion.css('.meeting::text, .punto-encuentro::text').get(),
                'schedule': excursion.css('.schedule::text, .horario::text').get(),
                'max_participants': excursion.css('.max-participants::text').get(),
                'url': response.urljoin(excursion.css('a::attr(href)').get()),
                'image_url': excursion.css('img::attr(src)').get(),
                'source': response.url.split('/')[2],
                'crawl_date': datetime.now().isoformat()
            }

    def parse_ecured(self, response):
        """Parse data from ecured.cu"""
        for item in response.css('.mw-category-group li'):
            museum_url = response.urljoin(item.css('a::attr(href)').get())
            yield scrapy.Request(
                museum_url,
                callback=self.parse_ecured_museum,
                meta={'name': item.css('a::text').get()}
            )

    def parse_ecured_museum(self, response):
        """Parse detailed museum information from Ecured"""
        yield {
            'type': 'museum',
            'name': response.meta['name'],
            'description': ' '.join(response.css('#mw-content-text p::text').getall()),
            'location': response.css('.geo::text').get(),
            'history': response.css('#Historia ~ p::text').getall(),
            'collections': response.css('#Colecciones ~ p::text, #Exposiciones ~ p::text').getall(),
            'url': response.url,
            'image_url': response.css('.imagen img::attr(src)').get(),
            'source': 'ecured.cu',
            'crawl_date': datetime.now().isoformat()
        }

class TourismCrawler:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def start_crawling(self):
        """Initialize and run the crawler process"""
        process = CrawlerProcess(settings={
            'USER_AGENT': 'Tourist Guide Bot (+https://www.example.com)',
            'ROBOTSTXT_OBEY': True,
            'FEED_FORMAT': 'json',
            'FEED_URI': os.path.join(self.output_dir, f'raw_data_{datetime.now().strftime("%Y%m%d")}.json'),
            'CONCURRENT_REQUESTS': 16,
            'DOWNLOAD_DELAY': 1,
            'COOKIES_ENABLED': False
        })
        
        process.crawl(TourismSpider)
        process.start()
        
    def clean_data(self, input_file: str) -> List[Dict]:
        """Clean and standardize crawled data"""
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        cleaned_data = []
        for item in data:
            # Standardize common fields
            cleaned_item = {
                'id': f"{item['type']}_{len(cleaned_data)}",
                'name': self._clean_text(item.get('name', '')),
                'type': item.get('type', 'unknown'),
                'description': self._clean_text(item.get('description', '')),
                'location': self._clean_text(item.get('location', '')),
                'url': item.get('url', ''),
                'image_url': item.get('image_url', ''),
                'source': item.get('source', ''),
                'last_updated': datetime.now().isoformat()
            }
            
            # Add type-specific fields
            if item['type'] == 'museum':
                cleaned_item.update({
                    'schedule': self._standardize_schedule(item.get('schedule', '')),
                    'price': self._standardize_price(item.get('price', '')),
                    'collections': [self._clean_text(c) for c in item.get('collections', [])],
                    'services': [self._clean_text(s) for s in item.get('services', [])],
                    'accessibility': self._clean_text(item.get('accessibility', ''))
                })
            elif item['type'] == 'excursion':
                cleaned_item.update({
                    'duration': self._standardize_duration(item.get('duration', '')),
                    'price': self._standardize_price(item.get('price', '')),
                    'difficulty_level': self._standardize_difficulty(item.get('difficulty_level', '')),
                    'included_services': [self._clean_text(s) for s in item.get('included_services', [])],
                    'required_items': [self._clean_text(i) for i in item.get('required_items', [])],
                    'meeting_point': self._clean_text(item.get('meeting_point', '')),
                    'schedule': self._standardize_schedule(item.get('schedule', '')),
                    'max_participants': self._parse_int(item.get('max_participants', ''))
                })
            elif item['type'] == 'destination':
                cleaned_item.update({
                    'coordinates': item.get('coordinates', {'latitude': None, 'longitude': None}),
                    'activities': [self._clean_text(a) for a in item.get('activities', [])]
                })
                
            cleaned_data.append(cleaned_item)
            
        return cleaned_data
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ''
        # Remove extra whitespace and normalize
        text = ' '.join(text.split())
        # Convert to title case for names
        return text.strip()
    
    def _standardize_schedule(self, schedule: str) -> dict:
        """Convert schedule text to structured format"""
        if not schedule:
            return {'type': 'unknown'}
            
        schedule = schedule.lower()
        if 'cerrado' in schedule:
            return {'type': 'closed'}
            
        try:
            # Try to parse common schedule formats
            days = []
            hours = []
            
            # Extract days
            if 'lunes a viernes' in schedule:
                days = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie']
            elif 'todos los días' in schedule:
                days = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom']
                
            # Extract hours
            import re
            time_pattern = r'(\d{1,2}):?(\d{2})?\s*(?:am|pm|hrs|h)?\s*(?:a|hasta|-)?\s*(\d{1,2}):?(\d{2})?\s*(?:am|pm|hrs|h)?'
            matches = re.findall(time_pattern, schedule)
            
            if matches:
                start_h, start_m, end_h, end_m = matches[0]
                hours = [{
                    'start': f"{start_h.zfill(2)}:{start_m if start_m else '00'}",
                    'end': f"{end_h.zfill(2)}:{end_m if end_m else '00'}"
                }]
                
            return {
                'type': 'regular',
                'days': days,
                'hours': hours
            }
            
        except Exception:
            return {'type': 'unknown', 'original': schedule}
    
    def _standardize_price(self, price: str) -> dict:
        """Convert price text to structured format"""
        if not price:
            return {'type': 'unknown'}
            
        price = price.lower()
        if 'gratis' in price or 'libre' in price:
            return {'type': 'free'}
            
        try:
            # Extract numeric values and currency
            import re
            amount_pattern = r'(\d+(?:\.\d{2})?)'
            amounts = re.findall(amount_pattern, price)
            
            if amounts:
                currency = 'CUP'
                if 'usd' in price or '$' in price:
                    currency = 'USD'
                elif 'eur' in price or '€' in price:
                    currency = 'EUR'
                    
                return {
                    'type': 'fixed',
                    'amount': float(amounts[0]),
                    'currency': currency
                }
                
        except Exception:
            pass
            
        return {'type': 'unknown', 'original': price}
    
    def _standardize_duration(self, duration: str) -> dict:
        """Convert duration text to structured format"""
        if not duration:
            return {'type': 'unknown'}
            
        try:
            # Extract hours and minutes
            import re
            hours_pattern = r'(\d+)\s*(?:hora|hr|h)'
            minutes_pattern = r'(\d+)\s*(?:minuto|min|m)'
            
            hours = re.findall(hours_pattern, duration.lower())
            minutes = re.findall(minutes_pattern, duration.lower())
            
            total_minutes = 0
            if hours:
                total_minutes += int(hours[0]) * 60
            if minutes:
                total_minutes += int(minutes[0])
                
            if total_minutes > 0:
                return {
                    'type': 'fixed',
                    'minutes': total_minutes
                }
                
        except Exception:
            pass
            
        return {'type': 'unknown', 'original': duration}
    
    def _standardize_difficulty(self, difficulty: str) -> str:
        """Standardize difficulty levels"""
        if not difficulty:
            return 'unknown'
            
        difficulty = difficulty.lower()
        if any(word in difficulty for word in ['fácil', 'facil', 'baja']):
            return 'easy'
        elif any(word in difficulty for word in ['media', 'moderada', 'intermedia']):
            return 'medium'
        elif any(word in difficulty for word in ['difícil', 'dificil', 'alta']):
            return 'hard'
            
        return 'unknown'
    
    def _parse_int(self, value: str) -> int:
        """Safely parse integer values"""
        try:
            return int(''.join(filter(str.isdigit, value)))
        except (ValueError, TypeError):
            return None
