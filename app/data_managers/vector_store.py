import re
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import os
import json
from datetime import datetime
import pickle
import logging

logger = logging.getLogger(__name__)

class VectorStore:
    """Vector store for tourism domain data with specialized handling for museums and excursions"""
    
    def __init__(self, persist_dir: str):
        self.persist_dir = persist_dir
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.collections = set()
        
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
        for name, config in self.domain_config.items():
            os.makedirs(config['dir'], exist_ok=True)
            self.collections.add(name)

    def search(self, 
            query: str, 
            k: int = 5, 
            collections: Optional[List[str]] = None,
            similarity_threshold: Optional[float] = None
        ) -> List[Dict]:
        """Search for items most similar to the query text.

        Args:
            query: The query text
            k: Number of results to return
            collections: Optional list of collections to search in. If None, searches all.
            similarity_threshold: Optional minimum similarity score threshold

        Returns:
            List of items sorted by similarity score
        """
        # Get query embedding and process collections
        query_embedding = self.model.encode(query).tolist()
        results = self._search_with_embedding(query_embedding, k, collections, similarity_threshold)
        return results

    def _search_with_embedding(
            self,
            query_embedding: List[float],
            k: int,
            collections: Optional[List[str]] = None,
            similarity_threshold: Optional[float] = None
        ) -> List[Dict]:
        """Internal method to search using a pre-computed embedding"""
        results = []
        for collection in collections or self.collections:
            if collection not in self.domain_config:
                continue
                
            # Process items in collection, re-embedding if needed
            items = self._process_collection(collection, query_embedding)
            if not items:
                continue

            # Calculate similarities
            weight = self.domain_config[collection]['weight']
            item_embeddings = np.array([item['embedding'] for item in items])
            similarities = cosine_similarity([query_embedding], item_embeddings)[0] * weight

            # Add similarity scores
            for item, score in zip(items, similarities):
                if similarity_threshold is None or score >= similarity_threshold:
                    result = {**item}
                    result.pop('embedding', None)  # Remove embedding from result
                    result['similarity'] = float(score)
                    result['collection'] = collection
                    results.append(result)

        # Sort by similarity and take top k
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:k]

    def _process_collection(self, collection: str, query_embedding: List[float]) -> List[Dict]:
        """Process a single collection and return matching items"""
        items = self._load_items(collection)
        self.current_collection = collection  # Set current collection for _validate_and_fix_embeddings
        return self._validate_and_fix_embeddings(items, query_embedding)

    def _validate_and_fix_embeddings(self, items: List[Dict], query_embedding: List[float]) -> List[Dict]:
        """Process items and fix embeddings to match query embedding dimension"""
        valid_items = []
        needs_update = False
        query_dim = len(query_embedding)
        
        for item in items:
            if ('embedding' not in item or 
                not isinstance(item['embedding'], list) or
                len(item['embedding']) != query_dim):
                # Regenerate embedding
                text = self._prepare_text_for_embedding(item)
                item['embedding'] = self.model.encode(text).tolist()
                needs_update = True
            valid_items.append(item)
            
        if needs_update and hasattr(self, 'current_collection'):
            self._save_items(self.current_collection, valid_items)
            
        return valid_items

    def _prepare_text_for_embedding(self, item: Dict) -> str:
        """Prepare item text for embedding generation"""
        # Concatenate relevant fields for embedding
        fields = ['name', 'description', 'category', 'location']
        text_parts = []
        
        for field in fields:
            if field in item and item[field]:
                text_parts.append(str(item[field]))
                
        return ' '.join(text_parts)

    def _save_items(self, collection: str, items: List[Dict]):
        """Save items in a collection"""
        for item in items:
            self._save_item(collection, item)

    def _save_item(self, collection_name: str, doc: Dict):
        """Save a single document to its collection directory"""
        collection_path = self.domain_config[collection_name]['dir']
        file_path = os.path.join(collection_path, f"{doc['id']}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)

    def _load_items(self, collection_name: str) -> List[Dict]:
        """Load all documents from a given collection directory"""
        collection_path = self.domain_config[collection_name]['dir']
        loaded_docs = []
        if not os.path.exists(collection_path):
            return []
            
        for filename in os.listdir(collection_path):
            if filename.endswith('.json') and not filename.startswith("index"):
                file_path = os.path.join(collection_path, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        loaded_docs.append(json.load(f))
                except json.JSONDecodeError as e:
                    print(f"Error loading {file_path}: {e}")
        return loaded_docs

    def add_items(self, items: List[Dict]):
        """Add or update items in appropriate collections"""
        for item in items:
            try:
                # Determinar la colección basada en el tipo de item
                collection = self._determine_collection(item)
                if not collection:
                    logger.warning(f"Could not determine collection for item: {item.get('id', 'unknown')}")
                    continue
                
                # Preparar el texto para embedding
                text = self._prepare_text_for_embedding(item)
                
                # Generar embedding
                embedding = self.model.encode(text).tolist()
                
                # Añadir embedding al item
                item['embedding'] = embedding
                
                # Guardar en la colección apropiada
                self._save_item(collection, item)
                
            except Exception as e:
                logger.error(f"Error adding item {item.get('id', 'unknown')}: {str(e)}")

    def store(self, collection: str, items: List[Dict], regenerate_embeddings: bool = False):
        """Store items in the vector store, optionally regenerating embeddings"""
        if collection not in self.domain_config:
            raise ValueError(f"Unknown collection: {collection}")
            
        # Process and store each item
        for item in items:
            if not isinstance(item, dict) or 'id' not in item:
                continue
                
            try:
                # Generar o regenerar embedding si es necesario
                if regenerate_embeddings or 'embedding' not in item:
                    text = self._prepare_text_for_embedding(item)
                    item['embedding'] = self.model.encode(text).tolist()
                
                # Asegurar que tengamos toda la metadata necesaria
                item['timestamp'] = datetime.now().isoformat()
                
                # Guardar el item
                self._save_item(collection, item)
                
            except Exception as e:
                logger.error(f"Error storing item {item.get('id', 'unknown')}: {str(e)}")

    def _determine_collection(self, item: Dict) -> Optional[str]:
        """Determina la colección apropiada para un item basado en su tipo"""
        item_type = item.get('type', '').lower()
        
        if 'museum' in item_type or 'museo' in item_type:
            return 'museums'
        elif 'excursion' in item_type or 'tour' in item_type:
            return 'excursions'
        elif 'destination' in item_type or 'place' in item_type:
            return 'destinations'
            
        # Análisis de texto alternativo
        text = f"{item.get('name', '')} {item.get('description', '')}"
        text = text.lower()
        
        if any(word in text for word in ['museum', 'museo', 'galería', 'exhibition']):
            return 'museums'
        elif any(word in text for word in ['excursion', 'tour', 'trip', 'viaje']):
            return 'excursions'
            
        return 'destinations'  # colección por defecto

    def add_texts(self, collection_name: str, items: List[Dict]) -> None:
        """Añade textos a una colección específica en el vector store"""
        if not items:
            return
        
        # Crear directorio de la colección si no existe
        collection_dir = os.path.join(self.persist_dir, collection_name)
        os.makedirs(collection_dir, exist_ok=True)
        
        # Generar embeddings para todos los textos
        texts = [item['text'] for item in items]
        embeddings = self.model.encode(texts, convert_to_tensor=True)
        
        # Guardar cada item con su embedding
        for idx, item in enumerate(items):
            item_id = item['id']

            item_id = re.sub(r'[\\/:"*?<>|]', '', item_id) # Elimina caracteres no válidos
            item_id = item_id.replace('"', '')

            vector_file = os.path.join(collection_dir, f"{item_id}.pkl")
            
            vector_data = {
                'id': item_id,
                'embedding': embeddings[idx].cpu().numpy(),
                'metadata': item['metadata']
            }
            
            # Guardar en disco
            with open(vector_file, 'wb') as f:
                pickle.dump(vector_data, f)
        
        # Actualizar set de colecciones
        self.collections.add(collection_name)
        
        # Actualizar el índice de la colección
        self._update_collection_index(collection_name)

    def _update_collection_index(self, collection_name: str) -> None:
        """Actualiza el índice de una colección específica"""
        collection_dir = os.path.join(self.persist_dir, collection_name)
        index_file = os.path.join(collection_dir, 'index.json')
        
        # Recopilar metadatos de todos los archivos .pkl
        index_data = {}
        for file in os.listdir(collection_dir):
            if file.endswith('.pkl'):
                file_path = os.path.join(collection_dir, file)
                try:
                    with open(file_path, 'rb') as f:
                        data = pickle.load(f)
                        item_id = data['id']
                        metadata = data['metadata']
                        index_data[item_id] = {
                            'name': metadata.get('name', ''),
                            'type': metadata.get('type', ''),
                            'location': metadata.get('location', ''),
                            'file': file
                        }
                except Exception as e:
                    logger.error(f"Error loading {file}: {str(e)}")
                    continue
        
        # Guardar índice
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
