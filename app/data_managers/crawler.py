from typing import List, Dict
import scrapy
from scrapy.crawler import CrawlerProcess
from bs4 import BeautifulSoup
import requests
import json
import os
import re
from datetime import datetime

class TourismSpider(scrapy.Spider):
    name = 'tourism_spider'
    
    # CSS Selectors
    LINK_SELECTOR = 'a::attr(href)'
    IMAGE_SELECTOR = 'img::attr(src)'
    
    # Domain names
    DOMAIN_CUBATRAVEL = 'cubatravel.cu'
    DOMAIN_MUSEOSCUBA = 'museoscuba.org'
    DOMAIN_ECURED = 'ecured.cu'
    DOMAIN_ARTCUBA = 'artcubanacional.cult.cu'
    DOMAIN_CNPC = 'cnpc.cult.cu'
    
    # Define domain focus explicitly for documentation
    DOMAIN_FOCUS = {
        'museums': ['art', 'history', 'science', 'culture'],
        'excursions': ['urban', 'nature', 'cultural']
    }
    
    # Define primary and fallback sources
    SOURCES = {
        'museums': [
            f'https://www.{DOMAIN_MUSEOSCUBA}',
            f'https://www.{DOMAIN_ARTCUBA}/museos',
            f'https://www.{DOMAIN_ECURED}/Categor%C3%ADa:Museos_de_Cuba'
        ],
        'excursions': [
            f'https://www.{DOMAIN_CUBATRAVEL}/es/excursiones',
            f'https://www.{DOMAIN_CNPC}/excursiones'
        ],
        'destinations': [
            f'https://www.{DOMAIN_CUBATRAVEL}/es/destinos'
        ]
    }
    
    TRUSTED_SOURCES = {
        DOMAIN_CUBATRAVEL: {'type': 'official', 'reliability': 'high'},
        DOMAIN_MUSEOSCUBA: {'type': 'institutional', 'reliability': 'high'},
        DOMAIN_ECURED: {'type': 'encyclopedia', 'reliability': 'medium'},
        DOMAIN_ARTCUBA: {'type': 'official', 'reliability': 'high'},
        DOMAIN_CNPC: {'type': 'official', 'reliability': 'high'}
    }

    def __init__(self, *args, **kwargs):
        super(TourismSpider, self).__init__(*args, **kwargs)
        # Flatten sources into start_urls
        self.start_urls = []
        for sources in self.SOURCES.values():
            self.start_urls.extend(sources)
        # Track failed domains
        self.failed_domains = set()
        # Track successful items by type
        self.items_count = {'museum': 0, 'excursion': 0, 'destination': 0}
    
    def errback_httpbin(self, failure):
        """Handle various failures during crawling"""
        # Handle different types of failures
        try:
            if hasattr(failure, 'request'):
                failed_url = failure.request.url
            elif isinstance(failure, Exception):
                # If it's a direct exception, try to get url from traceback
                failed_url = str(failure)
            else:
                failed_url = "Unknown URL"

            domain = failed_url.split('/')[2] if '/' in failed_url else 'unknown'
            
            if domain not in self.failed_domains:
                self.failed_domains.add(domain)
                self.logger.error(f'Failed to crawl {domain}: {str(failure)}')
                
                # If a primary source fails, log warning about using fallback
                if self.DOMAIN_MUSEOSCUBA in failed_url:
                    self.logger.warning('Primary museum source unavailable, using fallback sources')
                elif self.DOMAIN_CUBATRAVEL in failed_url:
                    self.logger.warning('Primary excursion source unavailable, using fallback sources')

        except Exception as e:
            self.logger.error(f'Error in errback handling: {str(e)}')
            
    def closed(self, reason):
        """Called when the spider is closed"""
        # Log summary of crawled items
        self.logger.info(f"Crawling completed. Items found: {dict(self.items_count)}")
        if self.failed_domains:
            self.logger.warning(f"Failed domains: {', '.join(self.failed_domains)}")
            
    def parse(self, response):
        """Parse tourism data from allowed domains"""
        try:
            # Handle HTTP errors gracefully
            if response.status == 404:
                self.logger.warning(f"Page not found: {response.url} - skipping")
                return
            elif response.status >= 400:
                self.logger.warning(f"HTTP error {response.status} on {response.url} - skipping")
                return
            
            domain = response.url.split('/')[2]
            
            self.logger.info(f"Parsing URL: {response.url} with status {response.status}")
            self.logger.info(f"Response body length: {len(response.body)}")
            
            # Determine parser based on domain and path
            if self.DOMAIN_CUBATRAVEL in domain:
                self.logger.info(f"Using cubatravel parser for {response.url}")
                # Log some sample elements to debug selectors
                self.logger.info(f"Found {len(response.css('.destination-item'))} destination items")
                items_generator = self.parse_cubatravel(response) if 'excursiones' not in response.url else self.parse_excursions(response)
                item_type = 'excursion' if 'excursiones' in response.url else 'destination'

            elif self.DOMAIN_MUSEOSCUBA in domain or self.DOMAIN_ARTCUBA in domain:
                self.logger.info(f"Using museums parser for {response.url}")
                self.logger.info(f"Found {len(response.css('.museum-item, .museo-item'))} museum items")
                items_generator = self.parse_museums(response)
                item_type = 'museum'

            elif self.DOMAIN_ECURED in domain:
                self.logger.info(f"Using ecured parser for {response.url}")
                items = response.css('.mw-category-group li')
                self.logger.info(f"Found {len(items)} ecured items")
                items_generator = self.parse_ecured(response)
                item_type = 'museum'

            elif self.DOMAIN_CNPC in domain:
                self.logger.info(f"Using excursions parser for {response.url}")
                self.logger.info(f"Found {len(response.css('.excursion-item, .tour-item'))} excursion items")
                items_generator = self.parse_excursions(response)
                item_type = 'excursion'
            else:
                self.logger.warning(f"Unknown domain: {domain} for URL: {response.url}")
                return

            # Process each item yielded by the generator
            item_count = 0
            for item in items_generator:
                if item:  # Only count valid items
                    self.items_count[item_type] += 1
                    item_count += 1
                    yield item
            
            if item_count == 0:
                self.logger.info(f"No items found on {response.url}")

        except Exception as e:
            self.logger.error(f"Error parsing {response.url}: {str(e)}")
            return

    def parse_cubatravel(self, response):
        """Parse data from cubatravel.cu"""
        # Try multiple selectors as the site structure might vary
        destination_selectors = [
            '.destination-item',
            '.dest-item', 
            '.card',
            '.item',
            'article'
        ]
        
        destinations_found = []
        for selector in destination_selectors:
            destinations_found = response.css(selector)
            if destinations_found:
                self.logger.info(f"Found {len(destinations_found)} destinations using selector: {selector}")
                break
        
        if not destinations_found:
            self.logger.info(f"No destinations found with any selector on {response.url}")
            return
            
        for destination in destinations_found:
            # Extract data with fallback selectors
            name = (destination.css('.title::text').get() or 
                   destination.css('.name::text').get() or
                   destination.css('h1::text, h2::text, h3::text').get() or
                   destination.css('a::text').get())
            
            description = (destination.css('.description::text').get() or
                          destination.css('.desc::text').get() or
                          destination.css('p::text').get())
            
            if not name and not description:
                continue  # Skip items without basic info
                
            location = (destination.css('.location::text').get() or
                       destination.css('.address::text').get() or
                       destination.css('.lugar::text').get())
            
            # Extract coordinates if available
            lat = destination.css('::attr(data-lat)').get()
            lng = destination.css('::attr(data-lng)').get()
            coordinates = {}
            if lat and lng:
                try:
                    coordinates = {
                        'latitude': float(lat),
                        'longitude': float(lng)
                    }
                except (ValueError, TypeError):
                    coordinates = {'latitude': None, 'longitude': None}
            else:
                coordinates = {'latitude': None, 'longitude': None}
            
            # Extract activities
            activities = (destination.css('.activities li::text').getall() or
                         destination.css('.activity::text').getall() or
                         [])
            
            # Extract URL and image
            url = destination.css('a::attr(href)').get()
            if url:
                url = response.urljoin(url)
            
            image_url = destination.css('img::attr(src)').get()
            if image_url:
                image_url = response.urljoin(image_url)
            
            yield {
                'type': 'destination',
                'name': name.strip() if name else '',
                'description': description.strip() if description else '',
                'location': location.strip() if location else '',
                'coordinates': coordinates,
                'activities': [a.strip() for a in activities if a.strip()],
                'url': url or '',
                'image_url': image_url or '',
                'source': 'cubatravel.cu',
                'crawl_date': datetime.now().isoformat()
            }

    def parse_museums(self, response):
        """Parse data from museum websites"""
        # Try multiple selectors for museums
        museum_selectors = [
            '.museum-item',
            '.museo-item',
            '.museum',
            '.card',
            '.item',
            'article'
        ]
        
        museums_found = []
        for selector in museum_selectors:
            museums_found = response.css(selector)
            if museums_found:
                self.logger.info(f"Found {len(museums_found)} museums using selector: {selector}")
                break
        
        if not museums_found:
            self.logger.info(f"No museums found with any selector on {response.url}")
            return
            
        for museum in museums_found:
            # Extract basic info with fallback selectors
            name = (museum.css('.name::text, .titulo::text').get() or
                   museum.css('h1::text, h2::text, h3::text').get() or
                   museum.css('a::text').get())
            
            description = (museum.css('.description::text, .descripcion::text').get() or
                          museum.css('p::text').get())
            
            if not name and not description:
                continue  # Skip items without basic info
                
            location = (museum.css('.location::text, .direccion::text').get() or
                       museum.css('.address::text').get())
            
            schedule = museum.css('.schedule::text, .horario::text').get()
            price = museum.css('.price::text, .precio::text').get()
            
            # Extract collections and services
            collections = (museum.css('.coleccion li::text').getall() or
                          museum.css('.collections li::text').getall() or
                          [])
            
            services = (museum.css('.servicios li::text').getall() or
                       museum.css('.services li::text').getall() or
                       [])
            
            accessibility = museum.css('.accesibilidad::text').get()
            
            # Extract URL and image
            url = museum.css('a::attr(href)').get()
            if url:
                url = response.urljoin(url)
            
            image_url = museum.css('img::attr(src)').get()
            if image_url:
                image_url = response.urljoin(image_url)
            
            yield {
                'type': 'museum',
                'name': name.strip() if name else '',
                'location': location.strip() if location else '',
                'schedule': schedule.strip() if schedule else '',
                'price': price.strip() if price else '',
                'description': description.strip() if description else '',
                'collections': [c.strip() for c in collections if c.strip()],
                'services': [s.strip() for s in services if s.strip()],
                'accessibility': accessibility.strip() if accessibility else '',
                'url': url or '',
                'image_url': image_url or '',
                'source': response.url.split('/')[2],
                'crawl_date': datetime.now().isoformat()
            }

    def parse_excursions(self, response):
        """Parse excursion data"""
        # Try multiple selectors for excursions
        excursion_selectors = [
            '.excursion-item',
            '.tour-item',
            '.excursion',
            '.tour',
            '.card',
            '.item',
            'article'
        ]
        
        excursions_found = []
        for selector in excursion_selectors:
            excursions_found = response.css(selector)
            if excursions_found:
                self.logger.info(f"Found {len(excursions_found)} excursions using selector: {selector}")
                break
        
        if not excursions_found:
            self.logger.info(f"No excursions found with any selector on {response.url}")
            return
            
        for excursion in excursions_found:
            # Extract basic info with fallback selectors
            name = (excursion.css('.title::text, .nombre::text').get() or
                   excursion.css('h1::text, h2::text, h3::text').get() or
                   excursion.css('a::text').get())
            
            description = (excursion.css('.description::text, .descripcion::text').get() or
                          excursion.css('p::text').get())
            
            if not name and not description:
                continue  # Skip items without basic info
                
            duration = excursion.css('.duration::text, .duracion::text').get()
            price = excursion.css('.price::text, .precio::text').get()
            difficulty_level = excursion.css('.difficulty::text, .dificultad::text').get()
            
            # Extract services and requirements
            included_services = (excursion.css('.included li::text').getall() or
                               excursion.css('.services li::text').getall() or
                               [])
            
            required_items = (excursion.css('.required li::text').getall() or
                             excursion.css('.requirements li::text').getall() or
                             [])
            
            meeting_point = excursion.css('.meeting::text, .punto-encuentro::text').get()
            schedule = excursion.css('.schedule::text, .horario::text').get()
            max_participants = excursion.css('.max-participants::text').get()
            
            # Extract URL and image
            url = excursion.css('a::attr(href)').get()
            if url:
                url = response.urljoin(url)
            
            image_url = excursion.css('img::attr(src)').get()
            if image_url:
                image_url = response.urljoin(image_url)
            
            yield {
                'type': 'excursion',
                'name': name.strip() if name else '',
                'description': description.strip() if description else '',
                'duration': duration.strip() if duration else '',
                'price': price.strip() if price else '',
                'difficulty_level': difficulty_level.strip() if difficulty_level else '',
                'included_services': [s.strip() for s in included_services if s.strip()],
                'required_items': [i.strip() for i in required_items if i.strip()],
                'meeting_point': meeting_point.strip() if meeting_point else '',
                'schedule': schedule.strip() if schedule else '',
                'max_participants': max_participants.strip() if max_participants else '',
                'url': url or '',
                'image_url': image_url or '',
                'source': response.url.split('/')[2],
                'crawl_date': datetime.now().isoformat()
            }
    
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
            name = item.css('a::text').get()
            if museum_url and name:
                yield scrapy.Request(
                    museum_url,
                    callback=self.parse_ecured_museum,
                    meta={'name': name},
                    errback=self.errback_httpbin
                )

    def parse_ecured_museum(self, response):
        """Parse detailed museum information from Ecured"""
        item = {
            'type': 'museum',
            'name': response.meta['name'],
            'description': ' '.join(p.strip() for p in response.css('#mw-content-text p::text').getall() if p.strip()),
            'location': response.css('.geo::text').get(),
            'history': [p.strip() for p in response.css('#Historia ~ p::text').getall() if p.strip()],
            'collections': [p.strip() for p in response.css('#Colecciones ~ p::text, #Exposiciones ~ p::text').getall() if p.strip()],
            'url': response.url,
            'image_url': response.css('.imagen img::attr(src)').get(),
            'source': 'ecured.cu',
            'crawl_date': datetime.now().isoformat()
        }
        
        # Validate required fields
        if item['name'] and (item['description'] or item['collections']):
            yield item

    def _validate_data(self, item: dict) -> dict:
        """Validate and standardize scraped data"""
        if not item.get('name'):
            return {}
            
        # Standardize fields
        item['name'] = item['name'].strip().title() if item.get('name') else ""
        item['price'] = self._standardize_price(item.get('price', ''))
        item['schedule'] = self._standardize_schedule(item.get('schedule', ''))
        item['location'] = self._standardize_location(item.get('location', ''))
        
        # Add source reliability info
        domain = item.get('source', '')
        item['source_info'] = self.TRUSTED_SOURCES.get(domain, {'type': 'unknown', 'reliability': 'low'})
        
        # Add domain classification
        if item['type'] == 'museum':
            item['domain_category'] = self._classify_museum(item)
        elif item['type'] == 'excursion':
            item['domain_category'] = self._classify_excursion(item)
        
        item['last_updated'] = datetime.now().isoformat()
        return item

    def _standardize_price(self, price: str) -> dict:
        """Standardize price information"""
        if not price:
            return {'type': 'unknown'}
        # Add price standardization logic here
        return {'type': 'fixed', 'amount': price.strip(), 'currency': 'CUP'}

    def _standardize_schedule(self, schedule: str) -> dict:
        """Standardize schedule information"""
        if not schedule:
            return {'type': 'unknown'}
        # Add schedule standardization logic here
        return {'type': 'regular', 'schedule': schedule.strip()}

    def _standardize_location(self, location: str) -> dict:
        """Standardize location information"""
        if not location:
            return {'type': 'unknown'}
        # Add location standardization logic here
        return {'type': 'address', 'address': location.strip()}

    def _classify_museum(self, item: dict) -> list:
        """Classify museum into domain categories"""
        categories = []
        description = (item.get('description', '') + ' ' + 
                      ' '.join(item.get('collections', []))).lower()
        
        for category in self.DOMAIN_FOCUS['museums']:
            if category in description:
                categories.append(category)
        return categories or ['culture']  # Default to culture if no specific category found

    def _classify_excursion(self, item: dict) -> list:
        """Classify excursion into domain categories"""
        categories = []
        description = (item.get('description', '') + ' ' + 
                      ' '.join(item.get('included_services', []))).lower()
        
        for category in self.DOMAIN_FOCUS['excursions']:
            if category in description:
                categories.append(category)
        return categories or ['cultural']  # Default to cultural if no specific category found

    def _parse_time_range(self, schedule_text: str) -> dict:
        """Extract time range from schedule text"""
        if not schedule_text:
            return {'type': 'unknown'}

        try:
            # Simpler time patterns
            hour_pattern = r'(\d{1,2})(?::(\d{2}))?' 
            time_suffix = r'(?:am|pm|hrs?)?'
            separator = r'\s*(?:a|hasta|-)\s*'
            
            # Build full pattern in parts
            full_pattern = f"{hour_pattern}{time_suffix}{separator}{hour_pattern}{time_suffix}"
            
            match = re.search(full_pattern, schedule_text, re.IGNORECASE)
            if not match:
                return {'type': 'text', 'value': schedule_text.strip()}

            start_hour, start_min, end_hour, end_min = match.groups()
            
            # Convert to 24-hour format
            start_time = f"{start_hour}:{start_min or '00'}"
            end_time = f"{end_hour}:{end_min or '00'}"
            
            return {
                'type': 'range',
                'start': start_time,
                'end': end_time,
            }

        except Exception:
            return {'type': 'text', 'value': schedule_text.strip()}

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
        if not value:
            return 0
        try:
            return int(''.join(filter(str.isdigit, value)))
        except (ValueError, TypeError):
            return 0
