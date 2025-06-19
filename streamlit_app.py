"""
Aplicación Streamlit para el sistema de guía turístico de Cuba.
"""
import streamlit as st
import asyncio
import os
import uuid

# Constantes
UPDATING_DB_MSG = "🔄 Actualizando base de datos..."
DB_UPDATED_MSG = "✅ Base de datos actualizada correctamente!"
KNOWLEDGE_AGENT_NOT_AVAILABLE = "KnowledgeAgent no está disponible"
KNOWLEDGE_AGENT_WRONG_TYPE = "KnowledgeAgent no es del tipo correcto"
DIV_CLASS_SIDE_PANEL = '<div class="side-panel pulse">'
DIV_END = '</div>'

class AgentNotAvailableError(Exception):
    """Excepción lanzada cuando un agente requerido no está disponible."""
    pass
from app.agents.coordinator_agent import CoordinatorAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.weather_agent import WeatherAgent
from app.agents.location_agent import LocationAgent
from app.agents.llm_agent import LLMAgent
from app.agents.ui_agent import UIAgent
from app.agents.user_agent import UserAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.interfaces import AgentType
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(layout="wide")

# Título y descripción
st.title("🏖️ Guía Turístico Virtual de Cuba")
st.markdown("""
<div style="font-size: 1.05rem; margin-bottom: 30px; color: var(--text-secondary);">
Explora la riqueza cultural y natural de Cuba con nuestro asistente inteligente. 
Descubre <span style="color: var(--primary-color); font-weight: 500;">museos, excursiones</span> y 
<span style="color: var(--primary-color); font-weight: 500;">lugares de interés</span> con información en tiempo real.
</div>
""", unsafe_allow_html=True)

# Inicializar el sistema multiagente
@st.cache_resource
def get_coordinator():
    """Inicializa y configura el sistema multiagente."""
    try:
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        logger.info(f"Initializing coordinator with data_dir: {data_dir}")
        coordinator = CoordinatorAgent(data_dir)
        
        # Registrar agentes
        logger.info("Creating agents...")
        knowledge_agent = KnowledgeAgent(data_dir)
        weather_agent = WeatherAgent()
        location_agent = LocationAgent()
        llm_agent = LLMAgent()
        ui_agent = UIAgent()
        planner_agent = PlannerAgent()
        user_agent = UserAgent(data_dir)
        
        logger.info("Registering agents with coordinator...")
        coordinator.register_agent(knowledge_agent)
        coordinator.register_agent(weather_agent)
        coordinator.register_agent(location_agent)
        coordinator.register_agent(llm_agent)
        coordinator.register_agent(ui_agent)
        coordinator.register_agent(planner_agent)
        coordinator.register_agent(user_agent)
        
        # Verificar registro de agentes
        agent_status = coordinator.get_agent_status()
        logger.info(f"Agent registration status: {agent_status}")
        
        # Inicializar el sistema de forma asíncrona
        logger.info("Initializing agents asynchronously...")
        async def initialize_agents():
            await coordinator.initialize()
            # Verificar que el KnowledgeAgent está disponible
            if not coordinator.get_agent(AgentType.KNOWLEDGE):
                raise AgentNotAvailableError(KNOWLEDGE_AGENT_NOT_AVAILABLE)
            logger.info("All agents initialized successfully")
            
        try:
            # Intentar obtener el bucle de eventos actual
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # Crear un nuevo bucle si no existe uno
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        # Ejecutar la inicialización
        try:
            loop.run_until_complete(initialize_agents())
        except Exception as e:
            logger.error(f"Error during async initialization: {str(e)}", exc_info=True)
            raise
            
        return coordinator
        
    except Exception as e:
        logger.error(f"Error initializing coordinator: {str(e)}", exc_info=True)
        raise

coordinator = get_coordinator()

# Inicializar estado de la sesión
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())  # ✅ NUEVO: ID único por sesión
    logger.info(f"Generated new user_id: {st.session_state.user_id}")
if "show_map" not in st.session_state:
    st.session_state.show_map = True
if "show_weather" not in st.session_state:
    st.session_state.show_weather = True
if "show_planner" not in st.session_state:
    st.session_state.show_planner = True
if "updating_db" not in st.session_state:
    st.session_state.updating_db = False

def show_user_info():
    """Muestra información del usuario en la barra lateral"""
    if len(st.session_state.messages) > 0:
        # Buscar el nombre del usuario en los mensajes
        user_name = None
        for msg in st.session_state.messages:
            if msg.get("role") == "user":
                content = msg.get("content", "").lower()
                if "me llamo" in content:
                    # Extraer nombre simple
                    words = content.split()
                    try:
                        llamo_index = words.index("llamo")
                        if llamo_index + 1 < len(words):
                            user_name = words[llamo_index + 1].title()
                            break
                    except:
                        pass
        
        if user_name:
            st.sidebar.success(f"👤 Usuario: {user_name}")
            st.sidebar.caption(f"ID de sesión: {st.session_state.user_id[:8]}...")


