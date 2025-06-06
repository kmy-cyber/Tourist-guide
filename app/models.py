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
