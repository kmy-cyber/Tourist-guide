"""
Implementaciones específicas de crawlers para diferentes sitios turísticos de Cuba
"""
from datetime import datetime
from playwright.async_api import async_playwright
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag
import asyncio
from typing import Dict, List, Any, Optional
from .crawler import BaseSiteCrawler, CrawlerConfig, CrawlerType
import re
import logging

logger = logging.getLogger(__name__)


class CubaTravelCrawler(BaseSiteCrawler):
    """Crawler para destinos turísticos principales en cuba.travel"""

    def __init__(self):
        config = CrawlerConfig(
            name="cuba_travel_crawler",
            base_url="https://www.cuba.travel",
            type=CrawlerType.MAIN_DESTINATION,
            selectors={
                "list_item": ".destination-card, .destino-item, .place-card",
                "name": "h2, h3, .title, .nombre",
                "description": ".description, .descripcion, p",
                "location": ".location, .ubicacion, .provincia",
                "image": "img",
                "link": "a"
            },
            rate_limit=2.0
        )
        super().__init__(config)

    async def crawl(self) -> List[Dict[str, Any]]:
        """Crawling básico desde la página principal (limitado)."""
        destinations = []
        try:
            url = f"{self.config.base_url}/destinos"
            soup = await self._fetch_page(url)
            if soup:
                items = soup.select(self.config.selectors["list_item"])
                logger.info(f"Found {len(items)} destinations on cuba.travel")
                for item in items:
                    parsed_item = self.parse_item(item)
                    if parsed_item:
                        destinations.append(parsed_item)
        except Exception as e:
            self.log_error(f"Error crawling cuba.travel: {str(e)}")
        return destinations

    def parse_item(self, item: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Parseo específico para destinos de Cuba Travel"""
        try:
            name = self._extract_text(item, self.config.selectors["name"])
            if not name:
                return None
            description = self._extract_text(item, self.config.selectors["description"])
            location = self._extract_text(item, self.config.selectors["location"])
            img_element = item.select_one(self.config.selectors["image"])
            image_url = img_element.get("src") if img_element else ""
            link_element = item.select_one(self.config.selectors["link"])
            link_url = link_element.get("href") if link_element else ""

            data = {
                "name": name,
                "type": self.config.type.value,
                "description": description,
                "location": location,
                "image_url": image_url,
                "source_url": link_url,
                "source": "cuba.travel"
            }

            if self.validate_data(data):
                return self.standardize_data(data)
        except Exception as e:
            self.log_error(f"Error parsing cuba.travel item: {str(e)}")
        return None

    async def crawl_full_site_with_playwright(self) -> List[Dict[str, Any]]:
        """Crawling completo de provincias, lugares y sus páginas dinámicas."""
        results = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            base_url = self.config.base_url

            try:
                await page.goto(f"{base_url}/destinos", timeout=60000)
                await asyncio.sleep(self.config.rate_limit)
                province_links = await self._get_province_links(page)

                for province_url in province_links:
                    page_num = 1
                    while True:
                        paginated_url = f"{province_url}?page={page_num}"
                        await page.goto(paginated_url, timeout=60000)
                        await asyncio.sleep(self.config.rate_limit)
                        await page.wait_for_load_state("networkidle")
                        content = await page.content()
                        soup = BeautifulSoup(content, "html.parser")

                        items = soup.select(self.config.selectors["list_item"])
                        if not items:
                            break

                        for item in items:
                            link_el = item.select_one(self.config.selectors["link"])
                            if not link_el or not link_el.get("href"):
                                continue
                            place_url = urljoin(base_url, link_el["href"])
                            data = await self._parse_place_detail(page, place_url)
                            if data:
                                results.append(data)

                        next_btn = soup.select_one("a.next, a[rel=next]")
                        if next_btn:
                            page_num += 1
                        else:
                            break
            except Exception as e:
                self.log_error(f"Error in crawl_full_site_with_playwright: {str(e)}")
            finally:
                await browser.close()

        return results

    async def _get_province_links(self, page) -> List[str]:
        await page.wait_for_load_state("networkidle")
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        anchors = soup.select("a[href^='/destinos/']")
        unique_links = {
            urljoin(self.config.base_url, a["href"])
            for a in anchors if a["href"].count("/") == 2  # e.g. /destinos/la-habana
        }
        return list(unique_links)

    async def _parse_place_detail(self, page, url: str) -> Optional[Dict[str, Any]]:
        try:
            await page.goto(url, timeout=60000)
            await asyncio.sleep(self.config.rate_limit)
            await page.wait_for_load_state("networkidle")
            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")

            name = self._extract_text(soup, self.config.selectors["name"])
            description = self._extract_text(soup, self.config.selectors["description"])
            location = self._extract_text(soup, self.config.selectors["location"])
            img = soup.select_one(self.config.selectors["image"])
            image_url = img.get("src") if img else ""

            if not name:
                return None

            data = {
                "name": name.strip(),
                "type": self.config.type.value,
                "description": description.strip() if description else "",
                "location": location.strip() if location else "",
                "image_url": urljoin(self.config.base_url, image_url),
                "source_url": url,
                "source": "cuba.travel"
            }

            if self.validate_data(data):
                return self.standardize_data(data)
        except Exception as e:
            self.log_error(f"Error parsing detail page {url}: {str(e)}")
        return None


class HiCubaCrawler(BaseSiteCrawler):
    """Crawler para extraer hoteles de https://www.hicuba.com/reservar-hotel.htm"""

    def __init__(self):
        config = CrawlerConfig(
            name="hicuba_hotel_crawler",
            base_url="https://www.hicuba.com",
            type=CrawlerType.ALTERNATIVE_DESTINATION,
            selectors={
                "list_item": "div.callout",
                "name": "h1",
                "description": "p",
                "location": ".la-directions",
                "price": ".callout .precio",
                "image": ".callout img"
            }
        )
        super().__init__(config)
        self.max_zones = 100
        self.max_pages = 100

    async def crawl(self) -> List[Dict[str, Any]]:
        """Itera sobre páginas hasta que no haya más resultados."""
        hotels: List[Dict[str, Any]] = []
        for zone in range(1, self.max_zones):
            for page in range(self.max_pages):
                url = (f"{self.config.base_url}/reservar-hotel.htm"
                    f"?pageNum_hoteles={page}&zone={zone}")
                
                soup = await self._fetch_page(url)
                
                if not soup:
                    # error al fetch o al parse: lo registramos y salimos
                    self.log_error("No se pudo obtener o parsear la página", {"url": url})
                    break

                items = soup.select(self.config.selectors["list_item"])
                if not items:
                    # ya no hay hoteles en esta página: acabamos
                    break

                for item in items[:-2]:
                    link_tag = item.select_one('a.button[title="Ver detalles"]')
                    detail_href = link_tag["href"] if link_tag and link_tag.has_attr("href") else None
                    url = f"{self.config.base_url}/{detail_href}" if detail_href else None
                    soup_detail_page = await self._fetch_page(url)

                    parsed = self.parse_item(soup_detail_page)
                    if parsed:
                        hotels.append(parsed)

                # dormir entre páginas si quieres respetar rate limit
                await asyncio.sleep(self.config.rate_limit)

        return hotels

    def parse_item(self, item: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Parseo de cada hotel: nombre, descripción, precio e imagen."""
        try:
            name = self._extract_text(item, self.config.selectors["name"])
            if not name:
                return None

            description_item = item.select_one("article")
            description = "\n\n".join([
                description_text.get_text(strip=True) if description_text else ""
                for description_text in description_item.select(self.config.selectors["description"])
            ])

            price = self._extract_text(item, self.config.selectors["price"])
            img_tag = item.select_one(self.config.selectors["image"])
            image_url = img_tag["src"] if img_tag and img_tag.has_attr("src") else ""

            location = self._extract_text(item, self.config.selectors["location"])

            data = {
                "name": name.strip(),
                "type": self.config.type.value,
                "description": description.strip() if description else "",
                "location": location.strip() if location else "",
                "price": price,
                "image_url": urljoin(self.config.base_url, image_url),
                "source_url": "",
                "source": "cuba.travel"
            }

            if not self.validate_data(data):
                # Si faltan campos obligatorios, lo ignoramos
                return None

            return self.standardize_data(data)

        except Exception as e:
            self.log_error(f"Error parsing hotel item: {e}", {"item_html": str(item)})
            return None


class ViajeHotelesCubaCrawler(BaseSiteCrawler):
    """Crawler para información de provincias en viajehotelescuba.com"""
    
    def __init__(self):
        config = CrawlerConfig(
            name="viaje_hoteles_cuba_crawler",
            base_url="https://www.viajehotelescuba.com",
            type=CrawlerType.PROVINCE_INFO, 
            selectors={
                "list_item": ".provincia, .destino-card, .lugar-item",
                "name": "h2, h3, .titulo, .nombre-provincia",
                "description": ".descripcion, p, .info",
                "attractions": ".atracciones, .lugares, .sitios",
                "image": "img"
            }
        )
        super().__init__(config)
    
    async def crawl(self) -> List[Dict[str, Any]]:
        """Crawling de provincias cubanas"""
        destinations = []
        try:
            url = f"{self.config.base_url}/provincias"
            soup = await self._fetch_page(url)
            
            if soup:
                items = soup.select(self.config.selectors["list_item"])
                logger.info(f"Found {len(items)} provinces on viajehotelescuba.com")
                
                for item in items:
                    parsed_item = self.parse_item(item)
                    if parsed_item:
                        destinations.append(parsed_item)
                        
        except Exception as e:
            self.log_error(f"Error crawling viajehotelescuba.com: {str(e)}")
        
        return destinations
    
    def parse_item(self, item: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Parseo específico para provincias"""
        try:
            name = self._extract_text(item, self.config.selectors["name"])
            if not name:
                return None
                
            attractions = self._extract_text(item, self.config.selectors["attractions"])
            
            data = {
                "name": name,
                "type": self.config.type.value,  # Usa el tipo de crawler
                "description": self._extract_text(item, self.config.selectors["description"]),
                "attractions": attractions,
                "source": "viajehotelescuba.com"
            }
            
            if self.validate_data(data):
                return self.standardize_data(data)
                
        except Exception as e:
            self.log_error(f"Error parsing viajehotelescuba.com item: {str(e)}")
        
        return None


class BuenViajeCubaCrawler(BaseSiteCrawler):
    """Crawler para información detallada de destinos en buenviajeacuba.com"""
    
    def __init__(self):
        config = CrawlerConfig(
            name="buen_viaje_cuba_crawler",
            base_url="https://www.buenviajeacuba.com",
            type=CrawlerType.DESTINATION_DETAILS, 
            selectors={
                "list_item": ".destino-info, .lugar-detalle, .info-destino",
                "name": "h1, h2, h3, .titulo-destino",
                "description": ".descripcion, .info, p",
                "highlights": ".destacados, .puntos-interes",
                "tips": ".consejos, .tips"
            }
        )
        super().__init__(config)
    
    async def crawl(self) -> List[Dict[str, Any]]:
        """Crawling de información de destinos"""
        destinations = []
        try:
            url = f"{self.config.base_url}/informacion-destinos/"
            soup = await self._fetch_page(url)
            
            if soup:
                items = soup.select(self.config.selectors["list_item"])
                logger.info(f"Found {len(items)} destinations on buenviajeacuba.com")
                
                for item in items:
                    parsed_item = self.parse_item(item)
                    if parsed_item:
                        destinations.append(parsed_item)
                        
        except Exception as e:
            self.log_error(f"Error crawling buenviajeacuba.com: {str(e)}")
        
        return destinations
    
    def parse_item(self, item: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Parseo específico para información de destinos"""
        try:
            name = self._extract_text(item, self.config.selectors["name"])
            if not name:
                return None
                
            data = {
                "name": name,
                "type": self.config.type.value,  # Usa el tipo de crawler
                "description": self._extract_text(item, self.config.selectors["description"]),
                "highlights": self._extract_text(item, self.config.selectors["highlights"]),
                "tips": self._extract_text(item, self.config.selectors["tips"]),
                "source": "buenviajeacuba.com"
            }
            
            if self.validate_data(data):
                return self.standardize_data(data)
                
        except Exception as e:
            self.log_error(f"Error parsing buenviajeacuba.com item: {str(e)}")
        
        return None


class VisitCubaGoCrawler(BaseSiteCrawler):
    """Crawler para atracciones turísticas en visitcubago.com"""
    
    def __init__(self):
        config = CrawlerConfig(
            name="visit_cuba_go_crawler",
            base_url="https://visitcubago.com",
            type=CrawlerType.RATED_ATTRACTION, 
            selectors={
                "list_item": ".lugar-turistico, .atraccion, .destino-card",
                "name": "h2, h3, .titulo-lugar",
                "description": ".descripcion, p, .info-lugar",
                "category": ".categoria, .tipo",
                "rating": ".rating, .puntuacion",
                "location": ".ubicacion, .localizacion"
            }
        )
        super().__init__(config)
    
    async def crawl(self) -> List[Dict[str, Any]]:
        """Crawling de mejores lugares turísticos"""
        attractions = []
        try:
            url = f"{self.config.base_url}/mejores-lugares-turisticos-visitar-en-cuba/"
            soup = await self._fetch_page(url)
            
            if soup:
                items = soup.select(self.config.selectors["list_item"])
                logger.info(f"Found {len(items)} attractions on visitcubago.com")
                
                for item in items:
                    parsed_item = self.parse_item(item)
                    if parsed_item:
                        attractions.append(parsed_item)
                        
        except Exception as e:
            self.log_error(f"Error crawling visitcubago.com: {str(e)}")
        
        return attractions
    
    def parse_item(self, item: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Parseo específico para lugares turísticos"""
        try:
            name = self._extract_text(item, self.config.selectors["name"])
            if not name:
                return None
                
            # Extraer rating si existe
            rating_text = self._extract_text(item, self.config.selectors["rating"])
            rating = self._extract_rating(rating_text)
            
            data = {
                "name": name,
                "type": self.config.type.value,  # Usa el tipo de crawler
                "description": self._extract_text(item, self.config.selectors["description"]),
                "category": self._extract_text(item, self.config.selectors["category"]),
                "location": self._extract_text(item, self.config.selectors["location"]),
                "rating": rating,
                "source": "visitcubago.com"
            }
            
            if self.validate_data(data):
                return self.standardize_data(data)
                
        except Exception as e:
            self.log_error(f"Error parsing visitcubago.com item: {str(e)}")
        
        return None
    
    def _extract_rating(self, rating_text: str) -> Optional[float]:
        """Extrae rating numérico del texto"""
        if not rating_text:
            return None
        
        # Buscar números decimales en el texto
        rating_match = re.search(r'(\d+\.?\d*)', rating_text)
        if rating_match:
            try:
                return float(rating_match.group(1))
            except ValueError:
                pass
        return None


class SitiosTuristicosCrawler(BaseSiteCrawler):
    """Crawler para los 30 lugares de '30-lugares-para-conocer-en-cuba'"""
    
    def __init__(self):
        config = CrawlerConfig(
            name="sitios_turisticos_crawler",
            base_url="https://www.sitiosturisticos.es",
            type=CrawlerType.LANDMARK,
            
            selectors={
                "heading": "h3.elementor-heading-title.elementor-size-default",
                "text_block": ".elementor-widget-text-editor"
            }
        )
        super().__init__(config)
    
    async def crawl(self) -> List[Dict[str, Any]]:
        """Recorre todos los encabezados numerados y los parsea."""
        attractions: List[Dict[str, Any]] = []
        url = urljoin(self.config.base_url,
                      "/america/cuba/30-lugares-para-conocer-en-cuba/")
        soup = await self._fetch_page(url)
        if not soup:
            self.log_error("No se pudo obtener el HTML principal", {"url": url})
            return attractions
        
        # Seleccionamos todos los h3 y filtramos los que empiezan con 'N. '
        headings = soup.select(self.config.selectors["heading"])
        for h in headings:
            text = h.get_text(strip=True)
            if not re.match(r"^\d+\.\s", text):
                continue
            
            parsed = self.parse_item(h)
            if parsed:
                attractions.append(parsed)
        
        logger.info(f"{len(attractions)} lugares extraídos de sitiosturisticos.es")
        return attractions

    def parse_item(self, heading: Tag) -> Optional[Dict[str, Any]]:
        """Dado un <h3> numerado, extrae nombre, descripción y razón para visitar."""
        try:
            full_title = heading.get_text(strip=True)
            # 1. Separamos el número del nombre
            #    e.g. "1. La Habana" -> nombre="La Habana"
            name = re.sub(r"^\d+\.\s*", "", full_title)
            if not name:
                return None
            
            # Buscamos el siguiente bloque de texto que contiene la descripción
            text_block = heading.find_next_sibling(
                lambda tag: (isinstance(tag, Tag) and 
                             self.config.selectors["text_block"] in tag.get("class", []))
            )
            if not text_block:
                return None
            
            items = text_block.select("ul li p")

            if len(items) < 2:
                return None
            
            # Limpiamos los prefijos
            desc = items[0].get_text(" ", strip=True)
            desc = re.sub(r"^Descripción del destino:\s*", "", desc, flags=re.IGNORECASE)
            
            reason = items[1].get_text(" ", strip=True)
            reason = re.sub(r"^Razón para visitar:\s*", "", reason, flags=re.IGNORECASE)
            
            data = {
                "name": name,
                "type": self.config.type.value,
                "description": desc,
                "reason_to_visit": reason,
                "source": "sitiosturisticos.es",
                "crawl_date": datetime.now().isoformat()
            }
            
            if not self.validate_data(data):
                return None
            
            return self.standardize_data(data)
        
        except Exception as e:
            self.log_error(f"Error parseando item '{heading}': {e}")
            return None


class HabCulturalMuseosCrawler(BaseSiteCrawler):
    """Crawler para 'Museos y centros culturales' en habanacultural.ohc.cu"""

    def __init__(self):
        config = CrawlerConfig(
            name="habana_cultural_museos",
            base_url="http://habanacultural.ohc.cu",
            type=CrawlerType.LANDMARK,
            selectors={
                "heading": "div.post-bodycopy.clearfix div.accordion h3",
                "detail_block": "div.post-bodycopy.clearfix div.accordion h3 + div"
            }
        )
        super().__init__(config)
        self.max_pages = 4

    async def crawl(self) -> List[Dict[str, Any]]:
        resultados: List[Dict[str, Any]] = []
        for page in range(1, self.max_pages + 1):
            url = f"{self.config.base_url}/?page_id=103&page={page}"
            soup = await self._fetch_page(url)
            if not soup:
                self.log_error("No se pudo obtener o parsear la página", {"url": url})
                break

            headings = soup.select(self.config.selectors["heading"])
            if not headings:
                # Ya no hay más museos en páginas superiores
                break

            for h in headings:
                parsed = self.parse_item(h)
                if parsed:
                    resultados.append(parsed)

            await asyncio.sleep(self.config.rate_limit)

        return resultados

    def parse_item(self, heading: Tag) -> Optional[Dict[str, Any]]:
        try:
            name = heading.get_text(strip=True)
            if not name:
                return None

            # Bloque de detalles asociado
            block = heading.find_next_sibling("div")
            if not block:
                return None

            # Extraer pares Etiqueta: Valor
            info: Dict[str, str] = {}
            for p in block.select("p"):
                strong = p.find("strong")
                if strong and strong.next_sibling:
                    label = strong.get_text(strip=True).rstrip(":").lower().replace(" ", "_")

                    if label == "e-mail":
                        continue

                    value = strong.next_sibling.strip()
                    info[label] = value

            data: Dict[str, Any] = {
                "name": name,
                "type": self.config.type.value,
                "description": info.get("tema", ""),
                "entrance_fee": info.get("entrada", ""),
                "opening_hours": info.get("horario", ""),
                "address": info.get("dirección", ""),
                "phone": info.get("teléfono", ""),
                "source_url": urljoin(self.config.base_url, heading.find("a")["href"]),
                "crawl_date": datetime.now().isoformat()
            }

            if not self.validate_data(data):
                return None

            return self.standardize_data(data)

        except Exception as e:
            self.log_error(f"Error parseando museo '{heading}': {e}")
            return None

