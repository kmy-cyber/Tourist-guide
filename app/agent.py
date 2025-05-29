from typing import List
from .models import UserQuery, TourGuideResponse
from .llm import LLM
from .knowledge_base import TourismKB
import logging

logger = logging.getLogger(__name__)

class TourGuideAgent:
    def __init__(self, data_dir: str):
        self.llm = LLM()
        self.kb = TourismKB(data_dir)

    def _build_context(self, info_list: List[dict]) -> str:
        """Construir contexto estructurado para el LLM"""
        if not info_list:
            return "No se encontró información específica sobre tu consulta. Proporcionaré una respuesta general."
            
        context_parts = []
        for info in info_list:
            if not isinstance(info, dict):
                continue
                
            data = info.get('data', {})
            if not isinstance(data, dict):
                continue
                
            source_info = data.get('source_info', {}) or {}
            reliability = source_info.get('reliability', 'unknown')
            location = data.get('location', {}) or {}
            
            context_parts.append(f"""
Información sobre {data.get('name', 'lugar de interés')} ({data.get('type', 'atracción')}):
Ubicación: {location.get('address', 'No especificada')}
Descripción: {data.get('description', 'No disponible')}
Fuente: {source_info.get('type', 'No especificada')} (Confiabilidad: {reliability})
---""")
            
        return "\n".join(context_parts)

    def _calculate_confidence(self, info_list: List[dict]) -> float:
        """Calcular nivel de confianza basado en las fuentes y la cantidad de información"""
        if not info_list:
            return 0.5
            
        # Factores de confianza
        reliability_scores = {
            'high': 1.0,
            'medium': 0.8,
            'low': 0.6,
            'unknown': 0.5
        }
        
        # Calcular score promedio de confiabilidad
        total_score = 0
        valid_items = 0
        
        for info in info_list:
            if not isinstance(info, dict):
                continue
                
            data = info.get('data', {})
            if not isinstance(data, dict):
                continue
                
            source_info = data.get('source_info', {}) or {}
            reliability = source_info.get('reliability', 'unknown')
            total_score += reliability_scores.get(reliability, 0.5)
            valid_items += 1
            
        if valid_items == 0:
            return 0.5
            
        base_confidence = total_score / valid_items
        
        # Ajustar por cantidad de resultados
        results_factor = min(valid_items / 3, 1.0)  # Normalizar a máximo 1.0
        
        return base_confidence * results_factor

    async def process_query(self, query: UserQuery) -> TourGuideResponse:
        try:
            # Buscar información relevante
            relevant_info = self.kb.search(query.text)
            
            # Construir contexto estructurado
            context = self._build_context(relevant_info)
            
            # Calcular confianza
            confidence = self._calculate_confidence(relevant_info)
            
            # Generar respuesta
            system_prompt = f"""Eres un guía turístico experto en Cuba, especializado en museos y excursiones.
Usa la siguiente información verificada como referencia para tu respuesta:

{context}

Proporciona respuestas detalladas y precisas, mencionando la fuente de la información cuando sea relevante.
Si la información proporcionada no es suficiente, indica qué detalles podrían faltar."""

            answer = await self.llm.generate(
                prompt=query.text,
                context=system_prompt
            )
            
            return TourGuideResponse(
                answer=answer,
                sources=[info['id'] for info in relevant_info],
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return TourGuideResponse(
                answer="Lo siento, hubo un error al procesar tu consulta. Por favor, intenta de nuevo.",
                sources=[],
                confidence=0.0
            )
