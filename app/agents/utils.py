"""
Utilidades y mixins para los agentes del sistema.
"""
from typing import Optional
from .interfaces import AgentContext

class AgentUtilsMixin:
    """Mixin que proporciona utilidades comunes para los agentes."""

    def update_context_confidence(
        self, 
        context: AgentContext,
        new_confidence: float,
        weight: float = 1.0
    ) -> None:
        """
        Actualiza la confianza del contexto usando un promedio ponderado.
        
        Args:
            context: Contexto a actualizar
            new_confidence: Nueva confianza a incorporar
            weight: Peso de la nueva confianza (0-1)
        """
        if not 0 <= weight <= 1:
            raise ValueError("Weight must be between 0 and 1")
            
        context.confidence = (
            context.confidence * (1 - weight) + 
            new_confidence * weight
        )

    def add_source(self, context: AgentContext, source: str) -> None:
        """
        Añade una fuente al contexto si no existe.
        
        Args:
            context: Contexto a actualizar
            source: Fuente a añadir
        """
        if source not in context.sources:
            context.sources.append(source)
            
    def set_error(
        self, 
        context: AgentContext, 
        error: str,
        log_error: bool = True
    ) -> None:
        """
        Establece un error en el contexto.
        
        Args:
            context: Contexto a actualizar
            error: Mensaje de error
            log_error: Si se debe registrar el error en el log
        """
        context.error = error
        context.confidence = 0.1
        if log_error and hasattr(self, 'logger'):
            self.logger.error(error)
