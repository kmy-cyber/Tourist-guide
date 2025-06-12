"""
Interfaces para la arquitectura multiagente del sistema turístico.
Define los contratos que deben cumplir los diferentes agentes.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Protocol
from dataclasses import dataclass
from enum import Enum, auto

class AgentType(Enum):
    """Tipos de agentes disponibles en el sistema"""
    COORDINATOR = auto()
    KNOWLEDGE = auto()
    WEATHER = auto()
    LOCATION = auto()
    LLM = auto()
    UI = auto()

@dataclass
class AgentContext:
    """
    Contexto compartido entre agentes.
    Contiene toda la información necesaria para procesar una consulta.
    """
    query: str
    confidence: float = 0.5
    sources: List[str] = None
    metadata: Dict[str, Any] = None
    locations: List[Dict[str, Any]] = None
    weather_info: Dict[str, Any] = None
    response: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        self.sources = self.sources or []
        self.metadata = self.metadata or {}
        self.locations = self.locations or []
        self.weather_info = self.weather_info or {}

class IAgent(Protocol):
    """
    Protocolo base para todos los agentes.
    Define el contrato mínimo que debe cumplir cualquier agente.
    """
    @property
    def agent_type(self) -> AgentType:
        """Tipo del agente"""
        ...

    async def process(self, context: AgentContext) -> AgentContext:
        """Procesa el contexto y retorna un contexto actualizado"""
        ...

    async def initialize(self) -> None:
        """Inicializa recursos del agente si es necesario"""
        ...

    async def cleanup(self) -> None:
        """Limpia recursos del agente si es necesario"""
        ...

class ICoordinatorAgent(IAgent):
    """Protocolo para el agente coordinador"""
    
    def register_agent(self, agent: IAgent) -> None:
        """Registra un nuevo agente en el sistema"""
        ...

    async def get_response(self, query: str) -> AgentContext:
        """Procesa una consulta completa coordinando múltiples agentes"""
        ...

class IKnowledgeAgent(IAgent):
    """Protocolo para agentes que manejan conocimiento"""
    
    async def search_knowledge(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Busca información relevante en la base de conocimiento"""
        ...

    async def refresh_knowledge(self) -> None:
        """Actualiza la base de conocimiento"""
        ...

class IWeatherAgent(IAgent):
    """Protocolo para agentes que manejan información del clima"""
    
    async def get_weather(self, location: str) -> Optional[Dict[str, Any]]:
        """Obtiene información del clima para una ubicación"""
        ...

class ILocationAgent(IAgent):
    """Protocolo para agentes que manejan ubicaciones"""
    
    async def extract_locations(self, text: str) -> List[Dict[str, Any]]:
        """Extrae ubicaciones mencionadas en un texto"""
        ...

    async def get_coordinates(self, location: str) -> Optional[Dict[str, float]]:
        """Obtiene coordenadas para una ubicación"""
        ...

class ILLMAgent(IAgent):
    """Protocolo para agentes que manejan modelos de lenguaje"""
    
    async def generate_response(
        self, 
        system_prompt: str, 
        user_prompt: str,
        context: Dict[str, Any] = None
    ) -> str:
        """Genera una respuesta usando el modelo de lenguaje"""
        ...

class IUIAgent(IAgent):
    """Protocolo para agentes que manejan la interfaz de usuario"""
    
    async def update_ui(self, context: AgentContext) -> None:
        """Actualiza la interfaz de usuario con nueva información"""
        ...

    async def show_map(self, locations: List[Dict[str, Any]]) -> None:
        """Muestra un mapa con las ubicaciones especificadas"""
        ...

    async def show_weather(self, weather_info: Dict[str, Any]) -> None:
        """Muestra información del clima"""
        ...
