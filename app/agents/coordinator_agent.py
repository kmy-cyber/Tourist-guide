"""
Agente coordinador que orquesta la interacción entre agentes especializados.
"""
from typing import Dict, List, Optional, Type
from .base_agent import BaseAgent
from .interfaces import (
    IAgent, ICoordinatorAgent, AgentContext, AgentType,
    IKnowledgeAgent, IWeatherAgent, ILocationAgent, ILLMAgent, IUIAgent
)

class CoordinatorAgent(BaseAgent, ICoordinatorAgent):
    """
    Agente coordinador del sistema.
    Orquesta la interacción entre los diferentes agentes especializados.
    """
    
    def __init__(self, data_dir: str):
        """
        Inicializa el agente coordinador.
        
        Args:
            data_dir: Directorio base para los datos
        """
        super().__init__(AgentType.COORDINATOR)
        self.data_dir = data_dir
        self.agents: Dict[AgentType, IAgent] = {}
        
    def register_agent(self, agent: IAgent) -> None:
        """
        Registra un nuevo agente en el sistema.
        
        Args:
            agent: Agente a registrar
        """
        self.agents[agent.agent_type] = agent
        self.logger.info(f"Registered agent: {agent.agent_type.name}")
        
    def get_agent(self, agent_type: AgentType) -> Optional[IAgent]:
        """
        Obtiene un agente por su tipo.
        
        Args:
            agent_type: Tipo de agente a buscar
            
        Returns:
            El agente si existe, None en caso contrario
        """
        return self.agents.get(agent_type)
        
    async def initialize(self) -> None:
        """Inicializa todos los agentes registrados"""
        for agent in self.agents.values():
            await agent.initialize()
            
    async def cleanup(self) -> None:
        """Limpia recursos de todos los agentes"""
        for agent in self.agents.values():
            await agent.cleanup()

    async def process(self, context: AgentContext) -> AgentContext:
        """
        Procesa una consulta coordinando múltiples agentes.
        
        Args:
            context: Contexto con la consulta
            
        Returns:
            Contexto actualizado con la respuesta
        """

        try:              
            # 1. Procesar con agente de conocimiento
            if knowledge_agent := self.get_agent(AgentType.KNOWLEDGE):
                context = await knowledge_agent.process(context)
                
            # 2. Generar respuesta con LLM usando el conocimiento
            if llm_agent := self.get_agent(AgentType.LLM):
                context = await llm_agent.process(context)
                
            # 3. Extraer ubicaciones de la respuesta generada
            if location_agent := self.get_agent(AgentType.LOCATION):
                context = await location_agent.process(context)
                
            # 4. Obtener información del clima para las ubicaciones encontradas
            if context.locations and (weather_agent := self.get_agent(AgentType.WEATHER)):
                context = await weather_agent.process(context)
                
            # 5. Actualizar UI
            if ui_agent := self.get_agent(AgentType.UI):
                context = await ui_agent.process(context)
                
            return context
            
        except Exception as e:
            error_msg = f"Error processing query: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.set_error(context, error_msg)
            return context
            
    async def get_response(self, query: str) -> AgentContext:
        """
        Procesa una consulta y retorna el contexto con la respuesta.
        
        Args:
            query: Consulta del usuario
            
        Returns:
            Contexto con la respuesta y toda la información recopilada
        """
        context = AgentContext(query=query)
        return await self.process(context)
