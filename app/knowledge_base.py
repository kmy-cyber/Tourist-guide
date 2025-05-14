import json
import os
from typing import List

class TourismKB:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self._load_data()

    def _load_data(self):
        self.attractions = {}
        json_file = os.path.join(self.data_dir, "cuba_tourism_20250613.json")
        
        # Inicializar el diccionario
        if os.path.exists(json_file):
            with open(json_file, "r", encoding="utf-8") as f:
                json_data = json.load(f)
                if isinstance(json_data, dict):
                    self.attractions = json_data
                else:
                    # Si el JSON es una lista, convertirla a diccionario
                    self.attractions = {f"item_{i}": item for i, item in enumerate(json_data)}
        
        # Cargar descripciones detalladas
        for i in range(8):  # Asumiendo 8 archivos de atracciones
            attraction_id = f"attraction_{i}"
            file_path = os.path.join(self.data_dir, f"cuba_attraction_{i}.txt")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    if attraction_id not in self.attractions:
                        self.attractions[attraction_id] = {}

    def search(self, query: str) -> List[dict]:
        """
        Búsqueda simple por coincidencia de palabras clave
        """
        results = []
        query_terms = query.lower().split()
        
        for attraction_id, data in self.attractions.items():
            description = data.get("description", "").lower()
            if any(term in description for term in query_terms):
                results.append({
                    "id": attraction_id,
                    "data": data
                })
        
        return results[:3]  # Retorna los 3 mejores resultados
