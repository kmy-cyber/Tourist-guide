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
        margin-right: auto;
    }
    .side-panel {
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
# Añadir estado para los nuevos toggles
if "show_map" not in st.session_state: st.session_state.show_map = True
if "show_weather" not in st.session_state: st.session_state.show_weather = True
if "show_planner" not in st.session_state: st.session_state.show_planner = True
if "show_graph" not in st.session_state: st.session_state.show_graph = True

# --- Interfaz de Usuario ---
st.title("🏖️ Guía Turístico Virtual de Cuba (BDI)")
st.markdown("Bienvenido a tu asistente de viajes inteligente. Pregúntame cualquier cosa sobre tu próximo viaje a Cuba.")

# Barra de opciones con toggles
with st.container():
    cols = st.columns(4)
    with cols[0]:
        if st.button("🗺️ Mapa", use_container_width=True, type="primary" if st.session_state.show_map else "secondary"):
            st.session_state.show_map = not st.session_state.show_map
            st.rerun()
    with cols[1]:
        if st.button("🌤️ Clima", use_container_width=True, type="primary" if st.session_state.show_weather else "secondary"):
            st.session_state.show_weather = not st.session_state.show_weather
            st.rerun()
    with cols[2]:
        if st.button("📅 Planificador", use_container_width=True, type="primary" if st.session_state.show_planner else "secondary"):
            st.session_state.show_planner = not st.session_state.show_planner
            st.rerun()
    with cols[3]:
        if st.button("📊 Grafo", use_container_width=True, type="primary" if st.session_state.show_graph else "secondary"):
            st.session_state.show_graph = not st.session_state.show_graph
            st.rerun()

# --- Layout Principal ---
col1, col2 = st.columns([2, 1.2], gap="large")

with col1:
    st.header("Conversación")
    chat_container = st.container(height=600)
    for message in st.session_state.messages:
        role = message["role"]
        with chat_container:
            with st.chat_message(role, avatar="👤" if role == "user" else "🤖"):
                st.markdown(message["content"])

# --- Procesamiento de la Entrada del Usuario ---
if prompt := st.chat_input("Ej: ¿Qué museos hay en La Habana?"):
    if not coordinator:
        st.error("El sistema de agentes no está disponible.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
             with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)

        with st.spinner("Pensando... Los agentes están colaborando..."):
            try:
                final_context = asyncio.run(coordinator.get_response(prompt, st.session_state.user_id))
                assistant_response = {
                    "role": "assistant",
                    "content": final_context.response or "No he podido generar una respuesta.",
                    "context": final_context
                }
                st.session_state.messages.append(assistant_response)
                st.rerun()
            except Exception as e:
                logger.error(f"Error processing user query: {e}", exc_info=True)
                st.error(f"Ha ocurrido un error al procesar tu solicitud: {e}")

# --- Paneles Laterales (Derecha) ---
with col2:
    st.header("Información Adicional")
    last_assistant_message = next((m for m in reversed(st.session_state.messages) if m["role"] == "assistant"), None)
    
    if last_assistant_message:
        context: AgentContext = last_assistant_message.get("context")

        # Panel del Grafo de Conocimiento
        if st.session_state.show_graph and context and context.ui_elements.get("knowledge_graph_html"):
            with st.container():
                st.markdown('<div class="side-panel">', unsafe_allow_html=True)
                st.markdown('<div class="section-title">📊 GRAFO DE CONOCIMIENTO</div>', unsafe_allow_html=True)
                st.components.v1.html(
                    context.ui_elements["knowledge_graph_html"],
                    height=510,
                    scrolling=False
                )
                st.markdown('</div>', unsafe_allow_html=True)

        # Panel de Itinerario
        if st.session_state.show_planner and context and context.itinerary:
            with st.container():
                st.markdown('<div class="side-panel">', unsafe_allow_html=True)
                st.markdown('<div class="section-title">📅 ITINERARIO SUGERIDO</div>', unsafe_allow_html=True)
                # ... (lógica para mostrar itinerario) ...
                st.markdown('</div>', unsafe_allow_html=True)

        # Panel del Clima
        if st.session_state.show_weather and context and context.ui_elements.get("weather_html"):
            with st.container():
                st.markdown('<div class="side-panel">', unsafe_allow_html=True)
                st.markdown('<div class="section-title">🌤️ CLIMA ACTUAL</div>', unsafe_allow_html=True)
                st.components.v1.html(context.ui_elements["weather_html"], height=200)
                st.markdown('</div>', unsafe_allow_html=True)

        # Panel del Mapa
        if st.session_state.show_map and context and context.ui_elements.get("map_html"):
            with st.container():
                st.markdown('<div class="side-panel">', unsafe_allow_html=True)
                st.markdown('<div class="section-title">🗺️ MAPA INTERACTIVO</div>', unsafe_allow_html=True)
                st.components.v1.html(context.ui_elements["map_html"], height=400)
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Aquí aparecerá información adicional como mapas, clima o itinerarios.")

# --- Barra Lateral (Sidebar) ---
with st.sidebar:
    st.header("Opciones")
    st.info(f"ID de Usuario: `{st.session_state.user_id[:8]}...`")
    if st.button("Limpiar Conversación"):
        st.session_state.messages = []
        st.rerun()
