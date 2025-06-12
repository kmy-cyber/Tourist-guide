"""
Agente especializado en interacción con modelos de lenguaje.
"""
from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from .interfaces import ILLMAgent, AgentContext, AgentType
from ..llm import LLM

class LLMAgent(BaseAgent, ILLMAgent):
    """Agente que maneja la generación de respuestas con LLM"""
    
    def __init__(self):
        """Inicializa el agente LLM"""
        super().__init__(AgentType.LLM)
        self.llm = LLM()
        
    async def process(self, context: AgentContext) -> AgentContext:
        """
        Procesa el contexto para generar una respuesta.
        
        Args:
            context: Contexto actual
            
        Returns:
            Contexto actualizado con la respuesta generada
        """
        try:
            # Construir prompt del sistema
            system_prompt = self.build_system_prompt(context)
            
            # Generar respuesta
            response = await self.generate_response(
                system_prompt=system_prompt,
                user_prompt=context.query,
                context=context.metadata
            )
            
            context.response = response
            self.update_context_confidence(context, 0.8 if response else 0.3)
            return context
            
        except Exception as e:
            self.set_error(context, f"Error generating response: {str(e)}")
            return context
            
    def build_system_prompt(self, context: AgentContext) -> str:
        """
        Construye el prompt del sistema con toda la información disponible.
        
        Args:
            context: Contexto actual
            
        Returns:
            Prompt del sistema formateado
        """
        prompt_parts = [
            "Eres un guía turístico experto en Cuba.",
            "Usa la siguiente información verificada como referencia:"
        ]
        
        # Añadir información de conocimiento
        if knowledge := context.metadata.get("knowledge"):
            prompt_parts.append("\nInformación disponible:")
            for info in knowledge:
                if isinstance(info, dict):
                    data = info.get("data", {})
                    prompt_parts.append(f"""
- {data.get('name', 'Lugar')} ({data.get('type', 'atracción')}):
  {data.get('description', 'No hay descripción disponible')}
""")
        
        # Añadir información del clima
        if context.weather_info:
            prompt_parts.append("\nInformación del clima:")
            for city, weather in context.weather_info.items():
                prompt_parts.append(f"\n- {city}: {weather.get('report', '')}")
        
        # Añadir instrucciones específicas
        prompt_parts.extend([
            "\nInstrucciones:",
            "1. Proporciona información precisa y relevante",
            "2. Incluye el clima en tus recomendaciones si está disponible",
            "3. Menciona lugares específicos cuando sea posible",
            "4. Mantén un tono amigable y profesional"
        ])
        
        return "\n".join(prompt_parts)
        
    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Genera una respuesta usando el modelo de lenguaje.
        
        Args:
            system_prompt: Prompt del sistema
            user_prompt: Prompt del usuario
            context: Contexto adicional
            
        Returns:
            Respuesta generada
        """
        return await self.llm.generate_response(system_prompt, user_prompt)
