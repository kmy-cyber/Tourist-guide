"""
Agente coordinador que orquesta la interacción entre agentes BDI.
Ahora actúa como un EnvironmentManager, gestionando el contexto compartido.
"""
from typing import Any, Dict, List, Optional
from .base_agent import BaseAgent
from .interfaces import IAgent, ICoordinatorAgent, AgentContext, AgentType

class CoordinatorAgent(BaseAgent, ICoordinatorAgent):
    """
    Agente coordinador del sistema BDI.
    Orquesta el ciclo de vida de los agentes especializados, permitiéndoles
    actuar sobre un contexto compartido (pizarra).
    """
    
    def __init__(self, data_dir: str):
        """
        Inicializa el coordinador.
        """
        super().__init__(AgentType.COORDINATOR)
        self.data_dir = data_dir
        self.agents: Dict[AgentType, IAgent] = {}
        # El orden de ejecución define la prioridad o los "turnos" de los agentes.
        self.agent_execution_order = [
            AgentType.USER,
            AgentType.KNOWLEDGE,
            AgentType.PLANNER,
            AgentType.LLM, # LLM se beneficia de la info de los agentes anteriores
            AgentType.LOCATION,
            AgentType.WEATHER,
            AgentType.UI,
        ]
        
    def register_agent(self, agent: IAgent) -> None:
        """Registra un nuevo agente en el sistema."""
        self.agents[agent.agent_type] = agent
        if hasattr(agent, 'set_coordinator'):
            agent.set_coordinator(self)
        self.logger.info(f"Registered agent: {agent.agent_type.name}")
        
    def get_agent(self, agent_type: AgentType) -> Optional[IAgent]:
        """Obtiene un agente por su tipo."""
        return self.agents.get(agent_type)
        
    async def initialize(self) -> None:
        """Inicializa todos los agentes registrados en orden."""
        for agent_type in self.agent_execution_order:
            if agent := self.agents.get(agent_type):
                try:
                    await agent.initialize()
                    self.logger.info(f"Initialized agent: {agent_type.name}")
                except Exception as e:
                    self.logger.error(f"Failed to initialize agent {agent_type.name}: {str(e)}")
            
    async def cleanup(self) -> None:
        """Limpia recursos de todos los agentes."""
        for agent in self.agents.values():
            await agent.cleanup()

    async def get_response(self, query: str, user_id: str = 'default_user') -> AgentContext:
        """
        Procesa una consulta completa orquestando los ciclos BDI de los agentes.
        
        Args:
            query: Consulta del usuario.
            user_id: Identificador del usuario.
            
        Returns:
            El contexto final después de que todos los agentes hayan actuado.
        """
        self.logger.info(f"--- Starting new BDI process for query: {query[:50]}... ---")
        
        # 1. Crear el contexto compartido inicial (el "mundo" o "pizarra")
        context = AgentContext(query=query.strip(), user_id=user_id)

        try:
            # 2. Ejecutar el ciclo BDI de cada agente en orden de prioridad.
            #    Cada agente lee y modifica el contexto compartido.
            for agent_type in self.agent_execution_order:
                if agent := self.get_agent(agent_type):
                    self.logger.debug(f"--- Running cycle for {agent.agent_type.name} ---")
                    context = await agent.run(context)
            
            # 3. Guardar la interacción final
            if user_agent := self.get_agent(AgentType.USER):
                if context.query and context.response:
                    await user_agent.save_interaction(user_id, context.query, context.response)
                    self.logger.info("Final interaction saved to user history.")

            self.logger.info(f"--- BDI process completed. Final confidence: {context.confidence:.2f} ---")
            return context
            
        except Exception as e:
            error_msg = f"Critical error in coordinator: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.set_error(context, error_msg)
            return context

    def get_agent_status(self) -> Dict[str, bool]:
        """
        Obtiene el estado de disponibilidad de todos los agentes registrados.
        Este método es útil para la UI y para depuración.
        
        Returns:
            Diccionario con el nombre del tipo de agente y su estado (True si está registrado).
        """
        return {
            agent_type.name: agent_type in self.agents 
            for agent_type in AgentType
        }

    # --- Implementación de los métodos abstractos de BaseAgent ---
    # El Coordinador es un agente especial. Su ciclo BDI principal es el método 
    # `get_response`, que orquesta a los demás. Por lo tanto, estos métodos 
    # abstractos heredados tienen una implementación mínima para permitir la instanciación.

    def update_beliefs(self, context: AgentContext):
        """El coordinador percibe el estado general del sistema."""
        self.beliefs['agent_count'] = len(self.agents)
        self.beliefs['last_query'] = context.query if context else None

    def generate_desires(self):
        """El deseo principal del coordinador es siempre orquestar el flujo."""
        self.desires = ['orchestrate_flow']

    def generate_intentions(self):
        """
        La intención real del coordinador está encapsulada en el método `get_response`.
        Este método del ciclo BDI puede permanecer vacío.
        """
        self.intentions = []
