from pydantic import BaseModel, Field
from typing import List, Optional

class UserQuery(BaseModel):
    text: str

class TourGuideResponse(BaseModel):
    answer: str
    sources: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None
