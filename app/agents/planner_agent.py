"""
Agente especializado en la planificación de itinerarios turísticos.
Archivo completo corregido con todos los métodos necesarios.
"""

import json
import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
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
from .interfaces import AgentType, AgentContext, IPlannerAgent, ILLMAgent

logger = logging.getLogger(__name__)

class PlannerAgent(BaseAgent, IPlannerAgent):
    def __init__(self):
        super().__init__(AgentType.PLANNER)
        self.planner: Optional[GeneticAlgorithmPlanner] = None
        self.coordinator = None
        
    def set_coordinator(self, coordinator):
        """Establece la referencia al coordinador"""
        self.coordinator = coordinator
        self.logger.info("Coordinator reference set in PlannerAgent")
        
    async def process(self, context: AgentContext) -> AgentContext:
        """Procesa el contexto para determinar si generar itinerario"""
        try:
            # Detectar si la consulta requiere planificación
            if self._is_planning_query(context.query):
                self.logger.info("Consulta de planificación detectada")
                
                # Obtener el contexto del usuario
                user_context = context.metadata.get('user_context')
                if not user_context:
                    self.logger.warning("No se encontró contexto de usuario para planificación")
                    return context

                # Convertir contexto de diccionario a UserContext si es necesario
                if isinstance(user_context, dict):
                    user_context = UserContext.from_dict(user_context)

                # Extraer preferencias del usuario y la consulta
                preferences = await self._extract_preferences_from_query(context)
                
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

                # Verificar si tenemos suficiente información
                if not self._has_sufficient_info(context):
                    self._apply_defaults(context)

                # Corregir el valor de duration_days para que no sea None
                duration_days = preferences.get('duration_days')
                if duration_days is None:
                    duration_days = 3 # Asignar un valor por defecto

                # Crear UserPreferences para el planificador
                planner_preferences = UserPreferences(
                    start_date=datetime.now(),
                    end_date=datetime.now() + timedelta(days=preferences.get('duration_days') or 3),
                    max_budget=float(preferences.get('budget') or 300),
                    interest_categories=preferences.get('interests', []),
                    max_walking_distance=float(preferences.get('max_walking_distance') or 5.0)
                )
                
                # Buscar actividades disponibles usando el agente de conocimiento
                available_activities = await self._get_available_activities(context)
                
                if available_activities:
                    self.logger.info(f"Se encontraron {len(available_activities)} actividades disponibles")
                    # Crear y optimizar el itinerario
                    planner = create_tourism_planner(available_activities, planner_preferences)
                    itinerary = planner.optimize()
                    
                    # Actualizar el contexto con el itinerario generado
                    if itinerary:
                        context.itinerary = self._format_itinerary(itinerary)
                        self.update_context_confidence(context, planner.best_score)
                        self.logger.info("Itinerario generado exitosamente")
                    else:
                        self.logger.warning("No se pudo generar un itinerario válido")
                else:
                    self.logger.warning("No se encontraron actividades disponibles para planificación")
                    
            return context
            
        except Exception as e:
            self.set_error(context, f"Error en planificación: {str(e)}")
            self.logger.error(f"Error en planificación: {str(e)}", exc_info=True)
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
            r"\d+\s*horas?", r"mañana", "tarde", "noche"
        ]
        
        query_lower = query.lower()
        
        # Verificar palabras clave de planificación
        has_planning_keywords = any(keyword in query_lower for keyword in planning_keywords)
        
        # Verificar indicadores de tiempo
        has_time_indicators = any(re.search(pattern, query_lower) for pattern in time_indicators)
        
        return has_planning_keywords or has_time_indicators

    async def _extract_preferences_from_query(self, context: AgentContext) -> Dict[str, Any]:
        """
        Extrae preferencias del usuario desde la consulta usando LLM para mejor precisión.
        Esta versión es más robusta para parsear y sanear la respuesta del LLM.
        """
        if not hasattr(self, 'coordinator'):
            self.logger.warning("No coordinator available for LLM extraction, falling back to patterns.")
            return self._extract_preferences_with_patterns(context.query)
            
        llm_agent = self.coordinator.get_agent(AgentType.LLM)
        if not llm_agent:
            self.logger.warning("No LLM agent available, falling back to pattern matching.")
            return self._extract_preferences_with_patterns(context.query)

        try:
            system_prompt = """Eres un asistente especializado en planificación turística.
            Analiza la consulta del usuario y extrae las siguientes preferencias:
            - duration_days: número de días del viaje (requerido)
            - budget: presupuesto numérico (sin símbolos monetarios)
            - travel_type: tipo de viaje (familia, pareja, solo, grupo)
            - interests: lista de intereses (cultura, naturaleza, gastronomía, etc.)
            
            Responde ÚNICAMENTE con un objeto JSON. No añadas texto explicativo.
            Ejemplo: {"duration_days": 3, "interests": ["playa", "naturaleza"]}
            """
            
            llm_response_text = await llm_agent.generate_response(
                system_prompt=system_prompt,
                user_prompt=context.query
            )
            
            json_match = re.search(r'\{.*\}', llm_response_text, re.DOTALL)
            
            if json_match:
                json_string = json_match.group(0)
                
                # Sanear la cadena de JSON para eliminar escapes inválidos como \_
                sanitized_json_string = json_string.replace('\\_', '_')

                try:
                    # Usar la cadena saneada para el parseo
                    preferences = json.loads(sanitized_json_string)
                    self.logger.info(f"Preferencias extraídas y saneadas con LLM: {preferences}")
                    return preferences
                except json.JSONDecodeError as e:
                    self.logger.error(f"Fallo al parsear JSON saneado: {e}. String: {sanitized_json_string}")
                    return self._extract_preferences_with_patterns(context.query)
            else:
                self.logger.warning(f"No se encontró un bloque JSON en la respuesta del LLM. Usando patrones. Respuesta: {llm_response_text}")
                return self._extract_preferences_with_patterns(context.query)
                
        except Exception as e:
            self.logger.error(f"Error crítico usando LLM para extracción de preferencias: {str(e)}")
            return self._extract_preferences_with_patterns(context.query)      
    def _extract_preferences_with_patterns(self, query: str) -> Dict[str, Any]:
        """
        Método de respaldo que usa patrones regex para extraer preferencias.
        
        Args:
            query: Consulta del usuario
            
        Returns:
            Diccionario con las preferencias extraídas
        """
        query = query.lower()
        preferences = {}
        
        # Extraer duración (días)
        duration_patterns = [
            r"(\d+)\s*día[s]?",
            r"(\d+)\s*day[s]?",
            r"durante\s*(\d+)",
            r"por\s*(\d+)\s*días?"
        ]
        
        for pattern in duration_patterns:
            match = re.search(pattern, query)
            if match:
                preferences["duration_days"] = int(match.group(1))
                break
        
        # Extraer presupuesto
        budget_patterns = [
            r"presupuesto.*?(\d+).*?(?:pesos|cup|usd|\$|dolares|dólares)",
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
        
        # Extraer tipo de viaje
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
        
        # Extraer intereses específicos
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
        # Solo verificar si hay actividades disponibles
        has_activities = bool(context.metadata.get("knowledge"))
        return has_activities
    
    def _apply_defaults(self, context: AgentContext) -> None:
        """Aplica valores por defecto para información faltante"""
        prefs = context.user_preferences
        
        # Duración por defecto: 3 días
        if "duration_days" not in prefs:
            prefs["duration_days"] = 3
            
        # Presupuesto por defecto: $300 USD
        if "budget" not in prefs:
            prefs["budget"] = 300
            
        # Intereses por defecto: cultura y naturaleza
        if "interests" not in prefs:
            prefs["interests"] = ["cultura", "naturaleza"]

    async def _get_available_activities(self, context: AgentContext) -> List[TourismActivity]:
        """
        Obtiene actividades disponibles del agente de conocimiento.
        
        Args:
            context: Contexto con la información de la consulta
            
        Returns:
            Lista de actividades turísticas disponibles
        """
        try:
            # Obtener conocimiento relevante del contexto
            knowledge_items = context.metadata.get("knowledge", [])
            
            if not knowledge_items:
                self.logger.warning("No hay conocimiento disponible para generar actividades")
                return []
                
            activities = []
            
            # Convertir cada item de conocimiento en una actividad turística
            for item in knowledge_items:
                try:
                    logger.info(f"item: {item}")
                    
                    # Extraer información relevante
                    name = item.get("name", "")
                    description = item.get("description", "")
                    location_data = item.get("location", {})
                    rating = float(item.get("rating", 4.0))  # Rating por defecto 4.0
                    
                    if not name:  # Skip items sin nombre
                        continue
                    
                    # Crear objeto Location si hay datos de ubicación
                    location = None
                    if location_data and location_data.get("name"):
                        location = Location(
                            name=location_data.get("name", ""),
                            latitude=float(location_data.get("latitude", 0.0)),
                            longitude=float(location_data.get("longitude", 0.0))
                        )
                    
                    # Determinar tipo de actividad basado en categorías o tags
                    activity_type = self._determine_activity_type(item)
                    
                    # Estimar duración y costo basado en tipo de actividad
                    duration = self._estimate_duration(activity_type)
                    cost = self._estimate_cost(activity_type)
                    
                    activity_id = f"{item.get('id', '')}_{name.lower().replace(' ', '_')}_{activity_type.value.lower()}"

                    # Crear actividad turística
                    activity = TourismActivity(
                        id=activity_id,
                        name=name,
                        description=description,
                        location=location,
                        activity_type=activity_type,
                        cost=cost,
                        rating=rating,
                        duration_minutes=duration * 60  # Convertir horas a minutos
                    )
                    
                    activities.append(activity)
                    
                except Exception as e:
                    self.logger.warning(f"Error procesando item de conocimiento: {str(e)}")
                    continue
                    
            self.logger.info(f"Se generaron {len(activities)} actividades desde el conocimiento")
            return activities
            
        except Exception as e:
            self.logger.error(f"Error obteniendo actividades disponibles: {str(e)}")
            return []

    def _determine_activity_type(self, item: Dict[str, Any]) -> ActivityType:
        """
        Determina el tipo de actividad basado en categorías, tags o contenido.
        
        Args:
            item: Diccionario con información del item de conocimiento
            
        Returns:
            Tipo de actividad identificado
        """
        # Obtener información para clasificar
        title = item.get("name", "").lower()
        content = item.get("description", "").lower()
        tags = [tag.lower() for tag in item.get("tags", [])]
        category = item.get("type", "").lower()
        
        # Combinar toda la información textual
        text_to_analyze = f"{title} {content} {' '.join(tags)} {category}"
        
        # Palabras clave para cada tipo de actividad
        type_keywords = {
            ActivityType.MUSEUM: [
                "museo", "museum", "galería", "gallery", "arte", "art", 
                "exposición", "exhibition", "colección", "collection",
                "historia", "history", "cultura", "cultural"
            ],
            ActivityType.TOUR: [
                "tour", "excursión", "recorrido", "visita", "guiada",
                "walking", "city tour", "sightseeing", "paseo"
            ],
            ActivityType.NATURE: [
                "naturaleza", "nature", "parque", "park", "playa", "beach",
                "montaña", "mountain", "reserva", "reserve", "jardín", "garden",
                "bosque", "forest", "río", "river", "mar", "sea"
            ],
            ActivityType.RESTAURANT: [
                "restaurante", "restaurant", "comida", "food", "bar",
                "café", "coffee", "cocina", "cuisine", "gastronomía",
                "dining", "eat", "meal"
            ],
            ActivityType.ENTERTAINMENT: [
                "teatro", "theater", "cine", "cinema", "concierto", "concert",
                "show", "espectáculo", "música", "music", "baile", "dance",
                "festival", "evento", "event", "fiesta", "party"
            ],
            ActivityType.SHOPPING: [
                "tienda", "shop", "shopping", "mercado", "market",
                "centro comercial", "mall", "boutique", "souvenir",
                "artesanía", "craft", "compras"
            ],
            ActivityType.ACCOMMODATION: [
                "hotel", "hostal", "casa", "house", "apartamento",
                "apartment", "alojamiento", "accommodation", "resort",
                "villa", "habitación", "room"
            ]
        }
        
        # Contar coincidencias para cada tipo
        type_scores = {}
        for activity_type, keywords in type_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_to_analyze)
            if score > 0:
                type_scores[activity_type] = score
        
        # Retornar el tipo con mayor puntuación, o MUSEUM por defecto
        if type_scores:
            return max(type_scores.items(), key=lambda x: x[1])[0]
        else:
            return ActivityType.MUSEUM  # Tipo por defecto

    def _estimate_duration(self, activity_type: ActivityType) -> float:
        """
        Estima la duración en horas para un tipo de actividad.
        
        Args:
            activity_type: Tipo de actividad
            
        Returns:
            Duración estimada en horas
        """
        duration_map = {
            ActivityType.MUSEUM: 2.0,
            ActivityType.TOUR: 3.0,
            ActivityType.NATURE: 4.0,
            ActivityType.RESTAURANT: 1.5,
            ActivityType.ENTERTAINMENT: 2.5,
            ActivityType.SHOPPING: 2.0,
            ActivityType.ACCOMMODATION: 0.5  # Solo para check-in/out
        }
        
        return duration_map.get(activity_type, 2.0)

    def _estimate_cost(self, activity_type: ActivityType) -> float:
        """
        Estima el costo en USD para un tipo de actividad.
        
        Args:
            activity_type: Tipo de actividad
            
        Returns:
            Costo estimado en USD
        """
        cost_map = {
            ActivityType.MUSEUM: 5.0,
            ActivityType.TOUR: 25.0,
            ActivityType.NATURE: 10.0,
            ActivityType.RESTAURANT: 15.0,
            ActivityType.ENTERTAINMENT: 20.0,
            ActivityType.SHOPPING: 30.0,
            ActivityType.ACCOMMODATION: 50.0
        }
        
        return cost_map.get(activity_type, 10.0)

    def _format_itinerary(self, itinerary: Itinerary) -> Dict[str, Any]:
        """
        Formatea el itinerario para incluir en el contexto.
        
        Args:
            itinerary: Objeto itinerario del planificador
            
        Returns:
            Diccionario con el itinerario formateado
        """
        try:
            formatted = {
                "days": [],
                "total_cost": 0.0,
                "total_duration": 0.0,
                "summary": {
                    "total_activities": 0,
                    "daily_breakdown": {}
                }
            }
            
            total_cost = 0.0
            total_duration = 0.0
            total_activities = 0
            
            for day_num, day_schedule in enumerate(itinerary.days, 1):
                day_info = {
                    "day": day_num,
                    "activities": [],
                    "daily_cost": 0.0,
                    "daily_duration": 0.0
                }
                
                daily_cost = 0.0
                daily_duration = 0.0
                
                for item in day_schedule.items:
                    activity = item.activity
                    
                    if not isinstance(activity, TourismActivity):
                        self.logger.warning(f"Actividad no válida en el día {day_num}: {activity}")
                        continue

                    activity_info = {
                        "name": activity.name,
                        "description": activity.description[:200] + "..." if len(activity.description) > 200 else activity.description,
                        "duration_hours": activity.duration_minutes / 60.0,  # Convertir minutos a horas
                        "cost": activity.cost,
                        "rating": activity.rating,
                        "type": activity.activity_type.value if hasattr(activity.activity_type, 'value') else str(activity.activity_type),
                        "location": {
                            "name": activity.location.name if activity.location else "No especificada",
                            "coordinates": [activity.location.latitude, activity.location.longitude] if activity.location else None
                        }
                    }
                    
                    day_info["activities"].append(activity_info)
                    daily_cost += activity.cost
                    daily_duration += activity.duration_minutes / 60.0
                    total_activities += 1
                
                day_info["daily_cost"] = round(daily_cost, 2)
                day_info["daily_duration"] = round(daily_duration, 2)
                
                formatted["days"].append(day_info)
                total_cost += daily_cost
                total_duration += daily_duration
                
                formatted["summary"]["daily_breakdown"][f"day_{day_num}"] = {
                    "activities": len(day_schedule.items),
                    "cost": round(daily_cost, 2),
                    "duration": round(daily_duration, 2)
                }
            
            formatted["total_cost"] = round(total_cost, 2)
            formatted["total_duration"] = round(total_duration, 2)
            formatted["summary"]["total_activities"] = total_activities
            
            return formatted
            
        except Exception as e:
            self.logger.error(f"Error formateando itinerario: {str(e)}")
            return {
                "days": [],
                "total_cost": 0.0,
                "total_duration": 0.0,
                "error": f"Error formateando itinerario: {str(e)}"
            }

    def _append_itinerary_to_response(self, context: AgentContext) -> str:
        """
        Genera texto del itinerario para añadir a la respuesta.
        
        Args:
            context: Contexto con el itinerario generado
            
        Returns:
            Texto formateado del itinerario
        """
        if not context.itinerary:
            return ""
            
        try:
            itinerary = context.itinerary
            original_response = context.response
            
            # Construir texto del itinerario
            itinerary_text = "\n\n## 📅 Itinerario Sugerido\n\n"
            
            # Resumen general
            summary = itinerary.get("summary", {})
            total_cost = itinerary.get("total_cost", 0)
            total_activities = summary.get("total_activities", 0)
            
            itinerary_text += f"**Resumen:** {total_activities} actividades, costo total estimado: ${total_cost:.2f} USD\n\n"
            
            # Detalles por día
            for day_info in itinerary.get("days", []):
                day_num = day_info.get("day", 1)
                daily_cost = day_info.get("daily_cost", 0)
                daily_duration = day_info.get("daily_duration", 0)
                
                itinerary_text += f"### Día {day_num}\n"
                itinerary_text += f"*Costo: ${daily_cost:.2f} USD | Duración: {daily_duration:.1f} horas*\n\n"
                
                for i, activity in enumerate(day_info.get("activities", []), 1):
                    name = activity.get("name", "Actividad sin nombre")
                    duration = activity.get("duration_hours", 0)
                    cost = activity.get("cost", 0)
                    location_name = activity.get("location", {}).get("name", "Ubicación no especificada")
                    
                    itinerary_text += f"{i}. **{name}**\n"
                    itinerary_text += f"   - 📍 {location_name}\n"
                    itinerary_text += f"   - ⏱️ {duration:.1f}h | 💰 ${cost:.2f}\n\n"
                
                itinerary_text += "---\n\n"
            
            return (original_response or "") + itinerary_text
            
        except Exception as e:
            self.logger.error(f"Error generando texto del itinerario: {str(e)}")
            return context.response or ""