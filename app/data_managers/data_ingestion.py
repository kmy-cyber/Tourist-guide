"""
Data ingestion coordinator for tourism system.
Handles the flow of data from crawler to vector store.
"""

import json
import os
import glob
from datetime import datetime
from typing import List, Dict
import logging
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from .crawler import TourismSpider
from .vector_store import VectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataIngestionCoordinator:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.raw_data_dir = os.path.join(data_dir, 'raw')
        self.vector_store = VectorStore(os.path.join(data_dir, 'vectors'))
        self.min_required_items = 10  # Minimum number of items needed
        
        # Ensure directories exist
        os.makedirs(self.raw_data_dir, exist_ok=True)
        
    def run_ingestion(self, use_subprocess=True):
        """Run the complete ingestion pipeline
        
        Args:
            use_subprocess: If True, use subprocess approach (safer for web apps)
        """
        logger.info("Starting data ingestion pipeline...")
        
        try:
            # 1. Crawl fresh data - default to subprocess for safety
            if use_subprocess:
                crawled_data = self._run_crawler_subprocess()
            else:
                crawled_data = self._run_crawler()
            
            # Verify we have enough data
            if len(crawled_data) < self.min_required_items:
                logger.warning(f"Crawler returned only {len(crawled_data)} items, which is below minimum threshold of {self.min_required_items}")
                
                # Try the other approach if the first one failed
                if use_subprocess:
                    logger.info("Trying direct approach as fallback...")
                    fallback_data = self._run_crawler()
                else:
                    logger.info("Trying subprocess approach as fallback...")
                    fallback_data = self._run_crawler_subprocess()
                
                if len(fallback_data) > len(crawled_data):
                    crawled_data = fallback_data
                
                # Load backup data if still insufficient
                if len(crawled_data) < self.min_required_items:
                    backup_data = self._load_backup_data()
                    if backup_data:
                        logger.info(f"Using {len(backup_data)} items from backup data")
                        crawled_data.extend(backup_data)
            
            # 2. Save raw data
            raw_data_path = self._save_raw_data(crawled_data)
            
            # 3. Process and clean data
            processed_data = self._process_data(crawled_data)
            
            # 4. Add to vector store
            self._add_to_vector_store(processed_data)
            
            logger.info(f"Data ingestion pipeline completed successfully with {len(processed_data)} items")
            return raw_data_path
            
        except Exception as e:
            logger.error(f"Error in data ingestion pipeline: {str(e)}")
            raise
        
    def _run_crawler(self) -> List[Dict]:
        """Run the tourism spider to collect data"""
        logger.info("Starting crawler...")
        
        # Create output file path with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(self.raw_data_dir, f'crawl_{timestamp}.json')
        
        try:
            # Configure Scrapy settings
            settings = {
                'USER_AGENT': 'TourismBot (+http://www.yourdomain.com)',
                'ROBOTSTXT_OBEY': True,
                'CONCURRENT_REQUESTS': 16,
                'DOWNLOAD_DELAY': 1,
                'COOKIES_ENABLED': False,
                'RETRY_TIMES': 2,
                'RETRY_HTTP_CODES': [500, 502, 503, 504, 522, 524, 408, 429],
                'DOWNLOAD_TIMEOUT': 15,
                'DNS_TIMEOUT': 10,
                'HTTPERROR_ALLOWED_CODES': [404],  # Allow 404s to be handled by spider
                'LOG_LEVEL': 'INFO',
                'FEEDS': {
                    output_file: {
                        'format': 'json',
                        'encoding': 'utf8',
                        'indent': 2,
                    }
                }
            }
            
            # Create and run the crawler process
            process = CrawlerProcess(settings)
            
            # Track crawler completion
            crawler_stats = {'completed': False, 'items_scraped': 0}
            
            def crawler_finished(spider, reason):
                crawler_stats['completed'] = True
                crawler_stats['items_scraped'] = spider.crawler.stats.get_value('item_scraped_count', 0)
                logger.info(f"Crawler finished with reason: {reason}, items scraped: {crawler_stats['items_scraped']}")
            
            # Connect to spider_closed signal
            from scrapy import signals
            crawler = process.create_crawler(TourismSpider)
            crawler.signals.connect(crawler_finished, signal=signals.spider_closed)
            
            # Start the crawler
            deferred = process.crawl(crawler)
            
            # Check if the output file was created
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    crawled_data = json.load(f)
                logger.info(f"Crawler finished, collected {len(crawled_data)} items from {output_file}")
                return crawled_data
            else:
                # If the specific file doesn't exist, look for any recent crawl files
                logger.warning(f"Expected output file {output_file} not found, searching for recent crawl files...")
                recent_files = self._find_recent_crawl_files()
                
                if recent_files:
                    latest_file = recent_files[0]  # Most recent file
                    logger.info(f"Found recent crawl file: {latest_file}")
                    with open(latest_file, 'r', encoding='utf-8') as f:
                        crawled_data = json.load(f)
                    logger.info(f"Loaded {len(crawled_data)} items from recent crawl file")
                    return crawled_data
                else:
                    logger.error("No crawl output files found")
                    return []
        except Exception as e:
            logger.error(f"Error in data ingestion pipeline: {str(e)}")
            raise
    
    def _run_crawler_subprocess(self) -> List[Dict]:
        """Fallback method using subprocess approach"""
        logger.info("Starting crawler using subprocess approach...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(self.raw_data_dir, f'crawl_subprocess_{timestamp}.json')
        
        try:
            import subprocess
            import sys
            from pathlib import Path
            
            # Create a simple run script content
            script_content = f'''
import os
import sys
import json
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from scrapy.crawler import CrawlerProcess
    from app.data_managers.crawler import TourismSpider
    from scrapy.utils.project import get_project_settings
    from scrapy import signals
    from twisted.internet import reactor
    import logging
    
    def spider_closed(spider, reason):
        """Ensure proper cleanup when spider closes"""
        if reactor.running:
            reactor.stop()
    
    def run_spider():
        settings = {{
            'USER_AGENT': 'TourismBot (+http://www.yourdomain.com)',
            'ROBOTSTXT_OBEY': True,
            'CONCURRENT_REQUESTS': 8,
            'DOWNLOAD_DELAY': 1.5,
            'COOKIES_ENABLED': False,
            'RETRY_TIMES': 2,
            'RETRY_HTTP_CODES': [500, 502, 503, 504, 522, 524, 408, 429],
            'DOWNLOAD_TIMEOUT': 15,
            'DNS_TIMEOUT': 10,
            'HTTPERROR_ALLOWED_CODES': [404],
            'LOG_LEVEL': 'INFO',
            'FEED_FORMAT': 'jsonlines',
            'FEED_EXPORT_ENCODING': 'utf-8',
            'FEED_URI': r"{output_file}",
            'FEED_EXPORT_INDENT': None,
            'FEED_STORE_EMPTY': False,
            'FEEDS': {{
                r"{output_file}": {{
                    'format': 'json',
                    'encoding': 'utf-8',
                    'indent': 2,
                    'item_export_kwargs': {{
                        'ensure_ascii': False
                    }}
                }}
            }}
        }}
        
        try:
            process = CrawlerProcess(settings)
            crawler = process.create_crawler(TourismSpider)
            crawler.signals.connect(spider_closed, signal=signals.spider_closed)
            process.crawl(crawler)
            process.start()
        except Exception as e:
            print(f"Error in spider execution: {{str(e)}}")
            raise
        
    if __name__ == "__main__":
        run_spider()
        
except Exception as e:
    print(f"Error running spider: {{str(e)}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''
            
            # Write script to a temporary file
            temp_script = os.path.join(self.raw_data_dir, f'temp_spider_{timestamp}.py')
            with open(temp_script, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            logger.info(f"Running subprocess spider with output file: {output_file}")
            
            # Run the script with increased timeout
            result = subprocess.run(
                [sys.executable, temp_script],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
                cwd=os.path.dirname(temp_script)
            )
            
            # Log subprocess output for debugging
            if result.stdout:
                logger.info("Subprocess stdout: " + result.stdout[:500] + "..." if len(result.stdout) > 500 else result.stdout)
            if result.stderr:
                for line in result.stderr.splitlines():
                    if 'WARNING' in line:
                        logger.warning(f"Subprocess: {line}")
                    elif 'ERROR' in line:
                        logger.error(f"Subprocess: {line}")
                    else:
                        logger.debug(f"Subprocess: {line}")
            
            # Clean up temporary script
            try:
                os.remove(temp_script)
            except Exception as cleanup_error:
                logger.warning(f"Could not clean up temp script: {cleanup_error}")
            
            # Check results
            if result.returncode == 0 and os.path.exists(output_file):
                try:
                    # Read and validate JSON
                    with open(output_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Check if the content is empty or malformed
                        if not content.strip():
                            logger.warning("Output file is empty")
                            return []
                        # Try to parse JSON
                        crawled_data = json.loads(content)
                        if isinstance(crawled_data, list):
                            logger.info(f"Subprocess crawler finished successfully, collected {len(crawled_data)} items")
                            return crawled_data
                        else:
                            logger.error("Output is not a JSON array")
                            return []
                except json.JSONDecodeError as json_error:
                    logger.error(f"Failed to parse JSON from output file: {json_error}")
                    # Try to fix malformed JSON
                    try:
                        with open(output_file, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            # Remove last line if it's incomplete
                            content = ''.join(lines[:-1] if lines else [])
                            if content.strip():
                                # Ensure it's a valid JSON array
                                content = content.rstrip().rstrip(',')  # Remove trailing comma if any
                                content = f"[{content}]"
                                crawled_data = json.loads(content)
                                logger.info(f"Recovered {len(crawled_data)} items from partial JSON")
                                return crawled_data
                    except:
                        logger.error("Could not recover from malformed JSON")
                        return []
                    return []
            else:
                logger.error(f"Subprocess crawler failed or no output file found. Return code: {result.returncode}")
                return []
                
        except subprocess.TimeoutExpired:
            logger.error("Subprocess crawler timed out")
            # Check if partial results exist
            if os.path.exists(output_file):
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            # Try to fix potential JSON issues
                            content = content.rstrip().rstrip(',')  # Remove trailing comma if any
                            content = f"[{content}]"  # Ensure it's an array
                            partial_data = json.loads(content)
                            if isinstance(partial_data, list):
                                logger.info(f"Recovered {len(partial_data)} items from timeout")
                                return partial_data
                except Exception as e:
                    logger.error(f"Failed to recover partial data after timeout: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error running subprocess crawler: {str(e)}")
            return []
    
    def _find_recent_crawl_files(self) -> List[str]:
        """Find recent crawl files in the raw data directory"""
        # Look for files matching various crawl patterns
        crawl_patterns = [
            os.path.join(self.raw_data_dir, 'crawl_*.json'),
            os.path.join(self.raw_data_dir, 'crawl_subprocess_*.json')
        ]
        
        crawl_files = []
        for pattern in crawl_patterns:
            crawl_files.extend(glob.glob(pattern))
        
        if not crawl_files:
            return []
        
        # Sort by modification time (most recent first)
        crawl_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        # Only return files from the last hour to ensure they're recent
        import time
        current_time = time.time()
        recent_files = []
        
        for file_path in crawl_files:
            file_time = os.path.getmtime(file_path)
            if current_time - file_time < 3600:  # Within last hour
                recent_files.append(file_path)
        
        return recent_files
            
    def _load_backup_data(self) -> List[Dict]:
        """Load most recent backup data if available"""
        try:
            # Find most recent data file
            data_files = [f for f in os.listdir(self.raw_data_dir) 
                         if f.startswith('tourism_data_') and f.endswith('.json')]
            if not data_files:
                return []
                
            latest_file = max(data_files)
            with open(os.path.join(self.raw_data_dir, latest_file), 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading backup data: {str(e)}")
            return []
        
    def _save_raw_data(self, data: List[Dict]) -> str:
        """Save raw data to file system"""
        output_file = os.path.join(
            self.raw_data_dir,
            f'tourism_data_{datetime.now().strftime("%Y%m%d")}.json'
        )
        
        try:
            # Ensure data is a list
            if not isinstance(data, list):
                logger.warning("Data is not a list, wrapping it")
                data = [data] if data else []
            
            # Validate each item is a dict
            validated_data = []
            for item in data:
                if isinstance(item, dict):
                    validated_data.append(item)
                else:
                    logger.warning(f"Skipping invalid item (not a dict): {str(item)[:100]}...")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(validated_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Raw data saved to {output_file} ({len(validated_data)} items)")
            return output_file
        except Exception as e:
            logger.error(f"Error saving raw data: {str(e)}")
            raise
        
    def _process_data(self, items: List[Dict]) -> List[Dict]:
        """Process and validate crawled data"""
        processed_items = []
        
        for item in items:
            # Skip items without required fields
            if not all(k in item for k in ['name', 'type', 'description']):
                logger.warning(f"Skipping item due to missing required fields: {item.get('name', 'UNKNOWN')}")
                continue
                
            # Generate unique ID if not present
            if 'id' not in item:
                item['id'] = f"{item['type']}_{len(processed_items)}"
            
            # Add timestamp if not present
            if 'last_updated' not in item:
                item['last_updated'] = datetime.now().isoformat()
                
            processed_items.append(item)
            
        logger.info(f"Processed {len(processed_items)} items")
        return processed_items
        
    def _add_to_vector_store(self, items: List[Dict]):
        """Add processed items to vector store"""
        try:
            # Group items by type for batch processing
            items_by_type = {}
            for item in items:
                item_type = item['type']
                if item_type not in items_by_type:
                    items_by_type[item_type] = []
                items_by_type[item_type].append(item)
            
            # Add items by type
            for item_type, type_items in items_by_type.items():
                logger.info(f"Adding {len(type_items)} {item_type} items to vector store")
                self.vector_store.add_items(type_items)
                
            logger.info("All items added to vector store successfully")
            
        except Exception as e:
            logger.error(f"Error adding items to vector store: {str(e)}")
            raise