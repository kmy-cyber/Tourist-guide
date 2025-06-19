from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
import json
import os
import re
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import logging
import aiohttp
from bs4 import BeautifulSoup
import asyncio
from urllib.parse import urljoin

# Configurar logger
logger = logging.getLogger(__name__)

class CrawlerType(Enum):
    """Tipos de crawlers disponibles"""
    HOTEL = "hotel"
    MUSEUM = "museum"
    EXCURSION = "excursion"
    DESTINATION = "destination"
    ATTRACTION = "attraction"
    MAIN_DESTINATION = "main_destination"
    ALTERNATIVE_DESTINATION = "alternative_destination"
    PROVINCE_INFO = "province_info"
    DESTINATION_DETAILS = "destination_details"
    RATED_ATTRACTION = "rated_attractions"
    LANDMARK = "landmark_info"


@dataclass
class CrawlerConfig:
    """Configuración base para un crawler"""
    name: str
    base_url: str
    type: CrawlerType
    selectors: Dict[str, str]
    reliability: float = 1.0
    priority: int = 1
    enabled: bool = True
    rate_limit: float = 1.0  # Rate limit in seconds between requests

class BaseSiteCrawler(ABC):
    """Clase base abstracta para crawlers específicos de sitio"""
    
    def __init__(self, config: CrawlerConfig):
        """Inicializa el crawler base"""
        self.config = config
        self.results = []
        self.errors = []
        self._crawler_process = None
        self._html_result = None
        self._semaphore = None
        logger.info(f"Inicializando crawler {config.name} para {config.base_url}")
    
    def log_error(self, error: str, context: Optional[Dict] = None):
        """Registro de errores durante el crawling"""
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "error": error,
            "context": context or {}
        }
        self.errors.append(error_entry)
        logger.error(f"Error in {self.config.name}: {error}")
    
    def _extract_text(self, item: BeautifulSoup, selector: str) -> str:
        """Extrae texto de un elemento usando un selector"""
        try:
            element = item.select_one(selector)
            return element.get_text(strip=True) if element else ""
        except Exception as e:
            self.log_error(f"Error extracting text with selector {selector}: {str(e)}")
            return ""
            
    async def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Obtiene una página usando aiohttp y devuelve un objeto BeautifulSoup.
        
        Args:
            url: URL de la página a obtener
            
        Returns:
            BeautifulSoup object o None si hay error
        """
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(1)  # Limit concurrent requests
            
        try:
            async with self._semaphore:
                # Respetar rate limit
                await asyncio.sleep(self.config.rate_limit)
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
                
                timeout = aiohttp.ClientTimeout(total=30)
                try:
                    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                        async with session.get(url) as response:
                            if response.status == 200:
                                try:
                                    html = await response.text()
                                    return BeautifulSoup(html, 'html.parser')
                                except Exception as e:
                                    self.log_error(f"Error parsing content from {url}: {str(e)}")
                                    return None
                            else:
                                self.log_error(f"Error fetching {url}: Status {response.status}")
                                return None
                except aiohttp.ClientError as e:
                    self.log_error(f"Network error fetching {url}: {str(e)}")
                    return None
                    
        except Exception as e:
            self.log_error(f"Error fetching {url}: {str(e)}")
            return None
            
    @abstractmethod
    async def crawl(self) -> List[Dict[str, Any]]:
        """Método principal de crawling que debe ser implementado"""
        pass
    
    @abstractmethod
    def parse_item(self, item: Any) -> Optional[Dict[str, Any]]:
        """Método para parsear un item específico"""
        pass
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validación básica de datos"""
        required_fields = ["name", "type", "description"]
        return all(field in data and data[field] for field in required_fields)
    
    def standardize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Estandarización de datos común"""
        return {
            "id": f"{self.config.type.value}_{len(self.results)}",
            "name": data.get("name", "").strip(),
            "type": self.config.type.value,
            "description": data.get("description", "").strip(),
            "source": {
                "url": self.config.base_url,
                "name": self.config.name,
                "reliability": self.config.reliability,
                "crawl_date": datetime.now().isoformat()
            }
        }


class DataCleaner:
    """Clase para limpieza y estandarización de datos"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Limpia y normaliza texto"""
        if not text:
            return ""
        return " ".join(text.split()).strip()
    
    @staticmethod
    def parse_price(price: str) -> Dict[str, Any]:
        """Parsea y estandariza precios"""
        if not price:
            return {"type": "unknown"}
            
        price = price.lower()
        if any(word in price for word in ["gratis", "libre", "free"]):
            return {"type": "free"}
            
        try:
            amount_pattern = r"(\d+(?:\.\d{2})?)"
            amounts = re.findall(amount_pattern, price)
            
            if amounts:
                currency = "CUP"
                if any(c in price.upper() for c in ["USD", "$"]):
                    currency = "USD"
                elif any(c in price for c in ["EUR", "€"]):
                    currency = "EUR"
                    
                return {
                    "type": "fixed",
                    "amount": float(amounts[0]),
                    "currency": currency
                }
        except Exception:
            pass
            
        return {"type": "unknown", "original": price}
    
    @staticmethod
    def parse_schedule(schedule: str) -> Dict[str, Any]:
        """Parsea y estandariza horarios"""
        if not schedule:
            return {"type": "unknown"}
            
        schedule = schedule.lower()
        if "cerrado" in schedule:
            return {"type": "closed"}
            
        try:
            days = []
            if "lunes a viernes" in schedule:
                days = ["Lun", "Mar", "Mie", "Jue", "Vie"]
            elif "todos los días" in schedule:
                days = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
                
            time_pattern = r"(\d{1,2}):?(\d{2})?\s*(?:am|pm|hrs|h)?\s*(?:a|hasta|-)?\s*(\d{1,2}):?(\d{2})?\s*(?:am|pm|hrs|h)?"
            matches = re.findall(time_pattern, schedule)
            
            if matches:
                start_h, start_m, end_h, end_m = matches[0]
                hours = [{
                    "start": f"{start_h.zfill(2)}:{start_m if start_m else '00'}",
                    "end": f"{end_h.zfill(2)}:{end_m if end_m else '00'}"
                }]
                
                return {
                    "type": "regular",
                    "days": days,
                    "hours": hours
                }
        except Exception:
            pass
            
        return {"type": "unknown", "original": schedule}


