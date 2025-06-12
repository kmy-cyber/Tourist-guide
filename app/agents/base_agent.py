"""
Clase base para todos los agentes del sistema.
Proporciona funcionalidad común y utilidades.
"""
import logging
from typing import Optional
from .interfaces import IAgent, AgentContext, AgentType
from .utils import AgentUtilsMixin

class BaseAgent(AgentUtilsMixin, IAgent):
    """Implementación base para todos los agentes"""

    def __init__(self, agent_type: AgentType):
        """
        Inicializa un agente base.
        
        Args:
            agent_type: Tipo del agente
        """
        self._agent_type = agent_type
        self.logger = logging.getLogger(f"app.agents.{self.__class__.__name__}")
        self.logger.info(f"{self.__class__.__name__} initialized")

    @property
    def agent_type(self) -> AgentType:
        """Retorna el tipo del agente"""
        return self._agent_type

    async def process(self, context: AgentContext) -> AgentContext:
        """Procesa el contexto. Debe ser implementado por las clases derivadas."""
        raise NotImplementedError("Subclasses must implement process()")

    async def initialize(self) -> None:
        """Inicializa recursos del agente"""
        pass

    async def cleanup(self) -> None:
        """Limpia recursos del agente"""
        pass
