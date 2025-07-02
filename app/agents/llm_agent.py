"""
Agente especializado en interacción con modelos de lenguaje bajo el modelo BDI.
"""
from typing import Dict, Any, Optional

from .base_agent import BaseAgent
from .interfaces import ILLMAgent, AgentContext, AgentType
from ..llm import LLM

class LLMAgent(BaseAgent, ILLMAgent):
    """
    Agente BDI que maneja la generación de respuestas con LLM.
    - Creencia: El conocimiento, itinerario y perfil de usuario disponibles.
    - Deseo: Generar una respuesta textual si hay contexto suficiente.
    - Intención: Construir un prompt y generar la respuesta.
    """
    
    def __init__(self):
        super().__init__(AgentType.LLM)
        self.llm = LLM()
        
    # --- Ciclo BDI ---

    def update_beliefs(self, context: AgentContext):
        """Percibe el contexto para la generación de respuesta."""
        super().update_beliefs(context)
        self.beliefs['knowledge'] = context.knowledge
        self.beliefs['itinerary'] = context.itinerary
        self.beliefs['user_context'] = context.metadata.get('user_context')

    def generate_desires(self):
        """Desea generar una respuesta si hay algo sobre lo que hablar."""
        self.desires = []
        # Solo genera una respuesta si hay conocimiento o un itinerario.
        if self.beliefs.get('knowledge') or self.beliefs.get('itinerary'):
            self.desires.append('generate_text_response')

    def generate_intentions(self):
        """Se compromete a la acción de generar la respuesta."""
        self.intentions = []
        if 'generate_text_response' in self.desires:
            self.intentions.append(self.intend_to_generate_response)

    # --- Intención ---

    async def intend_to_generate_response(self, context: AgentContext) -> AgentContext:
        """

        Intención: Construye un prompt detallado a partir de las creencias
        y utiliza el LLM para generar la respuesta final.
        """
        self.logger.info("Executing intention: Generate Text Response.")
        try:
            system_prompt = self._build_system_prompt()
            
            response = await self.llm.generate_response(
                system_prompt=system_prompt,
                user_prompt=context.query
            )
            
            context.response = response
            self.update_context_confidence(context, 0.85 if response else 0.3)
        except Exception as e:
            self.set_error(context, f"Error in LLM generation: {str(e)}")
        
        return context

    # --- Métodos de Soporte ---

    def _build_system_prompt(self) -> str:
        """Construye el prompt del sistema con toda la información de sus creencias."""
        prompt_parts = ["Eres un guía turístico experto y amigable para Cuba."]
        
        # Añadir contexto de usuario
        user_context = self.beliefs.get('user_context')
        if user_context and user_context.get('profile'):
            profile = user_context['profile']
            if profile.get('name'):
                prompt_parts.append(f"Estás hablando con {profile['name']}.")
            if user_context.get('interests'):
                prompt_parts.append(f"Sus intereses incluyen: {', '.join(user_context['interests'])}.")

        # Añadir conocimiento
        if self.beliefs.get('knowledge'):
            prompt_parts.append("\nUsa la siguiente información verificada para tu respuesta:")
            for item in self.beliefs['knowledge']:
                data = item.get('data', {})
                prompt_parts.append(f"- {data.get('name', 'Info')}: {data.get('description', 'N/A')}")
        
        # Añadir itinerario
        if self.beliefs.get('itinerary'):
            prompt_parts.append("\nTambién has creado el siguiente itinerario:")
            itinerary = self.beliefs['itinerary']
            for day in itinerary.get('days', []):
                activities = [act['name'] for act in day.get('activities', [])]
                prompt_parts.append(f"Día {day['day']}: {', '.join(activities)}")

        prompt_parts.append("\nINSTRUCCIONES: Responde a la consulta del usuario de forma natural, usando la información proporcionada. Sé conciso y amigable. Si no tienes información, dilo honestamente.")
        return "\n".join(prompt_parts)
        
    async def generate_response(self, system_prompt: str, user_prompt: str, context: Dict[str, Any] = None) -> str:
        """Método de interfaz legado."""
        return await self.llm.generate_response(system_prompt, user_prompt)
