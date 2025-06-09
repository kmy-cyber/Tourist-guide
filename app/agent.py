from typing import List, Any
from .models import UserQuery, TourGuideResponse
from .llm import LLM
from .knowledge_base import TourismKB
from .weather.weather_service import WeatherService
from .expert_system import es_consulta_clima, extraer_ciudad, analizar_consulta, QUERY_TYPES
import logging
import asyncio

logger = logging.getLogger(__name__)

class TourGuideAgent:
    def __init__(self, data_dir: str):
        self.llm = LLM()
        self.kb = TourismKB(data_dir)
        self.weather_service = WeatherService()
        # Lista de ciudades conocidas
        self.ciudades_cuba = [
            "La Habana", "Santiago de Cuba", "Camagüey", "Holguín", "Santa Clara", 
            "Bayamo", "Cienfuegos", "Pinar del Río", "Matanzas", "Ciego de Ávila", 
            "Las Tunas", "Sancti Spíritus", "Guantánamo", "Artemisa", "Mayabeque"
        ]

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
            # Initialize variables
            weather_report = None
            weather_extra = ""
            
            # Analizar la consulta con el sistema experto
            info_consulta = analizar_consulta(query.text, self.ciudades_cuba)
            
            # Obtener la información relevante de forma asíncrona
            relevant_info = await self.kb.async_search(query.text)
            
            # Construir contexto estructurado
            context = self._build_context(relevant_info)
            
            # Calcular confianza
            confidence = self._calculate_confidence(relevant_info)
            
            # Obtener información del clima si es necesario
            ciudad = info_consulta.ciudad
            if ciudad:
                weather_report = self.weather_service.get_weather_report(ciudad)
                if weather_report:
                    weather_extra = f"\n\nInformación del clima en {ciudad}:\n{weather_report}"
                    # Aumentar confianza si tenemos datos del clima
                    confidence = max(confidence, 0.8)

            # Si es consulta específica de clima
            if info_consulta.tipo == QUERY_TYPES['CLIMA']:
                if not ciudad:
                    return TourGuideResponse(
                        answer="¿Sobre qué ciudad de Cuba deseas saber el clima? Por favor, especifica el nombre.",
                        sources=[],
                        confidence=0.9
                    )
                if not weather_report:
                    return TourGuideResponse(
                        answer=f"Lo siento, no pude obtener el clima para {ciudad} en este momento. Por favor, intenta más tarde.",
                        sources=[],
                        confidence=0.5
                    )
            
            # Generar respuesta considerando el tipo de consulta y el clima
            system_prompt = f"""Eres un guía turístico experto en Cuba, especializado en museos y excursiones.
Usa la siguiente información verificada como referencia para tu respuesta:

{context}{weather_extra}

Tipo de consulta: {info_consulta.tipo}
{"Categoría específica: " + info_consulta.categoria if info_consulta.categoria else ""}
{"Restricciones a considerar: " + ", ".join(info_consulta.restricciones) if info_consulta.restricciones else ""}
{"Fecha mencionada: " + info_consulta.fecha.strftime('%d/%m/%Y') if info_consulta.fecha else ""}

Instrucciones específicas:
1. Si la consulta es sobre el clima, proporciona recomendaciones de actividades basadas en las condiciones meteorológicas
2. Para consultas sobre lugares o actividades, considera el clima actual en tus recomendaciones
3. Si se menciona una fecha futura, contextualiza las sugerencias según la temporada
4. Menciona las fuentes de información cuando sea relevante

Si la información proporcionada no es suficiente, indica qué detalles podrían faltar."""

            answer = await self.llm.generate_response(
                system_prompt=system_prompt,
                user_prompt=query.text
            )
            
            sources = [info['id'] for info in relevant_info]
            if weather_report:
                sources.append(f"OpenWeather - {ciudad}")
            
            return TourGuideResponse(
                answer=answer,
                sources=sources,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return TourGuideResponse(
                answer="Lo siento, hubo un error al procesar tu consulta. Por favor, intenta de nuevo.",
                sources=[],
                confidence=0.0
            )