# Función para manejar el cambio de estado de los toggles
def toggle_component(component):
    st.session_state[f"show_{component}"] = not st.session_state[f"show_{component}"]
    st.rerun()

# Barra de opciones estilo ChatGPT
with st.container():
    map_active = "active" if st.session_state.show_map else ""
    weather_active = "active" if st.session_state.show_weather else ""
    planner_active = "active" if st.session_state.show_planner else ""
    update_active = "active" if st.session_state.updating_db else ""
    
    # Usamos columnas para organizar los botones
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button(
            "🗺️ Mapa",
            key="map_toggle",
            use_container_width=True,
            type="primary" if st.session_state.show_map else "secondary"
        ):
            toggle_component("map")
    with col2:
        if st.button(
            "🌤️ Clima",
            key="weather_toggle",
            use_container_width=True,
            type="primary" if st.session_state.show_weather else "secondary"
        ):
            toggle_component("weather")
    with col3:
        if st.button(
            "📅 Planificador",
            key="planner_toggle",
            use_container_width=True,
            type="primary" if st.session_state.show_planner else "secondary"
        ):
            toggle_component("planner")
    with col4:
        update_clicked = st.button(
            "🔄 Actualizar BD",
            key="update_toggle",
            use_container_width=True,
            type="primary" if st.session_state.updating_db else "secondary"
        )

# Lógica de actualización de BD en el flujo principal
if update_clicked:
    st.session_state.updating_db = True
    # Forzar re-renderizado inmediato para mostrar spinner
    st.rerun()

if st.session_state.updating_db:
    try:
        with st.spinner(UPDATING_DB_MSG):
            knowledge_agent = coordinator.get_agent(AgentType.KNOWLEDGE)
            
            # ✅ Un solo método, simple
            asyncio.run(knowledge_agent.refresh_knowledge())
            
            st.success(DB_UPDATED_MSG)
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
    finally:
        st.session_state.updating_db = False
        st.rerun()



# Interface principal con dos columnas
col1, col2 = st.columns([2, 1], gap="large")

# Área principal de mensajes (col1)
with col1:
    with st.container():
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        
        # Mostrar mensajes anteriores con nuevo diseño
        for message in st.session_state.messages:
            bubble_class = "user-bubble" if message["role"] == "user" else "assistant-bubble"
            bubble_icon = "👤" if message["role"] == "user" else "🤖"
            user_label = "Tú" if message["role"] == "user" else "Asistente"
            
            # Formateamos sin f-string compleja
            bubble_html = f"""
            <div class="chat-bubble {bubble_class}">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 5px;">
                    <span style="font-size: 1.2rem;">{bubble_icon}</span>
                    <strong>{user_label}</strong>
                </div>
                {message["content"]}
            </div>
            """
            st.markdown(bubble_html, unsafe_allow_html=True)
            
            # Mostrar nivel de confianza              
            if "confidence" in message:
                confidence = float(message["confidence"])
                st.progress(confidence, text=f"Confianza: {confidence:.0%}")
            
            # Mostrar fuentes si existen
            if "sources" in message and message["sources"]:
                with st.expander("📚 Fuentes de información", expanded=False):
                    st.caption(", ".join(message["sources"]))
        
        st.markdown('</div>', unsafe_allow_html=True)

