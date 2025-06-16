from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Union, Any

class UserQuery(BaseModel):
    text: str
    filters: Optional[Dict[str, str]] = None

class SourceInfo(BaseModel):
    type: str
    reliability: str
    url: Optional[str] = None

class LocationInfo(BaseModel):
    address: str
    coordinates: Optional[Dict[str, float]] = None

class TourismItem(BaseModel):
    id: str
    name: str
    type: str
    description: str
    location: LocationInfo
    source_info: SourceInfo
    metadata: Optional[Dict] = None

class TourGuideResponse(BaseModel):
    answer: str
    sources: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    items: Optional[List[TourismItem]] = None
    error: Optional[str] = None
    map_data: Optional[Any] = None  # Para el mapa de Folium


class UserProfile(BaseModel):
    """Perfil del usuario"""
    user_id: str
    name: Optional[str] = None
    last_active: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    interaction_count: int = 0
    preferences: Dict[str, Any] = Field(default_factory=dict)
    interests: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True
        allow_population_by_field_name = True


class UserContext(BaseModel):
    """Contexto completo del usuario"""
    profile: UserProfile
    mentioned_locations: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    current_session: Dict[str, Any] = Field(default_factory=dict)
    last_query_timestamp: Optional[datetime] = None
    
    def dict(self):
        """Convierte a diccionario para serialización"""
        return {
            'profile': {
                'user_id': self.profile.user_id,
                'name': self.profile.name,
                'last_active': self.profile.last_active.isoformat() if self.profile.last_active else None,
                'interaction_count': self.profile.interaction_count,
                'preferences': self.profile.preferences,
                'created_at': self.profile.created_at.isoformat() if self.profile.created_at else None
            },
            'mentioned_locations': self.mentioned_locations,
            'interests': self.interests,
            'conversation_history': self.conversation_history[-20:],  # Solo últimas 20 interacciones
            'current_session': self.current_session,
            'last_query_timestamp': self.last_query_timestamp.isoformat() if self.last_query_timestamp else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        """Crea instancia desde diccionario"""
        profile_data = data.get('profile', {})
        profile = UserProfile(
            user_id=profile_data.get('user_id', ''),
            name=profile_data.get('name'),
            last_active=datetime.fromisoformat(profile_data['last_active']) if profile_data.get('last_active') else None,
            interaction_count=profile_data.get('interaction_count', 0),
            preferences=profile_data.get('preferences', {}),
            created_at=datetime.fromisoformat(profile_data['created_at']) if profile_data.get('created_at') else datetime.now()
        )
        
        return cls(
            profile=profile,
            mentioned_locations=data.get('mentioned_locations', []),
            interests=data.get('interests', []),
            conversation_history=data.get('conversation_history', []),
            current_session=data.get('current_session', {}),
            last_query_timestamp=datetime.fromisoformat(data['last_query_timestamp']) if data.get('last_query_timestamp') else None
        )
