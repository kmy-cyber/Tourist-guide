from typing import List
from .models import UserQuery, TourGuideResponse
from .llm import LLM
from .knowledge_base import TourismKB

class TourGuideAgent:
    def __init__(self, data_dir: str):
        self.llm = LLM()
        self.kb = TourismKB(data_dir)

    async def process_query(self, query: UserQuery) -> TourGuideResponse:
        # Buscar información relevante en la base de conocimientos
        relevant_info = self.kb.search(query.text)
        
        # Construir contexto para el LLM
        context = "\n".join([
            f"Información sobre {info['id']}:\n{info['data'].get('description', '')}"
            for info in relevant_info
        ])
        
        # Generar respuesta usando el LLM
        answer = await self.llm.generate(
            prompt=query.text,
            context=f"Usa esta información como referencia:\n{context}"
        )
        
        return TourGuideResponse(
            answer=answer,
            sources=[info['id'] for info in relevant_info],
            confidence=0.8 if relevant_info else 0.5
        )
