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
    layout="wide"
)

# Título y descripción
st.title("🏖️ Guía Turístico Virtual de Cuba")
st.markdown("""
Este sistema especializado te ayuda a explorar:
- 🏛️ Museos de arte, historia, ciencia y cultura
- 🚶 Excursiones urbanas y en la naturaleza
- 📍 Lugares de interés turístico
""")

# Inicializar el sistema multiagente
@st.cache_resource
def get_coordinator():
    """
    Inicializa y configura el sistema multiagente.
    """
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
if "last_update" not in st.session_state:
    st.session_state.last_update = None

# Interface principal con dos columnas
col1, col2 = st.columns([1, 2])

# Área principal de mensajes (col1)
with col1:
    # Contenedor del chat
    chat_container = st.container()
    
    with chat_container:
        # Mostrar mensajes anteriores
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                # Mostrar nivel de confianza                
                if "confidence" in message:
                    confidence = float(message["confidence"])
                    st.progress(confidence, text=f"Confianza: {confidence:.0%}")
                    st.caption("📊 Nivel de confianza basado en las fuentes y el contexto")
                
                # Mostrar fuentes si existen
                if "sources" in message and message["sources"]:
                    with st.expander("📚 Ver fuentes"):
                        st.caption(', '.join(message["sources"]))
# Panel lateral (col2)
with col2:
    # Estilos CSS para los componentes
    st.markdown("""
        <style>
        /* Estilo para contenedores de componentes */
        div[data-testid="stVerticalBlock"] > div {
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        /* Estilo para títulos de secciones */
        .component-title {
            color: #1a73e8;
            font-size: 1.2rem;
            margin-bottom: 1rem;
            font-weight: 500;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Contenedor lateral persistente
    side_container = st.container()
    
    with side_container:
        if st.session_state.messages:            
            last_message = st.session_state.messages[-1]

            # Sección de clima
            if "weather_html" in last_message and last_message["weather_html"]:
                try:
                    st.markdown('<p class="component-title">🌤️ Información del clima</p>', unsafe_allow_html=True)
                    with st.container():
                        st.components.v1.html(
                            last_message["weather_html"],
                            height=300,
                            scrolling=False
                        )
                except Exception as e:
                    st.warning("No se pudo cargar la información del clima", icon="⚠️")
                    logger.error(f"Error en componente del clima: {str(e)}")
            
            # Sección de mapa
            if "locations" in last_message and last_message.get("map_html"):
                try:
                    st.markdown('<p class="component-title">🗺️ Ubicaciones mencionadas</p>', unsafe_allow_html=True)
                    with st.container():
                        st.components.v1.html(
                            last_message["map_html"],
                            height=400,
                            scrolling=False
                        )
                        
                        # Lista de ubicaciones expandible
                        with st.expander("📍 Detalles de ubicaciones", expanded=False):
                            for loc in last_message["locations"]:
                                st.markdown(
                                    f"""
                                    **{loc['name']}**  
                                    *{loc.get('type', 'Lugar')}*  
                                    {f"_{loc.get('description', '')}_" if 'description' in loc else ''}
                                    """
                                )
                except Exception as e:
                    st.warning("No se pudo cargar el mapa interactivo", icon="⚠️")
                    logger.error(f"Error en componente del mapa: {str(e)}")
                    
                    # Mostrar fallback con lista de ubicaciones
                    for loc in last_message["locations"]:
                        st.markdown(f"📍 **{loc['name']}** ({loc.get('type', 'lugar')})")    
    
    # Input del usuario y procesamiento de respuesta
    if prompt := st.chat_input("¿Qué te gustaría saber sobre Cuba?"):
        try:
            # Añadir mensaje del usuario
            user_message = {"role": "user", "content": prompt}
            st.session_state.messages.append(user_message)
            
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generar respuesta
            with st.chat_message("assistant"):
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
                    
                    logger.info(f"Metadata: {context}")

                    # Añadir elementos visuales si están disponibles
                    if context.locations:
                        response_data["locations"] = context.locations
                        response_data["map_html"] = context.metadata.get("map_html")
                        
                    if context.weather_info:
                        response_data["weather_html"] = context.metadata.get("weather_html")

                    # Mostrar respuesta
                    st.markdown(response_data["content"])
                    
                    # Mostrar errores si los hay
                    if context.error:
                        st.error(f"⚠️ {context.error}")
                        
                    # Actualizar estado
                    st.session_state.messages.append(response_data)
                    st.session_state.last_update = response_data
                    
        except Exception as e:
            st.error(f"❌ Error procesando tu consulta: {str(e)}")
            logger.error(f"Error en el procesamiento de la consulta: {str(e)}", exc_info=True)
