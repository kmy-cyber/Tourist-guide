"""
Interfaces para la arquitectura multiagente del sistema turístico.
Define los contratos que deben cumplir los diferentes agentes.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Protocol
from dataclasses import dataclass, field
from enum import Enum, auto

class AgentType(Enum):
    """Tipos de agentes disponibles en el sistema"""
    COORDINATOR = auto()
    KNOWLEDGE = auto()
    WEATHER = auto()
    LOCATION = auto()
    LLM = auto()
    UI = auto()
    PLANNER = auto()
    USER = auto()
        
@dataclass
class AgentContext:
    """
    Contexto compartido entre agentes (el "mundo" o "pizarra").
    Contiene toda la información necesaria para procesar una consulta.
    Los agentes leen y escriben en este objeto para colaborar.
    """
    query: str
    user_id: str = "default_user"
    confidence: float = 0.5
    sources: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Datos específicos que los agentes producen
    knowledge: List[Dict[str, Any]] = field(default_factory=list)
    locations: List[Dict[str, Any]] = field(default_factory=list)
    weather_info: Dict[str, Any] = field(default_factory=dict)
    itinerary: Optional[Dict[str, Any]] = None
    
    # Salida final
    response: Optional[str] = None
    ui_elements: Dict[str, Any] = field(default_factory=dict)
    
    # Estado y errores
    error: Optional[str] = None
    knowledge_gap_detected: bool = False # Para que el KnowledgeAgent sepa si debe buscar fuera

class IAgent(Protocol):
    """
    Protocolo base para todos los agentes.
    Define el contrato mínimo que debe cumplir cualquier agente.
    """
    @property
    def agent_type(self) -> AgentType:
        """Tipo del agente"""
        ...

    async def run(self, context: AgentContext) -> AgentContext:
        """
        Ejecuta el ciclo de vida proactivo del agente (BDI).
        Este es el nuevo método principal de ejecución.
        """
        ...

    async def process(self, context: AgentContext) -> AgentContext:
        """
        Procesa el contexto y retorna un contexto actualizado.
        Puede delegar en `run` para mantener la compatibilidad.
        """
        ...

    async def initialize(self) -> None:
        """Inicializa recursos del agente si es necesario"""
        ...

    async def cleanup(self) -> None:
        """Limpia recursos del agente si es necesario"""
        ...

# El resto de las interfaces (ICoordinatorAgent, IKnowledgeAgent, etc.) no necesitan
# cambios ya que heredan de IAgent y sus métodos específicos no se ven afectados
# por el cambio de arquitectura interna del agente.

class ICoordinatorAgent(IAgent):
    """Protocolo para el agente coordinador (ahora EnvironmentManager)"""
    def register_agent(self, agent: IAgent) -> None: ...
    async def get_response(self, query: str) -> AgentContext: ...

class IKnowledgeAgent(IAgent):
    """Protocolo para agentes que manejan conocimiento"""
    async def search_knowledge(self, query: str, limit: int = 3) -> List[Dict[str, Any]]: ...
    async def refresh_knowledge(self) -> None: ...

class IWeatherAgent(IAgent):
    """Protocolo para agentes que manejan información del clima"""
    async def get_weather(self, location: str) -> Optional[Dict[str, Any]]: ...

class ILocationAgent(IAgent):
    """Protocolo para agentes que manejan ubicaciones"""
    async def extract_locations(self, text: str) -> List[Dict[str, Any]]: ...
    async def get_coordinates(self, location: str) -> Optional[Dict[str, float]]: ...

class ILLMAgent(IAgent):
    """Protocolo para agentes que manejan modelos de lenguaje"""
    async def generate_response(self, system_prompt: str, user_prompt: str, context: Dict[str, Any] = None) -> str: ...

class IUIAgent(IAgent):
    """Protocolo para agentes que manejan la interfaz de usuario"""
    async def show_map(self, locations: List[Dict[str, Any]]) -> None: ...
    async def show_weather(self, weather_info: Dict[str, Any]) -> None: ...

class IUserAgent(IAgent):
    """Protocolo para agentes que manejan usuarios"""
    async def get_user_context(self, user_id: str) -> Any: ...
    async def save_interaction(self, user_id: str, query: str, response: str) -> None: ...

class IPlannerAgent(IAgent):
    """Protocolo para agentes de planificación"""
    async def generate_itinerary(self, context: AgentContext) -> Optional[Dict[str, Any]]: ...
