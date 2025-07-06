"""
Agente especializado en gestionar perfiles y contextos de usuario bajo el modelo BDI.
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
    Agente BDI que gestiona la información y contexto del usuario.
    - Creencia: El estado actual del perfil del usuario.
    - Deseo: Mantener el perfil del usuario completo y actualizado.
    - Intención: Analizar la consulta para extraer y actualizar datos del perfil.
    """
    
    def __init__(self, data_dir: str):
        super().__init__(AgentType.USER)
        self.data_dir = Path(data_dir) / "users"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._context_cache: Dict[str, UserContext] = {}
        
        self.name_patterns = [r"me llamo (\w+)", r"soy (\w+)", r"mi nombre es (\w+)"]
        self.common_words = {'hola', 'gracias', 'si', 'no', 'museo', 'playa', 'hotel'}

    # --- Ciclo BDI ---

    def update_beliefs(self, context: AgentContext):
        """Percibe el contexto y carga el perfil del usuario en sus creencias."""
        super().update_beliefs(context)
        user_id = context.user_id
        # Cargar el contexto del usuario es parte de la percepción
        # Usamos una carga síncrona aquí para simplicidad en el ciclo.
        if user_id in self._context_cache:
            user_context = self._context_cache[user_id]
        else:
            user_context = self._load_user_context_sync(user_id)
            self._context_cache[user_id] = user_context
        
        self.beliefs['user_context'] = user_context

    def generate_desires(self):
        """Siempre desea mantener el contexto del usuario actualizado."""
        self.desires = ['update_user_profile']

    def generate_intentions(self):
        """Se compromete a la acción de procesar y actualizar el perfil."""
        self.intentions = []
        if 'update_user_profile' in self.desires:
            self.intentions.append(self.intend_to_process_user_data)

    # --- Intención ---

    async def intend_to_process_user_data(self, context: AgentContext) -> AgentContext:
        """
        Intención: Procesa la consulta actual para actualizar el perfil del usuario,
        guarda los cambios y enriquece el contexto compartido.
        """
        user_context: UserContext = self.beliefs['user_context']
        query = context.query

        # Extraer y actualizar nombre si no existe
        if not user_context.profile.name and query:
            potential_name = self._extract_user_name(query)
            if potential_name:
                user_context.profile.name = potential_name
                self.logger.info(f"✅ Learned user name: {potential_name}")

        # Extraer y actualizar intereses
        interests = self._extract_interests(query)
        for interest in interests:
            if interest not in user_context.interests:
                user_context.interests.append(interest)

        # Actualizar metadatos del perfil
        user_context.profile.last_active = datetime.now()
        user_context.profile.interaction_count += 1
        user_context.last_query_timestamp = datetime.now()

        # Guardar el contexto actualizado
        await self._save_user_context(user_context.profile.user_id, user_context)
        
        # Publicar el contexto del usuario en el contexto compartido para otros agentes
        context.metadata['user_context'] = user_context.dict()
        self.update_context_confidence(context, 0.9)
        self.logger.info(f"User context updated for {user_context.profile.name or user_context.profile.user_id}")

        return context

    # --- Métodos de Soporte ---

    def _extract_user_name(self, query: str) -> Optional[str]:
        query_lower = query.lower().strip()
        for pattern in self.name_patterns:
            match = re.search(pattern, query_lower)
            if match:
                name = match.group(1).title()
                if name.lower() not in self.common_words and len(name) > 2 and name.isalpha():
                    return name
        return None

    def _extract_interests(self, query: str) -> List[str]:
        # (La implementación no cambia)
        query_lower = query.lower()
        interests = []
        interest_keywords = {
            "museos": ["museo", "galeria", "arte", "historia"],
            "naturaleza": ["playa", "parque", "naturaleza", "senderismo"],
            "gastronomia": ["comida", "restaurante", "gastronomia"],
        }
        for category, keywords in interest_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                interests.append(category)
        return interests

    async def get_user_context(self, user_id: str) -> UserContext:
        if user_id in self._context_cache:
            return self._context_cache[user_id]
        context = self._load_user_context_sync(user_id)
        self._context_cache[user_id] = context
        return context
        
    def _load_user_context_sync(self, user_id: str) -> UserContext:
        context_path = self.data_dir / f"{user_id}.json"
        if context_path.exists():
            try:
                with open(context_path, 'r', encoding='utf-8') as f:
                    return UserContext.from_dict(json.load(f))
            except Exception as e:
                self.logger.error(f"Error loading user context for {user_id}: {e}")
        return self._create_new_context(user_id)

    def _create_new_context(self, user_id: str) -> UserContext:
        # (La implementación no cambia)
        profile = UserProfile(user_id=user_id, created_at=datetime.now())
        return UserContext(profile=profile)

    async def _save_user_context(self, user_id: str, context: UserContext):
        try:
            with open(self.data_dir / f"{user_id}.json", 'w', encoding='utf-8') as f:
                json.dump(context.dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving user context for {user_id}: {e}")

    async def save_interaction(self, user_id: str, query: str, response: str):
        context = await self.get_user_context(user_id)
        interaction = {'timestamp': datetime.now().isoformat(), 'query': query, 'response': response}
        context.conversation_history.append(interaction)
        context.conversation_history = context.conversation_history[-20:]
        await self._save_user_context(user_id, context)
