"""
Agente especializado en generación de lenguaje natural.
"""
from typing import Optional
from .base_agent import BaseAgent
from .interfaces import ILLMAgent, AgentContext
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMAgent(BaseAgent, ILLMAgent):
    """Agente que maneja la generación de lenguaje natural"""
    
    def __init__(self):
        """Inicializa el agente LLM"""
        super().__init__()
        self.client = AsyncOpenAI(
            api_key=os.getenv("FIREWORKS_API_KEY"),
            base_url="https://api.fireworks.ai/inference/v1"
        )
        self.model = "accounts/fireworks/models/llama-v3p1-8b-instruct"
        
        self._system_template = """
        Eres un guía turístico experto en Cuba, especializado en proporcionar información precisa y útil 
        sobre destinos, atracciones y actividades turísticas. Debes:
        
        1. Usar la información proporcionada como fuente principal
        2. Si hay datos del clima, integrarlos en tus recomendaciones
        3. Mantener un tono profesional pero amigable
        4. Proporcionar respuestas estructuradas y fáciles de leer
        5. Si no tienes información suficiente, indicarlo claramente
        """
    
    async def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        """
        Genera una respuesta usando el modelo de lenguaje.
        """
        messages = [
            {
                "role": "system", 
                "content": f"{self._system_template}\n\n{system_prompt}"
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ]

        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1000,
                temperature=0.7,
                stop=None
            )

            if not completion.choices:
                raise Exception("No response generated")

            return completion.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"Error in LLM generation: {str(e)}")
            raise
    
    def _build_prompt(self, context: AgentContext) -> tuple[str, str]:
        """
        Construye los prompts del sistema y usuario.
        """
        # Obtener información del conocimiento
        knowledge_results = context.metadata.get('knowledge_results', [])
        knowledge_context = []
        
        for result in knowledge_results:
            data = result.get('data', {})
            source_info = data.get('source_info', {})
            location = data.get('location', {})
            
            knowledge_context.append(f"""
Información sobre {data.get('name', 'lugar de interés')} ({data.get('type', 'atracción')}):
Ubicación: {location.get('address', 'No especificada')}
Descripción: {data.get('description', 'No disponible')}
Fuente: {source_info.get('type', 'No especificada')} (Confiabilidad: {source_info.get('reliability', 'unknown')})
---""")
        
        knowledge_text = "\n".join(knowledge_context) if knowledge_context else \
            "No se encontró información específica sobre tu consulta. Proporcionaré una respuesta general."
        
        # Añadir información del clima si está disponible
        weather_info = context.metadata.get('weather_info', '')
        
        system_prompt = f"""Eres un guía turístico experto en Cuba. 
Usa la siguiente información verificada como referencia:

{knowledge_text}

{weather_info if weather_info else ''}

Si hay información del clima disponible, inclúyela en tus recomendaciones y sugerencias."""
        
        return system_prompt, context.query
    
    async def _process_impl(self, context: AgentContext) -> AgentContext:
        """
        Procesa el contexto generando una respuesta natural.
        """
        system_prompt, user_prompt = self._build_prompt(context)
        
        try:
            response = await self.generate_response(system_prompt, user_prompt)
            context.metadata['llm_response'] = response
        except Exception as e:
            self.logger.error(f"Error generating response: {str(e)}")
            context.metadata['llm_response'] = """Lo siento, estoy teniendo problemas para generar una respuesta.
Por favor, intenta tu consulta de nuevo."""
            context.confidence = 0.1
        
        return context
