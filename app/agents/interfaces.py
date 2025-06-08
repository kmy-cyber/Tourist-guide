"""
Interfaces para la arquitectura multiagente del sistema turístico.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from ..models import UserQuery, TourGuideResponse

@dataclass
class AgentContext:
    """Contexto compartido entre agentes"""
    query: str
    confidence: float = 0.5
    sources: List[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        self.sources = self.sources or []
        self.metadata = self.metadata or {}

class IAgent(ABC):
    """Interface base para todos los agentes"""
    
    @abstractmethod
    async def process(self, context: AgentContext) -> AgentContext:
        """Procesa el contexto y retorna un contexto actualizado"""
        pass

    @property
    @abstractmethod
    def agent_type(self) -> str:
        """Retorna el tipo de agente"""
        pass

class IKnowledgeAgent(IAgent):
    """Interface para agentes que manejan conocimiento"""
    
    @abstractmethod
    async def search_knowledge(self, query: str) -> List[Dict[str, Any]]:
        """Busca información relevante"""
        pass

class IWeatherAgent(IAgent):
    """Interface para agentes que manejan información del clima"""
    
    @abstractmethod
    async def get_weather(self, location: str) -> Optional[str]:
        """Obtiene información del clima"""
        pass

class ILocationAgent(IAgent):
    """Interface para agentes que manejan ubicaciones y mapas"""
    
    @abstractmethod
    async def extract_locations(self, text: str) -> List[Dict[str, Any]]:
        """Extrae ubicaciones del texto"""
        pass
    
    @abstractmethod
    async def create_map(self, locations: List[Dict[str, Any]]) -> Any:
        """Crea un mapa con las ubicaciones"""
        pass

class ILLMAgent(IAgent):
    """Interface para agentes que manejan modelos de lenguaje"""
    
    @abstractmethod
    async def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        """Genera una respuesta usando el modelo de lenguaje"""
        pass

class ICoordinatorAgent(IAgent):
    """Interface para el agente coordinador"""
    
    @abstractmethod
    async def coordinate(self, query: UserQuery) -> TourGuideResponse:
        """Coordina la interacción entre agentes"""
        pass
        
    @abstractmethod
    def register_agent(self, agent: IAgent) -> None:
        """Registra un nuevo agente"""
        pass
