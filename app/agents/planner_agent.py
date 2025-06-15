"""
Agente especializado en la planificación de itinerarios turísticos.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import re
from ..models import UserContext
from ..planner.planner import (
    TourismActivity, 
    UserPreferences, 
    GeneticAlgorithmPlanner,
    Itinerary,
    create_tourism_planner,
    Location,
    ActivityType
)
from .base_agent import BaseAgent
from .interfaces import AgentType, AgentContext, IPlannerAgent

logger = logging.getLogger(__name__)

class PlannerAgent(BaseAgent, IPlannerAgent):
    def __init__(self):
        super().__init__(AgentType.PLANNER)
        self.planner: Optional[GeneticAlgorithmPlanner] = None
        
    async def process(self, context: AgentContext) -> AgentContext:
        """Procesa el contexto para determinar si generar itinerario"""
        try:
            # Detectar si la consulta requiere planificación
            if self._is_planning_query(context.query):
                # Obtener el contexto del usuario
                user_context = context.metadata.get('user_context')
                if not user_context:
                    self.logger.warning("No se encontró contexto de usuario para planificación")
                    return context

                # Convertir contexto de diccionario a UserContext si es necesario
                if isinstance(user_context, dict):
                    user_context = UserContext.from_dict(user_context)

                # Extraer preferencias del usuario y la consulta
                preferences = self._extract_preferences_from_query(context)
                
                # Combinar con las preferencias existentes del usuario
                user_preferences = user_context.profile.preferences
                preferences.update(user_preferences)
                
                # Añadir intereses del usuario
                if user_context.interests:
                    if 'interests' not in preferences:
                        preferences['interests'] = []
                    preferences['interests'].extend(user_context.interests)
                
                # Añadir ubicaciones mencionadas anteriormente
                if user_context.mentioned_locations:
                    if 'preferred_locations' not in preferences:
                        preferences['preferred_locations'] = []
                    preferences['preferred_locations'].extend(user_context.mentioned_locations)

                # Crear UserPreferences para el planificador
                planner_preferences = UserPreferences(
                    start_date=datetime.now(),
                    end_date=datetime.now() + timedelta(days=preferences.get('duration_days', 3)),
                    max_budget=float(preferences.get('budget', 300)),
                    interest_categories=preferences.get('interests', []),
                    max_walking_distance=float(preferences.get('max_walking_distance', 5.0))
                )
                
                # Buscar actividades disponibles usando el agente de conocimiento
                available_activities = await self._get_available_activities(context)
                
                if available_activities:
                    # Crear y optimizar el itinerario
                    planner = create_tourism_planner(available_activities, planner_preferences)
                    itinerary = planner.optimize()
                    
                    # Actualizar el contexto con el itinerario generado
                    if itinerary:
                        context.itinerary = self._format_itinerary(itinerary)
                        self.update_context_confidence(context, planner.best_score)
                    
            return context
            
        except Exception as e:
            self.set_error(context, f"Error en planificación: {str(e)}")
            return context
    
    def _is_planning_query(self, query: str) -> bool:
        """Detecta si la consulta requiere planificación de itinerario"""
        planning_keywords = [
            "itinerario", "planifica", "ruta", "viaje", "días",
            "horario", "schedule", "plan", "trip", "tour",
            "recorrido", "agenda", "programa", "visitar"
        ]
        
        time_indicators = [
            r"\d+\s*día[s]?", r"\d+\s*semana[s]?",
            r"mañana", r"tarde", r"fin de semana",
            r"enero|febrero|marzo|abril|mayo|junio",
            r"julio|agosto|septiembre|octubre|noviembre|diciembre",
            r"hoy", r"pasado mañana", r"próximo"
        ]
        
        # Frases que indican planificación
        planning_phrases = [
            "qué hacer en", "cómo organizar", "dónde ir",
            "lugares para visitar", "actividades en",
            "que visitar", "donde viajar", "turismo en"
        ]
        
        query_lower = query.lower()
        
        # Verificar palabras clave de planificación
        has_planning_keywords = any(keyword in query_lower for keyword in planning_keywords)
        
        # Verificar indicadores temporales
        has_time_indicators = any(re.search(pattern, query_lower) for pattern in time_indicators)
        
        # Verificar frases de planificación
        has_planning_phrases = any(phrase in query_lower for phrase in planning_phrases)
        
        return has_planning_keywords or has_time_indicators or has_planning_phrases
    
    def _extract_preferences_from_query(self, context: AgentContext) -> Dict[str, Any]:
        """Extrae preferencias detalladas de la consulta"""
        query = context.query.lower()
        preferences = {}
        
        # Extraer ubicaciones específicas mencionadas
        locations = []
        cuba_cities = [
            "la habana", "habana", "santiago de cuba", "trinidad", 
            "varadero", "cienfuegos", "camagüey", "holguín", 
            "santa clara", "viñales", "bayamo", "matanzas"
        ]
        
        for city in cuba_cities:
            if city in query:
                locations.append(city.title())
        
        if locations:
            preferences["preferred_locations"] = locations
        
        # Extraer duración (opcional)
        duration_patterns = [
            (r"(\d+)\s*día[s]?", "days"),
            (r"(\d+)\s*semana[s]?", "weeks"),
            (r"fin de semana", "weekend"),
            (r"una semana", "week")
        ]
        
        for pattern, duration_type in duration_patterns:
            match = re.search(pattern, query)
            if match:
                if duration_type == "days":
                    preferences["duration_days"] = int(match.group(1))
                elif duration_type == "weeks" or duration_type == "week":
                    days = int(match.group(1)) * 7 if duration_type == "weeks" else 7
                    preferences["duration_days"] = days
                elif duration_type == "weekend":
                    preferences["duration_days"] = 2
                break
        
        # Extraer presupuesto (opcional)
        budget_patterns = [
            r"(\d+)\s*(?:pesos|cup|usd|\$|dolares|dólares)",
            r"presupuesto\s*(?:de\s*)?(\d+)",
            r"gastando?\s*(\d+)",
            r"con\s*(\d+)\s*(?:pesos|dolares|dólares|\$)"
        ]
        
        for pattern in budget_patterns:
            match = re.search(pattern, query)
            if match:
                preferences["budget"] = float(match.group(1))
                break
        
        # Extraer tipo de viaje (opcional)
        travel_types = {
            "familia": ["familia", "niños", "familiar", "familia con niños"],
            "pareja": ["pareja", "romántico", "dos personas", "luna de miel"],
            "solo": ["solo", "individual", "solitario", "viajo solo"],
            "grupo": ["grupo", "amigos", "varios", "grupo de amigos"]
        }
        
        for travel_type, keywords in travel_types.items():
            if any(keyword in query for keyword in keywords):
                preferences["travel_type"] = travel_type
                break
        
        # Extraer intereses específicos (opcional pero amplio)
        interests = []
        interest_mapping = {
            "cultura": ["museo", "historia", "arte", "cultura", "cultural", "histórico"],
            "naturaleza": ["playa", "naturaleza", "parque", "senderismo", "outdoor", "montaña"],
            "gastronomía": ["comida", "restaurante", "gastronomía", "comer", "local food", "cocina"],
            "vida_nocturna": ["noche", "bar", "discoteca", "fiesta", "nightlife", "salir"],
            "arquitectura": ["arquitectura", "edificio", "colonial", "construcción"],
            "música": ["música", "concierto", "baile", "salsa", "son", "rumba"],
            "compras": ["compras", "shopping", "mercado", "tienda", "souvenir"],
            "aventura": ["aventura", "deporte", "buceo", "escalada", "excursión"]
        }
        
        for category, keywords in interest_mapping.items():
            if any(keyword in query for keyword in keywords):
                interests.append(category)
        
        if interests:
            preferences["interests"] = interests
        
        return preferences
    
    def _has_sufficient_info(self, context: AgentContext) -> bool:
        """Verifica si hay suficiente información para generar itinerario"""
        prefs = context.user_preferences
        
        # Solo verificar si hay actividades disponibles
        # El sistema puede generar itinerarios con información mínima
        has_activities = bool(context.metadata.get("knowledge"))
        
        return has_activities
    
    def _apply_defaults(self, context: AgentContext) -> None:
        """Aplica valores por defecto para información faltante"""
        prefs = context.user_preferences
        
        # Duración por defecto: 3 días
        if "duration_days" not in prefs:
            prefs["duration_days"] = 3
            self.logger.info("Aplicando duración por defecto: 3 días")
        
        # Presupuesto por defecto: $300 (flexible)
        if "budget" not in prefs:
            prefs["budget"] = 300.0
            self.logger.info("Aplicando presupuesto por defecto: $300")
        
        # Tipo de viaje por defecto: general
        if "travel_type" not in prefs:
            prefs["travel_type"] = "general"
        
        # Intereses por defecto: variados
        if not prefs.get("interests"):
            prefs["interests"] = ["cultura", "naturaleza", "gastronomía"]
            self.logger.info("Aplicando intereses por defecto: cultura, naturaleza, gastronomía")
    
    def _request_additional_info(self, context: AgentContext) -> str:
        """Solicita información adicional para mejorar la planificación (opcional)"""
        prefs = context.user_preferences
        suggestions = []
        
        # Generar sugerencias basadas en lo que falta, pero sin requerir
        if "duration_days" not in prefs:
            suggestions.append("duración específica (ej: 3 días, una semana)")
        
        if "budget" not in prefs:
            suggestions.append("presupuesto aproximado (para mejores recomendaciones)")
        
        if not prefs.get("interests"):
            suggestions.append("tus intereses específicos (museos, playas, gastronomía, etc.)")
        
        base_response = context.response or "Te ayudo a planificar tu viaje a Cuba."
        
        if suggestions:
            return f"""{base_response}

        🎯 **Generando itinerario con configuración estándar...**
        
        💡 Para un itinerario más personalizado, puedes especificar:
        - {' • '.join(suggestions)}
        
        Por ejemplo: "Planifica 5 días en La Habana, me interesan museos y vida nocturna, presupuesto $400"
        """
        else:
            return f"{base_response}\n\n🎯 **Generando tu itinerario personalizado...**"
    
    def _format_itinerary_response(self, original_response: str, itinerary: Dict[str, Any]) -> str:
        """Formatea la respuesta para incluir el itinerario"""
        
        itinerary_text = "\n\n## 📅 Tu Itinerario Personalizado\n\n"
        
        for i, day in enumerate(itinerary["days"], 1):
            date = day["date"]
            total_cost = day["total_cost"]
            
            itinerary_text += f"### Día {i} - {date}\n"
            itinerary_text += f"**Costo del día: ${total_cost:.2f}**\n\n"
            
            for activity in day["activities"]:
                time = activity["time"]
                name = activity["name"]
                duration = activity["duration"]
                cost = activity["cost"]
                rating = activity["rating"]
                description = activity.get("description", "")
                
                stars = "⭐" * int(rating)
                
                itinerary_text += f"**{time}** - {name} {stars}\n"
                itinerary_text += f"• Duración: {duration}\n"
                itinerary_text += f"• Costo: ${cost:.2f}\n"
                if description:
                    itinerary_text += f"• {description[:100]}...\n"
                itinerary_text += "\n"
            
            # Añadir información del clima si está disponible
            weather = day.get("weather")
            if weather:
                itinerary_text += f"🌤️ **Clima esperado**: {weather}\n\n"
        
        # Resumen final
        total_cost = itinerary["total_cost"]
        avg_rating = itinerary["average_rating"]
        
        itinerary_text += f"""---
    **💰 Costo total estimado**: ${total_cost:.2f}
    **⭐ Rating promedio**: {avg_rating:.1f}/5.0

    *Este itinerario ha sido optimizado considerando tus preferencias, el clima y la eficiencia de tiempo.*
    """
        
        return (original_response or "") + itinerary_text
        """Formatea la respuesta para incluir el itinerario"""
        
        itinerary_text = "\n\n## 📅 Tu Itinerario Personalizado\n\n"
        
        for i, day in enumerate(itinerary["days"], 1):
            date = day["date"]
            total_cost = day["total_cost"]
            
            itinerary_text += f"### Día {i} - {date}\n"
            itinerary_text += f"**Costo del día: ${total_cost:.2f}**\n\n"
            
            for activity in day["activities"]:
                time = activity["time"]
                name = activity["name"]
                duration = activity["duration"]
                cost = activity["cost"]
                rating = activity["rating"]
                description = activity.get("description", "")
                
                stars = "⭐" * int(rating)
                
                itinerary_text += f"**{time}** - {name} {stars}\n"
                itinerary_text += f"• Duración: {duration}\n"
                itinerary_text += f"• Costo: ${cost:.2f}\n"
                if description:
                    itinerary_text += f"• {description[:100]}...\n"
                itinerary_text += "\n"
            
            # Añadir información del clima si está disponible
            weather = day.get("weather")
            if weather:
                itinerary_text += f"🌤️ **Clima esperado**: {weather}\n\n"
        
        # Resumen final
        total_cost = itinerary["total_cost"]
        avg_rating = itinerary["average_rating"]
        
        itinerary_text += f"""---
**💰 Costo total estimado**: ${total_cost:.2f}
**⭐ Rating promedio**: {avg_rating:.1f}/5.0

*Este itinerario ha sido optimizado considerando tus preferencias, el clima y la eficiencia de tiempo.*
"""
        
        return (original_response or "") + itinerary_text