"""
Agente coordinador que orquesta la interacción entre agentes especializados.
"""
from typing import Dict, List
from .base_agent import BaseAgent
from .interfaces import (
    IAgent, ICoordinatorAgent, AgentContext,
    IKnowledgeAgent, IWeatherAgent, ILocationAgent, ILLMAgent
)
from .knowledge_agent import KnowledgeAgent
from .weather_agent import WeatherAgent
from .location_agent import LocationAgent
from .llm_agent import LLMAgent
from ..models import UserQuery, TourGuideResponse

class CoordinatorAgent(BaseAgent, ICoordinatorAgent):
    """Agente coordinador del sistema"""
    
    def __init__(self, data_dir: str):
        """
        Inicializa el agente coordinador.
        
        Args:
            data_dir: Directorio base para los datos
        """
        super().__init__()
        self.agents: Dict[str, IAgent] = {}
        self._setup_agents(data_dir)
    
    def _setup_agents(self, data_dir: str):
        """
        Configura los agentes especializados.
        """
        # Crear y registrar agentes
        self.register_agent(KnowledgeAgent(data_dir))
        self.register_agent(WeatherAgent())
        self.register_agent(LocationAgent())
        self.register_agent(LLMAgent())
    
    def register_agent(self, agent: IAgent) -> None:
        """
        Registra un nuevo agente en el sistema.
        """
        self.agents[agent.agent_type] = agent
        self.logger.info(f"Registered agent: {agent.agent_type}")
    
    def _get_agent_by_type(self, agent_type: type) -> IAgent:
        """
        Obtiene un agente por su tipo de interfaz.
        """
        for agent in self.agents.values():
            if isinstance(agent, agent_type):
                return agent
        raise ValueError(f"No agent found for type: {agent_type.__name__}")
    
    async def coordinate(self, query: UserQuery) -> TourGuideResponse:
        """
        Coordina el procesamiento de una consulta del usuario.
        
        Args:
            query: La consulta del usuario
            
        Returns:
            TourGuideResponse con la respuesta procesada
        """
        try:
            # Crear contexto inicial
            context = AgentContext(query=query.text)
            
            # 1. Búsqueda de conocimiento
            knowledge_agent = self._get_agent_by_type(IKnowledgeAgent)
            context = await knowledge_agent.process(context)
            
            # 2. Información del clima
            weather_agent = self._get_agent_by_type(IWeatherAgent)
            context = await weather_agent.process(context)
            
            # 3. Generación de respuesta
            llm_agent = self._get_agent_by_type(ILLMAgent)
            context = await llm_agent.process(context)
            
            # 4. Procesamiento de ubicaciones
            location_agent = self._get_agent_by_type(ILocationAgent)
            context = await location_agent.process(context)
            
            # Construir respuesta final
            response_text = context.metadata.get('llm_response', '')
            
            # Agregar mapa si hay ubicaciones
            map_obj = context.metadata.get('locations_map')
            if map_obj:
                response_text = response_text.rstrip() + "\n\n"
            
            return TourGuideResponse(
                answer=response_text,
                sources=list(set(context.sources)),
                confidence=context.confidence,
                map_data=map_obj if map_obj else None
            )
            
        except Exception as e:
            self.logger.error(f"Error coordinating response: {str(e)}", exc_info=True)
            return TourGuideResponse(
                answer="Lo siento, ocurrió un error procesando tu consulta. Por favor, inténtalo de nuevo.",
                sources=[],
                confidence=0.1
            )
    
    async def _process_impl(self, context: AgentContext) -> AgentContext:
        """
        Implementación del proceso para mantener compatibilidad con IAgent.
        En este caso, simplemente pasa el contexto a través de todos los agentes.
        """
        for agent in self.agents.values():
            context = await agent.process(context)
        return context
