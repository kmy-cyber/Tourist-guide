from typing import List, Dict
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import os
import json
from datetime import datetime
import pickle
import math

class VectorStore:
    def __init__(self, persist_dir: str):
        self.persist_dir = persist_dir
        
        # Define directories for each collection type
        self.collection_dirs = {
            'museums': os.path.join(persist_dir, 'museums'),
            'excursions': os.path.join(persist_dir, 'excursions'),
            'destinations': os.path.join(persist_dir, 'destinations')
        }
        
        # Ensure collection directories exist
        for col_dir in self.collection_dirs.values():
            os.makedirs(col_dir, exist_ok=True)
            
        # Initialize TF-IDF vectorizer
        self.vectorizer = TfidfVectorizer(
            max_features=512,  # Limit features to control vector size
            stop_words='english',  # Remove common English stop words
            ngram_range=(1, 2),  # Use unigrams and bigrams
            min_df=2,  # Minimum document frequency
            max_df=0.95  # Maximum document frequency
        )
        
        # Load or create vectorizer state
        self.vectorizer_path = os.path.join(persist_dir, 'tfidf_vectorizer.pkl')
        if os.path.exists(self.vectorizer_path):
            with open(self.vectorizer_path, 'rb') as f:
                self.vectorizer = pickle.load(f)
        else:
            print("Vectorizer not found, it will be fitted on the first `add_items` call.")

    def _encode_text(self, text: str) -> List[float]:
        """Convert text to TF-IDF vector"""
        # If the vectorizer has not been fitted, it won't have a vocabulary.
        # This check is crucial for handling the first time a text is encoded
        # before any items have been added to the store.
        if not hasattr(self.vectorizer, 'vocabulary_') or not self.vectorizer.vocabulary_:
            # Fit a dummy text if vocabulary is empty to prevent errors during transformation.
            # In a real scenario, you'd likely want the vectorizer to be fitted on a corpus
            # before querying or ensuring all data is added before initial search.
            # For this context, we will rely on `add_items` to fit it.
            # If `_encode_text` is called before `add_items`, it will train on the single text.
            self.vectorizer.fit([text])
            with open(self.vectorizer_path, 'wb') as f:
                pickle.dump(self.vectorizer, f)
        
        # Transform text to TF-IDF vector
        vector = self.vectorizer.transform([text])
        return vector.toarray()[0].tolist()

    def _prepare_document(self, item: Dict) -> Dict:
        """Prepare a document for indexing"""
        # Combine relevant fields for embedding
        text_for_embedding = f"{item['name']} "
        
        # Add type-specific fields to the embedding text
        if item['type'] == 'museum':
            collections = ', '.join(item.get('collections', []))
            services = ', '.join(item.get('services', []))
            text_for_embedding += f"{item['description']} {collections} {services}"
        elif item['type'] == 'excursion':
            included = ', '.join(item.get('included_services', []))
            text_for_embedding += f"{item['description']} {item.get('difficulty_level', '')} {included}"
        else:  # destination
            activities = ', '.join(item.get('activities', []))
            text_for_embedding += f"{item['description']} {activities}"
        
        return {
            'id': item['id'],
            'embedding': self._encode_text(text_for_embedding),
            'metadata': {
                'name': item['name'],
                'type': item['type'],
                'location': item.get('location', ''),
                'url': item.get('url', ''),
                'image_url': item.get('image_url', ''),
                'source': item.get('source', ''),
                'last_updated': item.get('last_updated'),
                # Add structured data based on type
                **self._get_type_specific_metadata(item)
            },
            'document': item['description']
        }
    
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
        collection_path = self.collection_dirs[collection_name]
        file_path = os.path.join(collection_path, f"{doc['id']}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=4)
        # print(f"Saved {doc['id']} to {file_path}") # Debugging

    def _load_items(self, collection_name: str) -> List[Dict]:
        """Load all documents from a given collection directory."""
        collection_path = self.collection_dirs[collection_name]
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
        # First, update vectorizer with all texts
        all_texts = []
        for item in items:
            text = f"{item['name']} {item['description']}"
            if 'collections' in item:
                text += ' ' + ' '.join(item['collections'])
            if 'services' in item:
                text += ' ' + ' '.join(item['services'])
            if 'included_services' in item:
                text += ' ' + ' '.join(item['included_services'])
            if 'activities' in item:
                text += ' ' + ' '.join(item['activities'])
            all_texts.append(text)
        
        # Fit vectorizer with all texts
        if all_texts:
            self.vectorizer.fit(all_texts)
            # Save the updated vectorizer
            with open(self.vectorizer_path, 'wb') as f:
                pickle.dump(self.vectorizer, f)
        
        # Group items by type and save them
        for item in items:
            doc = self._prepare_document(item)
            collection_key = f"{item['type']}s"  # Convert type to collection name (e.g., 'museum' -> 'museums')
            if collection_key in self.collection_dirs:
                self._save_item(collection_key, doc)
            else:
                print(f"Warning: Item type '{item['type']}' does not have a defined collection directory.")

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        np_vec1 = np.array(vec1)
        np_vec2 = np.array(vec2)

        dot_product = np.dot(np_vec1, np_vec2)
        norm_vec1 = np.linalg.norm(np_vec1)
        norm_vec2 = np.linalg.norm(np_vec2)

        if norm_vec1 == 0 or norm_vec2 == 0:
            return 0.0  # Handle zero vectors to avoid division by zero
        
        return dot_product / (norm_vec1 * norm_vec2)

    def search(self, query: str, n_results: int = 3, filters: Dict = None) -> List[Dict]:
        """Search across collections with optional filters."""
        query_embedding = self._encode_text(query)
        all_results = []
        
        # Search in each collection
        for collection_name in self.collection_dirs.keys():
            items_in_collection = self._load_items(collection_name)
            
            for item_doc in items_in_collection:
                # Apply filters if provided
                apply_item = True
                if filters and collection_name in filters:
                    for filter_key, filter_value in filters[collection_name].items():
                        # The metadata values are stored as JSON strings if they are complex types
                        stored_value = item_doc['metadata'].get(filter_key)
                        
                        # Handle JSON string parsing for comparison
                        try:
                            if isinstance(stored_value, str):
                                stored_value = json.loads(stored_value)
                        except (json.JSONDecodeError, TypeError):
                            # If it's not a valid JSON string or already parsed, use as is
                            pass

                        # Basic equality check for filtering
                        if stored_value != filter_value:
                            apply_item = False
                            break
                
                if apply_item:
                    # Calculate cosine distance
                    # Cosine distance = 1 - cosine_similarity. Lower distance is better.
                    distance = 1 - self._cosine_similarity(query_embedding, item_doc['embedding'])
                    
                    # Parse JSON strings in metadata back to Python objects for the returned result
                    parsed_metadata = {}
                    for key, value in item_doc['metadata'].items():
                        try:
                            parsed_metadata[key] = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            parsed_metadata[key] = value

                    all_results.append({
                        'id': item_doc['id'],
                        'distance': distance,
                        'metadata': parsed_metadata,
                        'document': item_doc['document']
                    })
        
        # Sort by distance (ascending) and return top n_results
        all_results.sort(key=lambda x: x['distance'])
        return all_results[:n_results]

