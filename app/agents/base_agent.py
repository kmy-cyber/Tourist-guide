"""
Clase base para todos los agentes del sistema bajo el modelo BDI.
Proporciona funcionalidad común y un ciclo de vida proactivo.
"""
import logging
from abc import abstractmethod
from typing import Optional, Dict, List, Any
from .interfaces import IAgent, AgentContext, AgentType
from .utils import AgentUtilsMixin

class BaseAgent(AgentUtilsMixin, IAgent):
    """
    Implementación base para todos los agentes con un ciclo de vida BDI.
    Cada agente tiene un estado interno (creencias) y decide proactivamente
    qué hacer (deseos) y cómo hacerlo (intenciones).
    """

    def __init__(self, agent_type: AgentType):
        """
        Inicializa un agente base con su estructura BDI.
        
        Args:
            agent_type: El tipo de agente (p. ej., KNOWLEDGE, LLM).
        """
        self._agent_type = agent_type
        self.logger = logging.getLogger(f"app.agents.{self.__class__.__name__}")
        
        # --- Componentes del Modelo BDI ---
        # Creencias (Beliefs): El conocimiento del agente sobre el mundo.
        self.beliefs: Dict[str, Any] = {"name": self.agent_type.name, "is_active": True}
        
        # Deseos (Desires): Los objetivos que el agente quiere alcanzar.
        self.desires: List[str] = []
        
        # Intenciones (Intentions): El plan de acción al que el agente se compromete.
        self.intentions: List[callable] = []
        
        self.logger.info(f"{self.__class__.__name__} (BDI) initialized")

    @property
    def agent_type(self) -> AgentType:
        """Retorna el tipo del agente."""
        return self._agent_type

    # --- Métodos del Ciclo BDI (a ser implementados por las subclases) ---

    @abstractmethod
    def update_beliefs(self, context: AgentContext):
        """
        El agente percibe el mundo (el contexto compartido) y actualiza sus creencias.
        Este es el paso de "percepción".
        """
        self.beliefs['current_query'] = context.query
        self.beliefs['shared_context'] = context

    @abstractmethod
    def generate_desires(self):
        """
        Basado en sus creencias actuales, el agente decide qué objetivos quiere lograr.
        Este es el paso de "deliberación".
        """
        pass

    @abstractmethod
    def generate_intentions(self):
        """
        El agente elige un plan de acción (una o más funciones) para cumplir sus deseos.
        Este es el paso de "planificación".
        """
        pass

    # --- Ejecución del Ciclo BDI ---

    async def execute_intentions(self, context: AgentContext) -> AgentContext:
        """
        El agente ejecuta su plan de acción (intenciones), modificando el contexto.
        """
        self.logger.debug(f"Executing {len(self.intentions)} intentions.")
        for intention in self.intentions:
            context = await intention(context)
        
        self.intentions = []  # Limpiar intenciones después de ejecutarlas
        return context

    async def run(self, context: AgentContext) -> AgentContext:
        """
        Ciclo de vida proactivo completo del agente (Percepción -> Deliberación -> Planificación -> Acción).
        Este método reemplaza al antiguo 'process'.
        """
        self.logger.debug(f"Running BDI cycle for {self.agent_type.name}")
        self.update_beliefs(context)
        self.generate_desires()
        self.generate_intentions()
        return await self.execute_intentions(context)

    # --- Métodos de Ciclo de Vida Estándar ---

    async def initialize(self) -> None:
        """Inicializa recursos del agente si es necesario."""
        pass

    async def cleanup(self) -> None:
        """Limpia recursos del agente si es necesario."""
        pass

    # El método process se mantiene por compatibilidad con la interfaz, pero delega al nuevo ciclo 'run'.
    async def process(self, context: AgentContext) -> AgentContext:
        """Método de procesamiento legado, ahora redirige al ciclo BDI."""
        return await self.run(context)
