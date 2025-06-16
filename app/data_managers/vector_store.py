from typing import List, Dict
from sentence_transformers import SentenceTransformer
import numpy as np
import os
import json
from datetime import datetime
import pickle

class VectorStore:
    """Vector store for tourism domain data with specialized handling for museums and excursions"""
    
    def __init__(self, persist_dir: str):
        self.persist_dir = persist_dir
        
        # Define directories for each collection type and their domain focus
        self.domain_config = {
            'museums': {
                'dir': os.path.join(persist_dir, 'museums'),
                'categories': ['art', 'history', 'science', 'culture'],
                'weight': 1.2  # Boost museum matches in searches
            },
            'excursions': {
                'dir': os.path.join(persist_dir, 'excursions'),
                'categories': ['urban', 'nature', 'cultural'],
                'weight': 1.1  # Slight boost for excursions
            },
            'destinations': {
                'dir': os.path.join(persist_dir, 'destinations'),
                'categories': ['urban', 'nature', 'cultural'],
                'weight': 1.0  # Base weight
            }
        }
        
        # Ensure collection directories exist
        for config in self.domain_config.values():
            os.makedirs(config['dir'], exist_ok=True)
            
        # Initialize sentence transformer
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def _encode_text(self, text: str) -> List[float]:
        """Convert text to embeddings vector using sentence-transformers"""
        # Clean and normalize text
        text = self._preprocess_text(text)
        
        # Transform text to embedding vector
        vector = self.model.encode(text)
        return vector.tolist()

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text with domain-specific cleaning and normalization"""
        if not text:
            return ""
            
        # Basic cleaning
        text = text.lower().strip()
        
        # Normalize domain-specific terms
        replacements = {
            'museo': 'museum',
            'galería': 'gallery',
            'exposición': 'exhibition',
            'excursión': 'excursion',
            'visita guiada': 'guided tour',
            'recorrido': 'tour'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
            
        return text

    def _prepare_document(self, item: Dict) -> Dict:
        """Prepare a document for indexing with enhanced metadata"""
        # Combine relevant fields for embedding
        text_for_embedding = f"{item['name']} "
        
        # Add type-specific fields
        if item['type'] == 'museum':
            text_for_embedding += self._prepare_museum_text(item)
        elif item['type'] == 'excursion':
            text_for_embedding += self._prepare_excursion_text(item)
        else:  # destination
            text_for_embedding += self._prepare_destination_text(item)
        
        # Create enhanced document
        return {
            'id': item['id'],
            'embedding': self._encode_text(text_for_embedding),
            'metadata': {
                'name': item['name'],
                'type': item['type'],
                'domain_category': item.get('domain_category', []),
                'location': item.get('location', {}),
                'url': item.get('url', ''),
                'image_url': item.get('image_url', ''),
                'source': item.get('source', ''),
                'source_info': item.get('source_info', {}),
                'last_updated': item.get('last_updated'),
                **self._get_type_specific_metadata(item)
            },
            'document': item['description']
        }
    
    def _prepare_museum_text(self, item: Dict) -> str:
        """Prepare museum-specific text for embedding"""
        collections = ', '.join(item.get('collections', []))
        services = ', '.join(item.get('services', []))
        return f"{item['description']} Collections: {collections} Services: {services}"
    
    def _prepare_excursion_text(self, item: Dict) -> str:
        """Prepare excursion-specific text for embedding"""
        included = ', '.join(item.get('included_services', []))
        return f"{item['description']} Level: {item.get('difficulty_level', '')} Services: {included}"
    
    def _prepare_destination_text(self, item: Dict) -> str:
        """Prepare destination-specific text for embedding"""
        activities = ', '.join(item.get('activities', []))
        return f"{item['description']} Activities: {activities}"

    def cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        a = np.array(a)
        b = np.array(b)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def search(self, query: str, top_k: int = 5, collection_type: str = None) -> List[Dict]:
        """Search for most similar items to query"""
        query_vector = self._encode_text(query)
        results = []
        
        # Determine which collections to search
        collections = [collection_type] if collection_type else self.domain_config.keys()
        
        for collection in collections:
            items = self._load_items(collection)
            weight = self.domain_config[collection]['weight']
            
            for item in items:
                score = self.cosine_similarity(query_vector, item['embedding']) * weight
                results.append({
                    'item': item,
                    'score': score
                })
        
        # Sort by score and return top k
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]

    def _get_type_specific_metadata(self, item: Dict) -> Dict:
        """Extract type-specific metadata"""
        if item['type'] == 'museum':
            return {
                'schedule': json.dumps(item.get('schedule', {'type': 'unknown'})),
                'price': json.dumps(item.get('price', {'type': 'unknown'})),
                'collections': json.dumps(item.get('collections', [])),
                'services': json.dumps(item.get('services', [])),
                'accessibility': item.get('accessibility', '')
            }
        elif item['type'] == 'excursion':
            return {
                'duration': json.dumps(item.get('duration', {'type': 'unknown'})),
                'price': json.dumps(item.get('price', {'type': 'unknown'})),
                'difficulty_level': item.get('difficulty_level', 'unknown'),
                'included_services': json.dumps(item.get('included_services', [])),
                'required_items': json.dumps(item.get('required_items', [])),
                'meeting_point': item.get('meeting_point', ''),
                'schedule': json.dumps(item.get('schedule', {'type': 'unknown'})),
                'max_participants': str(item.get('max_participants')) if item.get('max_participants') is not None else None
            }
        else:  # destination
            return {
                'coordinates': json.dumps(item.get('coordinates', {})),
                'activities': json.dumps(item.get('activities', []))
            }

    def _save_item(self, collection_name: str, doc: Dict):
        """Save a single document to its respective collection directory."""
        collection_path = self.domain_config[collection_name]['dir']
        file_path = os.path.join(collection_path, f"{doc['id']}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=4)

    def _load_items(self, collection_name: str) -> List[Dict]:
        """Load all documents from a given collection directory."""
        collection_path = self.domain_config[collection_name]['dir']
        loaded_docs = []
        if not os.path.exists(collection_path):
            return []
            
        for filename in os.listdir(collection_path):
            if filename.endswith('.json'):
                file_path = os.path.join(collection_path, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        loaded_docs.append(json.load(f))
                except json.JSONDecodeError as e:
                    print(f"Error loading {file_path}: {e}")
        return loaded_docs

    def add_items(self, items: List[Dict]):
        """Add items to appropriate collections."""
        for item in items:
            # Prepare document with embedding and metadata
            item_type = item.get('type', 'destinations')  # Default to destinations
            if item_type not in self.domain_config:
                print(f"Warning: Unknown item type {item_type}, using 'destinations'")
                item_type = 'destinations'

            doc = self._prepare_document(item)
            self._save_item(item_type, doc)