class CrawlerManager:
    """Gestor de crawlers del sistema"""
    
    def __init__(self):
        """Inicializa el gestor de crawlers"""
        self.crawlers: Dict[CrawlerType, BaseSiteCrawler] = {}
        self.data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info(f"CrawlerManager inicializado. Directorio de datos: {self.data_dir}")
    
    def register_crawler(self, crawler: BaseSiteCrawler) -> None:
        """Registra un nuevo crawler en el sistema"""
        if not crawler.config.enabled:
            logger.warning(f"Crawler {crawler.config.name} deshabilitado, ignorando registro")
            return
        self.crawlers[crawler.config.type] = crawler
        logger.info(f"Crawler {crawler.config.name} registrado exitosamente")
    
    async def run_crawlers(self, crawler_types: Optional[List[CrawlerType]] = None) -> Dict[str, Any]:
        """Ejecuta los crawlers especificados y retorna los resultados"""
        results = []
        errors = []
        stats = {"total_items": 0, "errors": 0}
        
        types_to_run = crawler_types or list(self.crawlers.keys())
        logger.info(f"Iniciando ejecución de crawlers. Tipos: {[t.value for t in types_to_run]}")
        
        for crawler_type in types_to_run:
            if crawler_type not in self.crawlers:
                logger.warning(f"Tipo de crawler no encontrado: {crawler_type.value}")
                continue
            
            crawler = self.crawlers[crawler_type]
            try:
                logger.info(f"Ejecutando crawler {crawler.config.name}")
                crawler_results = await crawler.crawl()
                
                if crawler_results:
                    results.extend(crawler_results)
                    stats["total_items"] += len(crawler_results)
                    logger.info(f"Crawler {crawler.config.name} completado. Items encontrados: {len(crawler_results)}")
                else:
                    logger.warning(f"Crawler {crawler.config.name} no retornó resultados")
                
                if crawler.errors:
                    errors.extend(crawler.errors)
                    stats["errors"] += len(crawler.errors)
                    logger.warning(f"Crawler {crawler.config.name} reportó {len(crawler.errors)} errores")
                    
            except Exception as e:
                error_info = {
                    "timestamp": datetime.now().isoformat(),
                    "crawler": crawler.config.name,
                    "error": str(e)
                }
                errors.append(error_info)
                stats["errors"] += 1
                logger.error(f"Error ejecutando crawler {crawler.config.name}: {str(e)}", exc_info=True)
        
        # Guardar resultados en archivo
        if results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"crawl_subprocess_{timestamp}.json"
            filepath = os.path.join(self.data_dir, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump({
                    "data": results,
                    "errors": errors,
                    "stats": stats,
                    "timestamp": datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
        
        return {
            "data": results,
            "errors": errors,
            "stats": stats
        }
