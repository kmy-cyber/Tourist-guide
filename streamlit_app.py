"""
Aplicación Streamlit para el sistema de guía turístico de Cuba.
"""
import streamlit as st
import asyncio
import os
from app.agents.coordinator_agent import CoordinatorAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.weather_agent import WeatherAgent
from app.agents.location_agent import LocationAgent
from app.agents.llm_agent import LLMAgent
from app.agents.ui_agent import UIAgent
from app.models import UserQuery
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de la página
st.set_page_config(
    page_title="Guía Turístico Cuba",
    page_icon="🏖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilos CSS personalizados
st.markdown("""
<style>
/* Estilo general */
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: #333;
    background-color: #f8f9fa;
}

/* Contenedor principal */
.main {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 20px;
}

/* Barra de opciones */
.options-bar {
    display: flex;
    gap: 15px;
    margin: 20px 0;
    padding: 12px 15px;
    border-radius: 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    align-items: center;
    position: sticky;
    top: 10px;
    z-index: 100;
}

.option-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    border-radius: 24px;
    background: #f1f3f5;
    cursor: pointer;
    transition: all 0.3s ease;
    user-select: none;
    border: 1px solid transparent;
}

.option-toggle:hover {
    background: #e9ecef;
    transform: translateY(-2px);
}

.option-toggle.active {
    background: #e6f4ff;
    border-color: #1a73e8;
    color: #1a73e8;
    box-shadow: 0 2px 8px rgba(26, 115, 232, 0.2);
}

.option-toggle.active .toggle-icon {
    color: #1a73e8;
}

.toggle-icon {
    font-size: 1.2rem;
    transition: color 0.3s ease;
}

/* Área de chat */
.chat-container {
    border-radius: 16px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    padding: 24px;
    margin-bottom: 20px;
    min-height: 500px;
    display: flex;
    flex-direction: column;
}

.chat-bubble {
    max-width: 85%;
    padding: 16px 20px;
    border-radius: 20px;
    margin-bottom: 15px;
    position: relative;
    animation: fadeIn 0.3s ease;
}

.user-bubble {
    background: #e6f4ff;
    border-bottom-right-radius: 4px;
    align-self: flex-end;
}

.assistant-bubble {
    background: #f8f9fa;
    border-bottom-left-radius: 4px;
    align-self: flex-start;
    border: 1px solid #eee;
}

.confidence-bar {
    height: 6px;
    border-radius: 3px;
    margin-top: 8px;
    background: linear-gradient(90deg, #4CAF50 0%, #FFC107 50%, #F44336 100%);
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Panel lateral */
.side-panel {
    border-radius: 16px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    padding: 20px;
    height: fit-content;
}

.section-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #1a73e8;
    margin-bottom: 15px;
    display: flex;
    align-items: center;
    gap: 8px;
    padding-bottom: 10px;
    border-bottom: 1px solid #eee;
}

/* Campo de entrada */
.stChatFloatingInputContainer {
    border-radius: 24px !important;
    box-shadow: 0 5px 20px rgba(0,0,0,0.1) !important;
    border: none !important;
    padding: 8px !important;
}

/* Animaciones */
@keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.03); }
    100% { transform: scale(1); }
}

.pulse {
    animation: pulse 1.5s infinite;
}

/* Progress bar personalizada */
.stProgress > div > div > div {
    background-color: #1a73e8 !important;
    border-radius: 4px !important;
}

</style>
""", unsafe_allow_html=True)

# Título y descripción
st.title("🏖️ Guía Turístico Virtual de Cuba")
st.markdown("""
<div style="font-size: 1.1rem; margin-bottom: 30px;">
Explora la riqueza cultural y natural de Cuba con nuestro asistente inteligente. 
Descubre <span style="color: #1a73e8; font-weight: 500;">museos, excursiones</span> y 
<span style="color: #1a73e8; font-weight: 500;">lugares de interés</span> con información en tiempo real.
</div>
""", unsafe_allow_html=True)

# Inicializar el sistema multiagente
@st.cache_resource
def get_coordinator():
    """Inicializa y configura el sistema multiagente."""
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    coordinator = CoordinatorAgent(data_dir)
    
    # Registrar agentes
    coordinator.register_agent(KnowledgeAgent(data_dir))
    coordinator.register_agent(WeatherAgent())
    coordinator.register_agent(LocationAgent())
    coordinator.register_agent(LLMAgent())
    coordinator.register_agent(UIAgent())
    
    return coordinator

coordinator = get_coordinator()

# Inicializar estado de la sesión
if "messages" not in st.session_state:
    st.session_state.messages = []
if "show_map" not in st.session_state:
    st.session_state.show_map = True
if "show_weather" not in st.session_state:
    st.session_state.show_weather = True

# Función para manejar el cambio de estado de los toggles
def toggle_component(component):
    st.session_state[component] = not st.session_state[component]
    st.rerun()

# Barra de opciones con estilo moderno
st.markdown("""
<div class="options-bar">
    <div class="option-toggle" onclick="toggleOption('map')">
        <span class="toggle-icon">🗺️</span>
        <span>Mapa</span>
    </div>
    <div class="option-toggle" onclick="toggleOption('weather')">
        <span class="toggle-icon">🌤️</span>
        <span>Clima</span>
    </div>
</div>
""", unsafe_allow_html=True)

# JavaScript para manejar los toggles
st.markdown("""
<script>
function toggleOption(option) {
    // Envía un mensaje a Streamlit para cambiar el estado
    window.parent.postMessage({
        streamlit: {
            type: 'toggleOption',
            option: option
        }
    }, '*');
}

// Manejar mensajes desde Streamlit
window.addEventListener('message', (event) => {
    const message = event.data;
    if (message.streamlit && message.streamlit.type === 'updateToggles') {
        updateToggleStyles();
    }
});

function updateToggleStyles() {
    const mapActive = %s;
    const weatherActive = %s;
    
    const mapToggle = document.querySelector('.option-toggle:nth-child(1)');
    const weatherToggle = document.querySelector('.option-toggle:nth-child(2)');
    
    if (mapActive) {
        mapToggle.classList.add('active');
    } else {
        mapToggle.classList.remove('active');
    }
    
    if (weatherActive) {
        weatherToggle.classList.add('active');
    } else {
        weatherToggle.classList.remove('active');
    }
}

// Inicializar estilos al cargar
document.addEventListener('DOMContentLoaded', updateToggleStyles);
</script>
""" % (str(st.session_state.show_map).lower(), 
       str(st.session_state.show_weather).lower()), unsafe_allow_html=True)

# Manejar eventos de JavaScript
if st.session_state.get('js_event'):
    event = st.session_state.js_event
    if event.get('type') == 'toggleOption':
        toggle_component(event['option'])
    st.session_state.js_event = None

# Interface principal con dos columnas
col1, col2 = st.columns([2, 1], gap="large")

# Área principal de mensajes (col1)
with col1:
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    
    # Mostrar mensajes anteriores con nuevo diseño
    for message in st.session_state.messages:
        bubble_class = "user-bubble" if message["role"] == "user" else "assistant-bubble"
        
        with st.container():
            st.markdown(f"""
            <div class="chat-bubble {bubble_class}">
                {message["content"]}
            </div>
            """, unsafe_allow_html=True)
            
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
    if st.session_state.messages:                 
        last_message = st.session_state.messages[-1]
        logger.info(f"weather_html: {last_message['weather_html']}")
        
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
                                st.markdown(
                                    f"""
                                    <div style="margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #f0f0f0;">
                                        <div style="font-weight: 600; font-size: 1.05rem;">{loc['name']}</div>
                                        <div style="font-size: 0.9rem; color: #666; margin-top: 4px;">
                                            {loc.get('description', 'Lugar de interés turístico')}
                                        </div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
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

            # Actualizar estado
            st.session_state.messages.append(response_data)
            st.rerun()
                
    except Exception as e:
        st.error(f"❌ Error procesando tu consulta: {str(e)}")
        logger.error(f"Error en el procesamiento de la consulta: {str(e)}", exc_info=True)

# JavaScript adicional para manejar eventos
st.markdown("""
<script>
// Escuchar eventos de toggle desde el frontend
window.addEventListener('message', (event) => {
    const message = event.data;
    if (message.streamlit && message.streamlit.type === 'toggleOption') {
        window.parent.postMessage({
            streamlit: {
                type: 'jsEvent',
                data: {
                    type: 'toggleOption',
                    option: message.streamlit.option
                }
            }
        }, '*');
    }
});
</script>
""", unsafe_allow_html=True)
