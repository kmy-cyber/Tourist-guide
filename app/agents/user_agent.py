"""
Agente especializado en gestionar perfiles y contextos de usuario.
Mantiene el estado y las preferencias del usuario durante la interacción.
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from .base_agent import BaseAgent
from .interfaces import IUserAgent, AgentType, AgentContext
from ..models import UserProfile, UserContext

logger = logging.getLogger(__name__)

class UserAgent(BaseAgent, IUserAgent):
    """
    Agente que gestiona la información y contexto del usuario.
    Mantiene persistencia de datos entre sesiones.
    """
    
    def __init__(self, data_dir: str):
        """
        Inicializa el agente de usuario.
        
        Args:
            data_dir: Directorio base donde se almacenarán los datos de usuario
        """
        super().__init__(AgentType.USER)
        self.data_dir = Path(data_dir) / "users"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._context_cache = {}
        
        # Patrones para detectar nombres
        self.name_patterns = [
            r"me llamo (\w+)",
            r"soy (\w+)",
            r"mi nombre es (\w+)",
            r"^(\w+)$",  # Solo una palabra (posible nombre)
        ]
        
        # Palabras comunes que NO son nombres
        self.common_words = {
            'el', 'la', 'un', 'una', 'si', 'no', 'que', 'como', 'donde',
            'cuando', 'quien', 'cual', 'muy', 'mas', 'menos', 'bien', 'mal',
            'hola', 'gracias', 'por', 'favor', 'clima', 'tiempo', 'museo',
            'excursion', 'playa', 'hotel', 'cuba', 'habana', 'santiago'
        }
        
    async def process(self, context: AgentContext) -> AgentContext:
        """
        Procesa el contexto actual actualizando la información del usuario.
        """
        try:
            # Extraer/generar user_id del metadata
            user_id = context.metadata.get('user_id', 'anonymous')
            
            # Obtener o crear contexto de usuario
            user_context = await self.get_user_context(user_id)
            
            # Intentar extraer nombre si no lo tenemos
            if not user_context.profile.name and context.query:
                potential_name = self.extract_user_name(context.query)
                if potential_name:
                    user_context.profile.name = potential_name
                    self.logger.info(f"✅ Learned user name: {potential_name}")
            
            # Actualizar última actividad
            user_context.profile.last_active = datetime.now()
            user_context.profile.interaction_count += 1
            
            # Actualizar timestamp de consulta
            user_context.last_query_timestamp = datetime.now()
            
            # Extraer intereses de la consulta
            interests = self.extract_interests(context.query)
            for interest in interests:
                if interest not in user_context.interests:
                    user_context.interests.append(interest)
            
            # Actualizar ubicaciones mencionadas (esto se hará después cuando location_agent procese)
            # Por ahora solo añadimos al contexto
            context.metadata['user_context'] = user_context.dict()
            
            # Guardar cambios
            await self._save_user_context(user_id, user_context)
            
            self.update_context_confidence(context, 0.9)
            self.logger.info(f"User context processed for {user_context.profile.name or user_id}")
            
            return context
            
        except Exception as e:
            self.set_error(context, f"Error processing user context: {str(e)}")
            return context
    
    def extract_user_name(self, query: str) -> Optional[str]:
        """
        Extrae el nombre del usuario de una consulta.
        """
        query_lower = query.lower().strip()
        
        for pattern in self.name_patterns:
            match = re.search(pattern, query_lower)
            if match:
                name = match.group(1).title()
                # Verificar que no sea una palabra común
                if (name.lower() not in self.common_words and 
                    len(name) > 1 and 
                    name.isalpha()):
                    return name
        
        return None
    
    def extract_interests(self, query: str) -> List[str]:
        """
        Extrae intereses del usuario basado en su consulta.
        """
        query_lower = query.lower()
        interests = []
        
        interest_keywords = {
            "museos": ["museo", "galeria", "arte", "historia", "cultura", "exposicion"],
            "naturaleza": ["playa", "parque", "naturaleza", "senderismo", "montaña"],
            "excursiones": ["excursion", "tour", "visita", "recorrido", "aventura"],
            "gastronomia": ["comida", "restaurante", "gastronomia", "cafe", "cocina"],
            "musica": ["musica", "baile", "salsa", "son", "rumba", "concierto"],
            "arquitectura": ["arquitectura", "edificio", "monumento", "iglesia", "catedral"],
            "deportes": ["deporte", "buceo", "surf", "pesca", "golf"]
        }
        
        for category, keywords in interest_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                interests.append(category)
        
        return interests
    
    async def get_user_context(self, user_id: str) -> UserContext:
        """
        Obtiene el contexto actual del usuario.
        Si no existe, crea uno nuevo.
        """
        # Verificar caché primero
        if user_id in self._context_cache:
            return self._context_cache[user_id]
            
        context_path = self.data_dir / f"{user_id}.json"
        
        if context_path.exists():
            try:
                with open(context_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                context = UserContext.from_dict(data)
                self.logger.info(f"Loaded existing user context for {context.profile.name or user_id}")
            except Exception as e:
                self.logger.error(f"Error loading user context: {e}")
                context = self._create_new_context(user_id)
        else:
            context = self._create_new_context(user_id)
            self.logger.info(f"Created new user context for {user_id}")
            
        self._context_cache[user_id] = context
        return context
    
    async def update_user_context(self, user_id: str, 
                                context_updates: Dict[str, Any]) -> None:
        """
        Actualiza el contexto del usuario con nueva información.
        """
        context = await self.get_user_context(user_id)
        
        # Actualizar campos relevantes
        if 'preferences' in context_updates:
            context.profile.preferences.update(context_updates['preferences'])
            
        if 'current_session' in context_updates:
            context.current_session.update(context_updates['current_session'])
            
        if 'interests' in context_updates:
            new_interests = [i for i in context_updates['interests'] 
                           if i not in context.interests]
            context.interests.extend(new_interests)
            
        if 'mentioned_locations' in context_updates:
            new_locations = [loc for loc in context_updates['mentioned_locations']
                           if loc not in context.mentioned_locations]
            context.mentioned_locations.extend(new_locations)
            
        await self._save_user_context(user_id, context)
    
    async def save_interaction(self, user_id: str, 
                             query: str, response: str) -> None:
        """
        Guarda una interacción en el historial del usuario.
        """
        context = await self.get_user_context(user_id)
        
        interaction = {
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'response': response[:500] + "..." if len(response) > 500 else response  # Limitar longitud
        }
        
        context.conversation_history.append(interaction)
        
        # Mantener solo las últimas 20 interacciones
        if len(context.conversation_history) > 20:
            context.conversation_history = context.conversation_history[-20:]
            
        await self._save_user_context(user_id, context)
    
    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Obtiene las preferencias del usuario.
        """
        context = await self.get_user_context(user_id)
        return context.profile.preferences
    
    def _create_new_context(self, user_id: str) -> UserContext:
        """
        Crea un nuevo contexto de usuario.
        """
        current_time = datetime.now()
        profile = UserProfile(
            user_id=user_id,
            name=None,
            last_active=current_time,
            created_at=current_time,
            interaction_count=0,
            preferences={},
            interests=[],
            locations=[]
        )
        return UserContext(
            profile=profile,
            mentioned_locations=[],
            interests=[],
            conversation_history=[],
            current_session={},
            last_query_timestamp=current_time
        )
    
    async def _save_user_context(self, user_id: str, context: UserContext) -> None:
        """
        Guarda el contexto del usuario en disco.
        """
        try:
            context_path = self.data_dir / f"{user_id}.json"
            
            # Asegurar que el directorio existe
            context_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(context_path, 'w', encoding='utf-8') as f:
                json.dump(context.dict(), f, ensure_ascii=False, indent=2)
            
            self._context_cache[user_id] = context
            
        except Exception as e:
            self.logger.error(f"Error saving user context for {user_id}: {e}")
    
    async def update_mentioned_locations(self, user_id: str, locations: List[str]) -> None:
        """
        Actualiza las ubicaciones mencionadas por el usuario.
        """
        try:
            context = await self.get_user_context(user_id)
            
            new_locations = [loc for loc in locations if loc not in context.mentioned_locations]
            if new_locations:
                context.mentioned_locations.extend(new_locations)
                await self._save_user_context(user_id, context)
                self.logger.info(f"Added {len(new_locations)} new locations for user {context.profile.name or user_id}")
                
        except Exception as e:
            self.logger.error(f"Error updating mentioned locations: {e}")
    
    def get_user_summary(self, user_context: UserContext) -> str:
        """
        Genera un resumen del usuario para usar en prompts.
        """
        summary_parts = []
        
        if user_context.profile.name:
            summary_parts.append(f"El usuario se llama {user_context.profile.name}.")
        
        if user_context.interests:
            interests_text = ", ".join(user_context.interests[:3])  # Solo top 3
            summary_parts.append(f"Le interesan: {interests_text}.")
        
        if user_context.mentioned_locations:
            locations_text = ", ".join(user_context.mentioned_locations[-3:])  # Últimas 3
            summary_parts.append(f"Ha preguntado sobre: {locations_text}.")
        
        interaction_count = user_context.profile.interaction_count
        if interaction_count > 1:
            summary_parts.append(f"Esta es su {interaction_count}ª interacción.")
        
        return " ".join(summary_parts)
