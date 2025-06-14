"""
Agente coordinador que orquesta la interacción entre agentes especializados.
"""
from typing import Any, Dict, List, Optional, Type
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
        
        # Si es un agente de ubicación, establecer referencia al coordinador
        if hasattr(agent, 'set_coordinator'):
            agent.set_coordinator(self)
            
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
        initialization_order = [
            AgentType.KNOWLEDGE,
            AgentType.LLM, 
            AgentType.LOCATION,  # Location agent debe inicializarse antes de ser usado
            AgentType.WEATHER,
            AgentType.UI,
            AgentType.COORDINATOR
        ]
        
        # Inicializar en orden específico
        for agent_type in initialization_order:
            if agent := self.agents.get(agent_type):
                try:
                    await agent.initialize()
                    self.logger.info(f"Initialized agent: {agent_type.name}")
                except Exception as e:
                    self.logger.error(f"Failed to initialize agent {agent_type.name}: {str(e)}")
        
        # Inicializar cualquier agente restante
        for agent_type, agent in self.agents.items():
            if agent_type not in initialization_order:
                try:
                    await agent.initialize()
                    self.logger.info(f"Initialized remaining agent: {agent_type.name}")
                except Exception as e:
                    self.logger.error(f"Failed to initialize remaining agent {agent_type.name}: {str(e)}")
            
    async def cleanup(self) -> None:
        """Limpia recursos de todos los agentes"""
        for agent_type, agent in self.agents.items():
            try:
                await agent.cleanup()
                self.logger.info(f"Cleaned up agent: {agent_type.name}")
            except Exception as e:
                self.logger.error(f"Failed to cleanup agent {agent_type.name}: {str(e)}")

    async def process(self, context: AgentContext) -> AgentContext:
        """
        Procesa una consulta coordinando múltiples agentes en el orden optimizado.
        
        Flujo de procesamiento:
        1. Buscar conocimiento relevante
        2. Generar respuesta con LLM usando el conocimiento encontrado
        3. Extraer ubicaciones de la respuesta generada por el LLM
        4. Obtener información del clima para las ubicaciones encontradas
        5. Actualizar la interfaz de usuario
        
        Args:
            context: Contexto con la consulta
            
        Returns:
            Contexto actualizado con la respuesta y toda la información
        """
        try:
            self.logger.info(f"Processing query: {context.query[:100]}...")
            
            # 1. CONOCIMIENTO: Buscar información relevante en la base de conocimiento
            if knowledge_agent := self.get_agent(AgentType.KNOWLEDGE):
                self.logger.info("Processing with Knowledge Agent...")
                context = await knowledge_agent.process(context)
                if context.error:
                    self.logger.warning(f"Knowledge agent error: {context.error}")
                else:
                    knowledge_count = len(context.metadata.get("knowledge", []))
                    self.logger.info(f"Knowledge agent found {knowledge_count} relevant items")
            else:
                self.logger.warning("Knowledge agent not available")
                
            # 2. LLM: Generar respuesta usando el conocimiento recopilado
            if llm_agent := self.get_agent(AgentType.LLM):
                self.logger.info("Generating response with LLM Agent...")
                context = await llm_agent.process(context)
                if context.error:
                    self.logger.error(f"LLM agent error: {context.error}")
                    return context
                else:
                    response_length = len(context.response) if context.response else 0
                    self.logger.info(f"LLM generated response ({response_length} chars)")
            else:
                self.logger.error("LLM agent not available - cannot generate response")
                self.set_error(context, "LLM agent not available")
                return context
                
            # 3. UBICACIONES: Extraer ubicaciones de la respuesta generada por LLM
            if context.response and (location_agent := self.get_agent(AgentType.LOCATION)):
                self.logger.info("Extracting locations from LLM response...")
                context = await location_agent.process(context)
                if context.error:
                    self.logger.warning(f"Location agent error: {context.error}")
                    # No retornamos aquí porque el error de ubicaciones no es crítico
                    context.error = None  # Limpiamos el error para continuar
                else:
                    location_count = len(context.locations)
                    self.logger.info(f"Location agent found {location_count} locations")
            else:
                if not context.response:
                    self.logger.warning("No response available for location extraction")
                else:
                    self.logger.warning("Location agent not available")
                
            # 4. CLIMA: Obtener información del clima para ubicaciones encontradas
            if context.locations and (weather_agent := self.get_agent(AgentType.WEATHER)):
                self.logger.info("Getting weather information for locations...")
                context = await weather_agent.process(context)
                if context.error:
                    self.logger.warning(f"Weather agent error: {context.error}")
                    context.error = None  # Limpiamos el error para continuar
                else:
                    weather_count = len(context.weather_info)
                    self.logger.info(f"Weather agent found info for {weather_count} locations")
            else:
                if not context.locations:
                    self.logger.info("No locations found for weather lookup")
                else:
                    self.logger.warning("Weather agent not available")
                
            # 5. UI: Actualizar interfaz de usuario con toda la información
            if ui_agent := self.get_agent(AgentType.UI):
                self.logger.info("Updating UI with processed information...")
                context = await ui_agent.process(context)
                if context.error:
                    self.logger.warning(f"UI agent error: {context.error}")
                    context.error = None  # Error de UI no es crítico
            else:
                self.logger.warning("UI agent not available")
                
            # Registro final del estado del contexto
            self.logger.info(f"Processing completed - Confidence: {context.confidence:.2f}")
            self.logger.info(f"Final state: Response={bool(context.response)}, "
                           f"Locations={len(context.locations)}, "
                           f"Weather={len(context.weather_info)}, "
                           f"Sources={len(context.sources)}")
            
            return context
            
        except Exception as e:
            error_msg = f"Critical error in coordinator: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.set_error(context, error_msg)
            return context
            
    async def get_response(self, query: str) -> AgentContext:
        """
        Procesa una consulta completa y retorna el contexto con la respuesta.
        
        Args:
            query: Consulta del usuario
            
        Returns:
            Contexto con la respuesta y toda la información recopilada
        """
        if not query or not query.strip():
            context = AgentContext(query=query or "")
            self.set_error(context, "Empty query provided")
            return context
            
        context = AgentContext(query=query.strip())
        self.logger.info(f"Starting new query processing: {query[:50]}...")
        
        try:
            processed_context = await self.process(context)
            
            # Validación final
            if not processed_context.response and not processed_context.error:
                self.set_error(processed_context, "No response generated and no error set")
                
            return processed_context
            
        except Exception as e:
            error_msg = f"Unexpected error in get_response: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.set_error(context, error_msg)
            return context
    
    def get_agent_status(self) -> Dict[str, bool]:
        """
        Obtiene el estado de disponibilidad de todos los agentes.
        
        Returns:
            Diccionario con el estado de cada tipo de agente
        """
        return {
            agent_type.name: agent_type in self.agents 
            for agent_type in AgentType
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Realiza una verificación de salud de todos los agentes.
        
        Returns:
            Diccionario con información de salud del sistema
        """
        health_info = {
            "coordinator": True,
            "agents": {}
        }
        
        for agent_type, agent in self.agents.items():
            try:
                # Verificación básica - el agente responde
                if hasattr(agent, 'agent_type'):
                    health_info["agents"][agent_type.name] = True
                else:
                    health_info["agents"][agent_type.name] = False
            except Exception as e:
                health_info["agents"][agent_type.name] = False
                self.logger.error(f"Health check failed for {agent_type.name}: {str(e)}")
        
        return health_info