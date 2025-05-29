from scrapy.crawler import CrawlerProcess
from app.data_managers.crawler import TourismSpider
import json
import sys
import logging
from scrapy.spidermiddlewares.httperror import HttpErrorMiddleware
from scrapy.exceptions import IgnoreRequest

logger = logging.getLogger(__name__)

class CustomErrorMiddleware(HttpErrorMiddleware):
    def process_spider_input(self, response, spider):
        # Only ignore severe server errors, not client errors like 404
        if response.status >= 500:
            logger.warning(f"Server error {response.status} on {response.url}")
            raise IgnoreRequest(f"HTTP status {response.status}")
        elif response.status == 404:
            logger.info(f"Page not found (404) on {response.url} - this is normal, continuing...")
            return None
        elif response.status >= 400:
            logger.warning(f"Client error {response.status} on {response.url} - continuing...")
            return None
        return None

def run_spider(output_file):
    process = CrawlerProcess(settings={
        'USER_AGENT': 'TourismBot (+http://www.yourdomain.com)',
        'ROBOTSTXT_OBEY': True,
        'CONCURRENT_REQUESTS': 16,
        'DOWNLOAD_DELAY': 1,
        'COOKIES_ENABLED': False,
        'RETRY_TIMES': 2,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 522, 524, 408, 429],
        'SPIDER_MIDDLEWARES': {
            'scrapy.spidermiddlewares.httperror.HttpErrorMiddleware': None,
            __name__ + '.CustomErrorMiddleware': 543,
        },
        'DOWNLOAD_TIMEOUT': 15,
        'DNS_TIMEOUT': 10,
        # Allow 404 responses to be passed to the spider
        'HTTPERROR_ALLOWED_CODES': [404],
        'FEEDS': {
            output_file: {
                'format': 'json',
                'encoding': 'utf8',
                'indent': 2,
            }
        }
    })
    process.crawl(TourismSpider)
    process.start()