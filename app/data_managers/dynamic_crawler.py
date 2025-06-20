"""
Agente Crawler Dinámico Simplificado
Detecta respuestas incompletas/desactualizadas y busca información externa automáticamente
"""

import asyncio
import aiohttp
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ContentGap:
    """Brecha de información detectada"""
    missing_fields: List[str]
    gap_type: str  # 'incomplete', 'outdated', 'inconsistent'
    priority: int  # 1-5

@dataclass
class SearchResult:
    """Resultado de búsqueda"""
    title: str
    url: str
    snippet: str
    score: float

class SmartCrawler:
    """Agente crawler inteligente simplificado"""
    
    def __init__(self):
        # Configuración de fuentes
        self.sources = {
            'google': 'https://www.googleapis.com/customsearch/v1',
            'wikipedia': 'https://es.wikipedia.org/w/api.php',
            'nominatim': 'https://nominatim.openstreetmap.org/search'
        }
        
        # Campos esperados por tipo
        self.required_fields = {
            'museum': ['name', 'description', 'location', 'schedule', 'price'],
            'excursion': ['name', 'description', 'duration', 'price', 'difficulty'],
            'destination': ['name', 'description', 'location', 'activities']
        }
        
        # Patrones de extracción
        self.patterns = {
            'price': r'(\d+(?:\.\d{2})?)\s*(CUP|USD|€|pesos?)',
            'schedule': r'(\d{1,2}:\d{2})\s*[-a]\s*(\d{1,2}:\d{2})',
            'phone': r'(?:\+53\s?)?\d{4}\s?\d{4}'
        }
        
        self.session = None
        self.cache = {}
    
    async def enhance_response(self, query: str, response: Dict) -> Tuple[Dict, List[str]]:
        """Mejorar respuesta automáticamente gestionando la sesión por consulta."""
        
        logs = []
        enhanced = response.copy()

        # Usar un gestor de contexto para la sesión de aiohttp
        async with aiohttp.ClientSession() as session:
            # 1. Detectar gaps
            gaps = self._detect_gaps(response)
            if not gaps:
                return response, ["No se detectaron gaps"]
            
            # 2. Buscar información
            for gap in gaps[:2]:  # Limitar a 2 gaps más importantes
                try:
                    search_query = self._create_search_query(query, gap)
                    results = await self._search_multi_source(session, search_query)
                    
                    if results:
                        new_data = await self._extract_info(session, results, gap)
                        if new_data:
                            enhanced.update(new_data)
                            logs.append(f"Mejorado: {', '.join(new_data.keys())}")
                            
                except Exception as e:
                    logs.append(f"Error: {str(e)}")
        
        # 3. Añadir metadatos
        if logs:
            enhanced['_enhanced'] = {
                'timestamp': datetime.now().isoformat(),
                'improvements': logs
            }
        
        return enhanced, logs
    
    def _detect_gaps(self, response: Dict) -> List[ContentGap]:
        """Detectar brechas en la información"""
        gaps = []
        
        # Detectar tipo
        content_type = response.get('type', 'destination')
        required = self.required_fields.get(content_type, [])
        
        # Campos faltantes
        missing = [field for field in required if not response.get(field)]
        if missing:
            gaps.append(ContentGap(missing, 'incomplete', len(missing)))
        
        # Información desactualizada (>30 días)
        last_update = response.get('last_updated')
        if last_update:
            try:
                update_date = datetime.fromisoformat(last_update.replace('Z', ''))
                if (datetime.now() - update_date).days > 30:
                    gaps.append(ContentGap(['updated_info'], 'outdated', 4))
            except:
                pass
        
        # Precios/horarios vagos
        if response.get('price') in [None, '', 'consultar', 'variable']:
            gaps.append(ContentGap(['price'], 'inconsistent', 3))
        
        return sorted(gaps, key=lambda x: x.priority, reverse=True)
    
    def _create_search_query(self, original: str, gap: ContentGap) -> str:
        """Crear consulta de búsqueda dirigida"""
        base = original.split()[:3]  # Primeras 3 palabras
        
        if gap.gap_type == 'incomplete':
            terms = gap.missing_fields + ['Cuba']
        elif gap.gap_type == 'outdated':
            terms = ['2024', '2025', 'actual', 'Cuba']
        else:
            terms = ['oficial', 'Cuba']
        
        return ' '.join(base + terms)
    
    async def _search_multi_source(self, session: aiohttp.ClientSession, query: str) -> List[SearchResult]:
        """Buscar en múltiples fuentes usando la sesión proporcionada."""
        cache_key = hashlib.md5(query.encode()).hexdigest()
        if cache_key in self.cache and (datetime.now() - self.cache[cache_key]['timestamp']).total_seconds() < 3600:
            return self.cache[cache_key]['data']
        
        results = []
        
        try:
            wiki_results = await self._search_wikipedia(session, query)
            results.extend(wiki_results)
        except Exception as e:
            logger.warning(f"Error en búsqueda de Wikipedia: {e}")

        if any(word in query.lower() for word in ['ubicación', 'dirección', 'donde']):
            try:
                geo_results = await self._search_nominatim(session, query)
                results.extend(geo_results)
            except Exception as e:
                logger.warning(f"Error en búsqueda de Nominatim: {e}")

        self.cache[cache_key] = {'timestamp': datetime.now(), 'data': results}
        return results
        """Buscar en múltiples fuentes"""
        
        # Cache simple
        cache_key = hashlib.md5(query.encode()).hexdigest()
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        results = []
        
        # Búsqueda en Wikipedia
        try:
            wiki_results = await self._search_wikipedia(query)
            results.extend(wiki_results)
        except:
            pass
        
        # Búsqueda en Nominatim para ubicaciones
        if any(word in query.lower() for word in ['ubicación', 'dirección', 'donde']):
            try:
                geo_results = await self._search_nominatim(query)
                results.extend(geo_results)
            except:
                pass
        
        # Cache por 1 hora
        self.cache[cache_key] = results
        return results
    
    async def _search_wikipedia(self, session: aiohttp.ClientSession, query: str) -> List[SearchResult]:
        """Buscar en Wikipedia usando la sesión proporcionada."""
        params = {'action': 'query', 'format': 'json', 'list': 'search', 'srsearch': f"{query} Cuba", 'srlimit': 3}
        async with session.get(self.sources['wikipedia'], params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = []
                for item in data.get('query', {}).get('search', []):
                    results.append(SearchResult(
                        title=item.get('title', ''),
                        url=f"https://es.wikipedia.org/wiki/{item['title'].replace(' ', '_')}",
                        snippet=item.get('snippet', ''),
                        score=0.8
                    ))
                return results
        return []
    
    async def _search_nominatim(self, session: aiohttp.ClientSession, query: str) -> List[SearchResult]:
        """Buscar ubicaciones usando la sesión proporcionada."""
        params = {'q': f"{query} Cuba", 'format': 'json', 'limit': 2, 'countrycodes': 'cu'}
        headers = {'User-Agent': 'SmartCrawler/1.0'}
        async with session.get(self.sources['nominatim'], params=params, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = []
                for item in data:
                    results.append(SearchResult(
                        title=item.get('display_name', ''),
                        url='',
                        snippet=f"Lat: {item.get('lat')}, Lon: {item.get('lon')}",
                        score=0.7
                    ))
                return results
        return []
    
    async def _extract_info(self, session: aiohttp.ClientSession, results: List[SearchResult], gap: ContentGap) -> Dict:
        """Extraer información de resultados usando la sesión proporcionada."""
        extracted = {}
        for result in results[:2]:
            if not result.url or 'wikipedia.org' not in result.url:
                continue
            try:
                page_data = await self._extract_from_page(session, result.url)
                if page_data:
                    relevant_data = {
                        k: v for k, v in page_data.items() 
                        if k in gap.missing_fields or gap.gap_type == 'outdated'
                    }
                    extracted.update(relevant_data)
                    if extracted: break
            except Exception as e:
                logger.warning(f"Error extrayendo de {result.url}: {e}")
                continue
        return extracted
    
    async def _extract_from_page(self, session: aiohttp.ClientSession, url: str) -> Dict:
        """Extraer datos estructurados de una página usando la sesión proporcionada."""
        try:
            async with session.get(url, timeout=8) as resp:
                if resp.status != 200:
                    return {}
                
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                for tag in soup(['script', 'style', 'nav', 'footer']):
                    tag.decompose()
                
                data = {}
                text = soup.get_text()
                
                for field, pattern in self.patterns.items():
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        if field == 'price': data['price'] = f"{match.group(1)} {match.group(2)}"
                        elif field == 'schedule': data['schedule'] = f"{match.group(1)} - {match.group(2)}"
                        else: data[field] = match.group(0)

                for p in soup.find_all('p'):
                    p_text = p.get_text().strip()
                    if 50 < len(p_text) < 300:
                        data['description'] = p_text
                        break
                
                infobox = soup.find('table', class_='infobox')
                if infobox:
                    for row in infobox.find_all('tr'):
                        cells = row.find_all(['th', 'td'])
                        if len(cells) >= 2:
                            key, value = cells[0].get_text().strip().lower(), cells[1].get_text().strip()
                            if 'ubicación' in key or 'dirección' in key: data['location'] = value
                            elif 'horario' in key: data['schedule'] = value
                            elif 'precio' in key or 'entrada' in key: data['price'] = value
                
                return data
        except Exception as e:
            logger.warning(f"Error procesando página {url}: {e}")
            return {}
        
    async def close(self):
        """Cerrar sesión """
        pass

class SimpleCrawlerIntegration:
    """Integración simplificada del crawler"""
    
    def __init__(self):
        self.crawler = SmartCrawler()
        self.stats = {'total': 0, 'enhanced': 0}
    
    async def process_query(self, query: str, response: Dict, auto_enhance: bool = True) -> Dict:
        """Procesar consulta con mejora opcional"""
        
        self.stats['total'] += 1
        
        if not auto_enhance:
            return {
                'response': response,
                'enhanced': False,
                'logs': []
            }
        
        try:
            enhanced_response, logs = await self.crawler.enhance_response(query, response)
            
            was_enhanced = '_enhanced' in enhanced_response
            if was_enhanced:
                self.stats['enhanced'] += 1
            
            return {
                'response': enhanced_response,
                'enhanced': was_enhanced,
                'logs': logs,
                'confidence': 0.9 if was_enhanced else 0.7
            }
            
        except Exception as e:
            logger.error(f"Error en mejora: {e}")
            return {
                'response': response,
                'enhanced': False,
                'logs': [f"Error: {str(e)}"]
            }
    
    def get_stats(self) -> Dict:
        """Estadísticas del sistema"""
        enhancement_rate = 0
        if self.stats['total'] > 0:
            enhancement_rate = self.stats['enhanced'] / self.stats['total']
        
        return {
            'total_queries': self.stats['total'],
            'enhanced_count': self.stats['enhanced'],
            'enhancement_rate': enhancement_rate
        }
    
    async def cleanup(self):
        """Limpiar recursos"""
        await self.crawler.close()

# Función principal de uso
async def enhance_tourism_data(query: str, current_data: Dict) -> Tuple[Dict, List[str]]:
    """
    Función principal para mejorar datos turísticos automáticamente
    
    Args:
        query: Consulta original del usuario
        current_data: Datos actuales del sistema
    
    Returns:
        (datos_mejorados, log_de_mejoras)
    """
    
    crawler = SmartCrawler()
    
    try:
        enhanced_data, logs = await crawler.enhance_response(query, current_data)
        return enhanced_data, logs
    
    finally:
        await crawler.close()

