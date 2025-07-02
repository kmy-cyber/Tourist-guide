"""
Agente especializado en la planificación de itinerarios turísticos bajo el modelo BDI.
"""
import json
import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .base_agent import BaseAgent
from .interfaces import IPlannerAgent, AgentType, AgentContext
from ..models import UserContext
from ..planner.planner import (
    TourismActivity, UserPreferences, GeneticAlgorithmPlanner, Itinerary,
    create_tourism_planner, Location, ActivityType
)

logger = logging.getLogger(__name__)

class PlannerAgent(BaseAgent, IPlannerAgent):
    """
    Agente BDI que planifica itinerarios.
    - Creencia: La consulta actual, el contexto del usuario, el conocimiento disponible.
    - Deseo: Generar un itinerario si la consulta lo requiere.
    - Intención: Extraer preferencias, obtener actividades y optimizar el plan.
    """
    def __init__(self):
        super().__init__(AgentType.PLANNER)
        self.coordinator = None

    def set_coordinator(self, coordinator):
        self.coordinator = coordinator

    # --- Ciclo BDI ---

    def update_beliefs(self, context: AgentContext):
        """Percibe el contexto para la planificación."""
        super().update_beliefs(context)
        self.beliefs['user_context_dict'] = context.metadata.get('user_context')
        self.beliefs['knowledge'] = context.knowledge
        self.beliefs['is_planning_query'] = self._is_planning_query(context.query)

    def generate_desires(self):
        """Desea planificar si la consulta lo indica y hay información suficiente."""
        self.desires = []
        if self.beliefs.get('is_planning_query') and self.beliefs.get('knowledge'):
            self.desires.append('generate_itinerary')

    def generate_intentions(self):
        """Se compromete a la acción de generar el itinerario."""
        self.intentions = []
        if 'generate_itinerary' in self.desires:
            self.intentions.append(self.intend_to_generate_itinerary)

    # --- Intención ---

    async def intend_to_generate_itinerary(self, context: AgentContext) -> AgentContext:
        """
        Intención: Ejecuta todo el proceso de planificación, desde la extracción
        de preferencias hasta la generación y formateo del itinerario.
        """
        self.logger.info("Executing intention: Generate Itinerary.")
        try:
            user_context_dict = self.beliefs.get('user_context_dict')
            if not user_context_dict:
                self.logger.warning("Cannot plan, user context not found in beliefs.")
                return context

            user_context = UserContext.from_dict(user_context_dict)
            
            # 1. Extraer y combinar preferencias
            query_prefs = await self._extract_preferences_from_query(context.query)
            user_prefs = user_context.profile.preferences
            combined_prefs = {**user_prefs, **query_prefs} # Query prefs override user prefs
            
            # 2. Obtener actividades disponibles del conocimiento
            available_activities = self._get_available_activities()
            if not available_activities:
                self.logger.warning("No available activities from knowledge to plan itinerary.")
                return context

            # 3. Crear preferencias para el planificador
            duration = combined_prefs.get('duration_days', 3)
            planner_prefs = UserPreferences(
                start_date=datetime.now(),
                end_date=datetime.now() + timedelta(days=duration),
                max_budget=float(combined_prefs.get('budget', 500)),
                interest_categories=combined_prefs.get('interests', []),
            )

            # 4. Ejecutar el planificador
            planner = create_tourism_planner(available_activities, planner_prefs)
            itinerary = planner.optimize()

            # 5. Actualizar contexto compartido
            if itinerary:
                context.itinerary = self._format_itinerary(itinerary)
                self.update_context_confidence(context, planner.best_score)
                self.logger.info("Itinerary generated successfully.")
            else:
                self.logger.warning("Failed to generate a valid itinerary.")
        
        except Exception as e:
            self.set_error(context, f"Error during itinerary generation: {str(e)}")
            self.logger.error(f"Error in planning intention: {str(e)}", exc_info=True)
        
        return context

    # --- Métodos de Soporte (la mayoría sin cambios) ---

    def _is_planning_query(self, query: str) -> bool:
        # (La implementación no cambia)
        planning_keywords = ["itinerario", "planifica", "ruta", "viaje", "días", "plan"]
        return any(keyword in query.lower() for keyword in planning_keywords)

    async def _extract_preferences_from_query(self, query: str) -> Dict[str, Any]:
        # (La implementación no cambia, pero ahora usa el coordinador para el LLM)
        if not self.coordinator: return {}
        llm_agent = self.coordinator.get_agent(AgentType.LLM)
        if not llm_agent: return {}
        
        system_prompt = """Extract duration_days, budget, and a list of interests from the user query. Respond ONLY with a JSON object. Example: {"duration_days": 5, "budget": 1000, "interests": ["history", "beach"]}"""
        response_text = await llm_agent.generate_response(system_prompt, query)
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {}

    def _get_available_activities(self) -> List[TourismActivity]:
        """Obtiene actividades de sus creencias (que vienen del KnowledgeAgent)."""
        knowledge_items = self.beliefs.get('knowledge', [])
        activities = []
        for item in knowledge_items:
            try:
                data = item.get('data', {})
                name = data.get('name')
                if not name: continue
                
                loc_data = data.get('location', {})
                location = Location(name=loc_data.get('name', name), latitude=loc_data.get('coordinates', {}).get('lat', 0), longitude=loc_data.get('coordinates', {}).get('lon', 0)) if loc_data else None

                activities.append(TourismActivity(
                    id=data.get('id', name),
                    name=name,
                    description=data.get('description', ''),
                    location=location,
                    activity_type=self._determine_activity_type(data),
                    cost=float(data.get('price', 20)),
                    rating=float(data.get('rating', 4.0)),
                    duration_minutes=120
                ))
            except Exception as e:
                self.logger.warning(f"Could not convert knowledge item to activity: {e}")
        return activities

    def _determine_activity_type(self, item_data: Dict) -> ActivityType:
        # (La implementación no cambia)
        item_type_str = item_data.get('type', 'destination').lower()
        mapping = {
            'museum': ActivityType.MUSEUM, 'museo': ActivityType.MUSEUM,
            'tour': ActivityType.TOUR, 'excursion': ActivityType.EXCURSION,
            'restaurant': ActivityType.RESTAURANT,
            'nature': ActivityType.NATURE, 'playa': ActivityType.NATURE,
            'entertainment': ActivityType.ENTERTAINMENT,
            'shopping': ActivityType.SHOPPING,
            'hotel': ActivityType.ACCOMMODATION,
        }
        return mapping.get(item_type_str, ActivityType.CULTURAL)

    def _format_itinerary(self, itinerary: Itinerary) -> Dict[str, Any]:
        # (La implementación no cambia)
        formatted = {"days": []}
        for day_num, day_schedule in enumerate(itinerary.days, 1):
            day_info = {"day": day_num, "activities": []}
            for item in day_schedule.items:
                activity = item.activity
                day_info["activities"].append({
                    "name": activity.name,
                    "type": activity.activity_type.value,
                    "duration_hours": round(activity.duration_minutes / 60, 1),
                    "cost": activity.cost,
                    "location": activity.location.name if activity.location else "N/A"
                })
            formatted["days"].append(day_info)
        return formatted
        
    async def generate_itinerary(self, context: AgentContext) -> Optional[Dict[str, Any]]:
        """Método de interfaz legado."""
        result_context = await self.run(context)
        return result_context.itinerary
