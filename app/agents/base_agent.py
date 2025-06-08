"""
Implementación base para agentes del sistema.
"""
from typing import Dict, Type, Optional
import logging
from .interfaces import IAgent, AgentContext

logger = logging.getLogger(__name__)

class BaseAgent(IAgent):
    """Clase base para todos los agentes del sistema"""
    
    def __init__(self):
        """Inicializa el agente base"""
        self.logger = logger.getChild(self.__class__.__name__)
        self._setup_logging()
    
    def _setup_logging(self):
        """Configura el logging para el agente"""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    @property
    def agent_type(self) -> str:
        """Retorna el tipo de agente"""
        return self.__class__.__name__
    
    async def process(self, context: AgentContext) -> AgentContext:
        """
        Procesa el contexto. Las subclases deben implementar este método.
        """
        try:
            return await self._process_impl(context)
        except Exception as e:
            self.logger.error(
                f"Error processing in {self.agent_type}: {str(e)}", 
                exc_info=True
            )
            context.confidence = 0.1
            return context
    
    async def _process_impl(self, context: AgentContext) -> AgentContext:
        """
        Implementación específica del procesamiento.
        Las subclases deben sobrescribir este método.
        """
        raise NotImplementedError(
            f"Agent {self.agent_type} must implement _process_impl"
        )