# Panel lateral (col2)
with col2:
    show_user_info()

    if st.session_state.messages:                 
        last_message = st.session_state.messages[-1]
        
        # Sección de clima
        if st.session_state.show_weather and "weather_html" in last_message and last_message["weather_html"]:
            try:
                with st.container():
                    st.markdown('<div class="side-panel pulse">', unsafe_allow_html=True)
                    st.markdown('<div class="section-title">🌤️ CONDICIONES CLIMÁTICAS</div>', unsafe_allow_html=True)
                    st.components.v1.html(
                        last_message["weather_html"],
                        height=280,
                        scrolling=False
                    )
                    st.markdown('</div>', unsafe_allow_html=True)
            except Exception as e:
                logger.error(f"Error en componente del clima: {str(e)}")
        
        # Sección del planificador
        if st.session_state.show_planner and "itinerary" in last_message and last_message["itinerary"]:
            try:
                with st.container():
                    st.markdown('<div class="side-panel pulse">', unsafe_allow_html=True)
                    st.markdown('<div class="section-title">📅 ITINERARIO SUGERIDO</div>', unsafe_allow_html=True)
                    
                    # Mostrar el itinerario
                    itinerary = last_message["itinerary"]
                    for day in itinerary["days"]:
                        with st.expander(f"Día {day['day']}", expanded=True):
                            for activity in day['activities']:
                                activity_html = f"""
                                <div style="margin-bottom: 12px; padding: 10px; border-left: 3px solid var(--primary-color); background: rgba(var(--primary-color-rgb), 0.05);">
                                    <div style="font-weight: 600; color: var(--primary-color);">
                                        ⏱️ {activity['duration_hours']}h - {activity['name']}
                                    </div>
                                    <div style="font-size: 0.9rem; margin-top: 4px;">
                                        {activity['description']}
                                    </div>
                                    {f'<div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px;">🏛️ {activity["location"]}</div>' if "location" in activity else ""}
                                </div>
                                """
                                st.markdown(activity_html, unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
            except Exception as e:
                logger.error(f"Error en componente del planificador: {str(e)}")
        
        # Sección de mapa
        if st.session_state.show_map and "locations" in last_message and last_message.get("map_html"):
            try:
                with st.container():
                    st.markdown('<div class="side-panel pulse">', unsafe_allow_html=True)
                    st.markdown('<div class="section-title">🗺️ MAPA INTERACTIVO</div>', unsafe_allow_html=True)
                    st.components.v1.html(
                        last_message["map_html"],
                        height=400,
                        scrolling=False
                    )
                    
                    # Lista de ubicaciones
                    if last_message["locations"]:
                        with st.expander("📍 Lugares mencionados", expanded=True):
                            for loc in last_message["locations"]:
                                loc_html = f"""
                                <div style="margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #f0f0f0;">
                                    <div style="font-weight: 600; font-size: 1.05rem; color: var(--primary-color);">
                                        {loc['name']}
                                    </div>
                                    <div style="font-size: 0.9rem; color: var(--text-secondary); margin-top: 4px;">
                                        {loc.get('description', 'Lugar de interés turístico')}
                                    </div>
                                </div>
                                """
                                st.markdown(loc_html, unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
            except Exception as e:
                logger.error(f"Error en componente del mapa: {str(e)}")

# Campo de entrada
if prompt := st.chat_input("¿Qué te gustaría saber sobre Cuba?"):
    try:
        # Añadir mensaje del usuario con nuevo diseño
        user_message = {"role": "user", "content": prompt}
        st.session_state.messages.append(user_message)
        
        # Generar respuesta
        with st.spinner("🔍 Buscando información..."):
            # Procesar consulta con el sistema multiagente
            context = asyncio.run(coordinator.get_response(prompt))

            context.metadata["user_id"] = st.session_state.user_id
            
            # Preparar respuesta para el chat
            response_data = {
                "role": "assistant",
                "content": context.response or "Lo siento, no pude procesar tu consulta.",
                "confidence": context.confidence,
                "sources": context.sources
            }
            
            # Añadir elementos visuales si están disponibles y activados
            if context.locations and st.session_state.show_map:
                response_data["locations"] = context.locations
                response_data["map_html"] = context.metadata.get("map_html")
                
            if context.weather_info and st.session_state.show_weather:
                response_data["weather_html"] = context.metadata.get("weather_html")

            # Añadir información del planificador si está disponible
            if hasattr(context, 'itinerary') and context.itinerary and st.session_state.show_planner:
                logger.info("Itinerario encontrado en la respuesta")
                if isinstance(context.itinerary, (list, dict)):
                    response_data["itinerary"] = context.itinerary
                    logger.info(f"Itinerario agregado a la respuesta: {context.itinerary}")
                else:
                    logger.warning(f"Formato de itinerario no válido: {type(context.itinerary)}")
            
            # Actualizar estado y forzar re-renderizado
            st.session_state.messages.append(response_data)
            st.rerun()
                
    except Exception as e:
        st.error(f"❌ Error procesando tu consulta: {str(e)}")
        logger.error(f"Error en el procesamiento de la consulta: {str(e)}", exc_info=True)

# JavaScript para manejar eventos
st.markdown("""
<script>
// Escuchar eventos de toggle
window.addEventListener("message", (event) => {
    if (event.data.streamlit && event.data.streamlit.type === 'toggle') {
        // Enviar evento a Python
        window.parent.postMessage({
            streamlit: {
                type: 'jsEvent',
                event: 'toggle',
                component: event.data.streamlit.component
            }
        }, '*');
    }
});
</script>
""", unsafe_allow_html=True)

# Manejar eventos desde JavaScript
if st.session_state.get('js_event'):
    event = st.session_state.js_event
    if event.get('type') == 'toggle':
        st.session_state.js_event = {
            'type': 'toggle',
            'component': event.get('component')
        }
        st.rerun()

class AgentNotAvailableError(Exception):
    """Excepción lanzada cuando un agente requerido no está disponible."""
    pass