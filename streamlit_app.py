"""
Aplicación Streamlit para el sistema de guía turístico de Cuba,
integrada con la arquitectura multiagente BDI proactiva.
"""
import streamlit as st
import asyncio
import os
import uuid
import logging

# Importaciones de los agentes BDI
from app.agents.coordinator_agent import CoordinatorAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.weather_agent import WeatherAgent
from app.agents.location_agent import LocationAgent
from app.agents.llm_agent import LLMAgent
from app.agents.ui_agent import UIAgent
from app.agents.user_agent import UserAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.interfaces import AgentType, AgentContext

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuración de la página
st.set_page_config(page_title="Guía de Cuba AI", layout="wide", initial_sidebar_state="auto")

# Estilos CSS personalizados para una mejor apariencia
st.markdown("""
<style>
    .stApp {
        background-color: #f0f2f6;
    }
    .st-emotion-cache-1y4p8pa {
        padding-top: 2rem;
    }
    .chat-bubble {
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        max-width: 85%;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .user-bubble {
        background-color: #dcf8c6;
        margin-left: auto;
        text-align: right;
    }
    .assistant-bubble {
        background-color: #ffffff;
        margin-right: auto;
    }
    .side-panel {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .section-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #005A9C;
        margin-bottom: 1rem;
        border-bottom: 2px solid #005A9C;
        padding-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Inicialización del Sistema Multiagente (BDI) ---
@st.cache_resource
def initialize_bdi_system():
    """
    Inicializa y configura el sistema multiagente BDI.
    Esta función se cachea para mantener una única instancia del sistema.
    """
    try:
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        logger.info(f"Initializing BDI system with data_dir: {data_dir}")
        
        coordinator = CoordinatorAgent(data_dir)
        
        # Registrar todos los agentes BDI
        coordinator.register_agent(KnowledgeAgent(data_dir))
        coordinator.register_agent(WeatherAgent())
        coordinator.register_agent(LocationAgent())
        coordinator.register_agent(LLMAgent())
        coordinator.register_agent(UIAgent())
        coordinator.register_agent(PlannerAgent())
        coordinator.register_agent(UserAgent(data_dir))
        
        logger.info(f"Agent registration status: {coordinator.get_agent_status()}")
        
        # Inicializar el sistema de forma asíncrona
        logger.info("Initializing all agents...")
        # Usar un nuevo bucle de eventos si no hay uno disponible (necesario para Streamlit)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        loop.run_until_complete(coordinator.initialize())
        logger.info("BDI System initialized successfully.")
        return coordinator
        
    except Exception as e:
        logger.error(f"Critical error initializing BDI system: {e}", exc_info=True)
        st.error(f"Error al iniciar el sistema de agentes: {e}")
        return None

coordinator = initialize_bdi_system()

# --- Estado de la Sesión ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())
    logger.info(f"New session started. User ID: {st.session_state.user_id}")

# --- Interfaz de Usuario ---
st.title("🏖️ Guía Turístico Virtual de Cuba (BDI)")
st.markdown("Bienvenido a tu asistente de viajes inteligente. Pregúntame cualquier cosa sobre tu próximo viaje a Cuba.")

# --- Layout Principal (Chat a la izquierda, Paneles a la derecha) ---
col1, col2 = st.columns([2, 1.2], gap="large")

with col1:
    st.header("Conversación")
    chat_container = st.container(height=600)
    
    # Mostrar mensajes de la conversación
    for message in st.session_state.messages:
        role = message["role"]
        with chat_container:
            with st.chat_message(role, avatar="👤" if role == "user" else "🤖"):
                st.markdown(message["content"])

# --- Procesamiento de la Entrada del Usuario ---
if prompt := st.chat_input("Ej: ¿Qué museos hay en La Habana?"):
    if not coordinator:
        st.error("El sistema de agentes no está disponible. No se puede procesar la solicitud.")
    else:
        # Añadir mensaje del usuario al historial y a la UI
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
             with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)

        # Iniciar el ciclo BDI para procesar la consulta
        with st.spinner("Pensando... Los agentes están colaborando para encontrar la mejor respuesta."):
            try:
                # Este es el punto de entrada principal a la arquitectura BDI
                final_context = asyncio.run(coordinator.get_response(prompt, st.session_state.user_id))

                # Preparar la respuesta del asistente para mostrar en la UI
                assistant_response = {
                    "role": "assistant",
                    "content": final_context.response or "No he podido generar una respuesta de texto.",
                    "context": final_context # Guardamos el contexto completo para renderizar los paneles
                }
                st.session_state.messages.append(assistant_response)
                st.rerun() # Volver a ejecutar el script para mostrar la nueva respuesta y los paneles

            except Exception as e:
                logger.error(f"Error processing user query: {e}", exc_info=True)
                st.error(f"Ha ocurrido un error al procesar tu solicitud: {e}")


# --- Paneles Laterales (Derecha) ---
with col2:
    st.header("Información Adicional")
    
    # Obtener el contexto de la última respuesta del asistente
    last_assistant_message = next((m for m in reversed(st.session_state.messages) if m["role"] == "assistant"), None)
    
    if last_assistant_message:
        context: AgentContext = last_assistant_message.get("context")

        # Panel de Itinerario
        if context and context.itinerary:
            with st.container():
                st.markdown('<div class="side-panel">', unsafe_allow_html=True)
                st.markdown('<div class="section-title">📅 Itinerario Sugerido</div>', unsafe_allow_html=True)
                itinerary = context.itinerary
                for day in itinerary.get("days", []):
                    with st.expander(f"**Día {day['day']}**", expanded=True):
                        for activity in day.get('activities', []):
                            st.markdown(f"**{activity['name']}** ({activity['type']})")
                            st.caption(f"Duración: {activity['duration_hours']}h | Costo: ${activity['cost']:.2f} | Ubicación: {activity['location']}")
                st.markdown('</div>', unsafe_allow_html=True)

        # Panel del Clima
        if context and context.ui_elements.get("weather_html"):
            with st.container():
                st.markdown('<div class="side-panel">', unsafe_allow_html=True)
                st.markdown('<div class="section-title">🌤️ Clima Actual</div>', unsafe_allow_html=True)
                st.components.v1.html(context.ui_elements["weather_html"], height=200)
                st.markdown('</div>', unsafe_allow_html=True)

        # Panel del Mapa
        if context and context.ui_elements.get("map_html"):
            with st.container():
                st.markdown('<div class="side-panel">', unsafe_allow_html=True)
                st.markdown('<div class="section-title">🗺️ Mapa Interactivo</div>', unsafe_allow_html=True)
                st.components.v1.html(context.ui_elements["map_html"], height=400)
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Aquí aparecerá información adicional como mapas, clima o itinerarios cuando sea relevante.")

# --- Barra Lateral (Sidebar) ---
with st.sidebar:
    st.header("Opciones del Sistema")
    st.info(f"ID de Usuario: `{st.session_state.user_id[:8]}...`")

    if st.button("Limpiar Conversación"):
        st.session_state.messages = []
        st.rerun()

    st.header("Estado de los Agentes")
    if coordinator:
        agent_status = coordinator.get_agent_status()
        for agent_name, status in agent_status.items():
            st.markdown(f"- **{agent_name}**: {'✅ Activo' if status else '❌ Inactivo'}")
    else:
        st.warning("Sistema no inicializado.")
