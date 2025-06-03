import streamlit as st
import asyncio
import os
from app.agent import TourGuideAgent
from app.models import UserQuery
from app.expert_system import QUERY_TYPES
import logging
import threading
import time

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar variables de estado
if "refresh_status" not in st.session_state:
    st.session_state.refresh_status = None
if "refresh_error" not in st.session_state:
    st.session_state.refresh_error = None
if "refresh_complete" not in st.session_state:
    st.session_state.refresh_complete = False

# Configuración de la página
st.set_page_config(
    page_title="Guía Turístico Cuba",
    page_icon="🏖️",
    layout="wide"
)

# Inicializar el agente
@st.cache_resource
def get_agent():
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    return TourGuideAgent(data_dir)

agent = get_agent()

# Helper async para llamar al agente
async def fetch_response(query: UserQuery):
    try:
        return await agent.process_query(query)
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return None

# Área de chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# Interface principal
col1, col2 = st.columns([2, 1])

# Sidebar con componente del clima
with st.sidebar:
    st.header("🌡️ Consulta el Clima")
    ciudad_selected = st.selectbox(
        "Selecciona una ciudad:",
        agent.ciudades_cuba,
        index=0
    )
    if st.button("Ver clima actual"):
        with st.spinner("Consultando el clima..."):
            weather_report = agent.weather_service.get_weather_report(ciudad_selected)
            if weather_report:
                st.markdown(weather_report, unsafe_allow_html=True)
            else:
                st.error("No se pudo obtener la información del clima en este momento.")

    st.markdown("---")
    st.header("🎯 Enfoque del Sistema")
    st.markdown("""
    ### Museos
    - Arte y cultura
    - Historia
    - Ciencia
    - Colecciones especiales
    
    ### Excursiones
    - Tours urbanos
    - Rutas culturales
    - Senderos naturales
    - Aventuras temáticas
    """)

with col1:
    # Mostrar mensajes anteriores
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if isinstance(message["content"], str) and "<!DOCTYPE html>" not in message["content"]:
                st.markdown(message["content"], unsafe_allow_html=True)
            else:
                st.markdown(message["content"], unsafe_allow_html=True)
            if "confidence" in message:
                conf_color = "green" if message["confidence"] > 0.7 else "yellow" if message["confidence"] > 0.4 else "red"
                st.progress(message["confidence"], text=f"Confianza: {message['confidence']:.0%}")
            if "sources" in message and message["sources"]:
                st.caption(f"📚 Fuentes: {', '.join(message['sources'])}")

    # Input del usuario
    if prompt := st.chat_input("¿Qué te gustaría saber sobre Cuba?"):
        # Añadir mensaje del usuario
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generar respuesta
        with st.chat_message("assistant"):
            with st.spinner("Analizando tu consulta..."):
                try:
                    # Usar asyncio para manejar la corutina
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    response = loop.run_until_complete(fetch_response(UserQuery(text=prompt)))
                    loop.close()
                    
                    if response and not response.error:
                        st.markdown(response.answer, unsafe_allow_html=True)
                        
                        # Mostrar nivel de confianza
                        conf_color = "green" if response.confidence > 0.7 else "yellow" if response.confidence > 0.4 else "red"
                        st.progress(response.confidence, text=f"Confianza en la respuesta: {response.confidence:.0%}")
                        
                        # Mostrar fuentes
                        if response.sources:
                            st.caption(f"📚 Fuentes consultadas: {', '.join(response.sources)}")
                        
                        # Guardar en historial
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": response.answer,
                            "confidence": response.confidence,
                            "sources": response.sources
                        })
                    else:
                        st.error("Lo siento, hubo un error al procesar tu consulta. Por favor, intenta de nuevo.")
                        
                except Exception as e:
                    logger.error(f"Error in Streamlit app: {e}")
                    st.error("Ocurrió un error inesperado. Por favor, intenta de nuevo.")

with col2:
    # Botón para actualizar datos
    if st.sidebar.button("🔄 Actualizar Base de Datos"):
        placeholder = st.sidebar.empty()
        try:
            placeholder.info("⏳ Actualizando datos... Por favor espere.")
            # Run refresh directly - no threading needed since Streamlit handles this
            agent.kb.refresh_data()
            placeholder.success("✅ Base de datos actualizada exitosamente")
            time.sleep(2)
            placeholder.empty()
            st.rerun()
        except Exception as e:
            placeholder.error(f"❌ Error al actualizar: {str(e)}")
            time.sleep(5)
            placeholder.empty()
            st.rerun()

    # Botón para limpiar historial
    if st.sidebar.button("🗑️ Limpiar Historial"):
        st.session_state.messages = []
        st.rerun()

# Verificar API key
if "FIREWORKS_API_KEY" not in os.environ:
    st.warning(
        "⚠️ No se encontró la API key de Fireworks. "
        "Asegúrate de configurar el archivo .env con tu API key."
    )
