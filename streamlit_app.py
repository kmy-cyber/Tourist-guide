import streamlit as st
import asyncio
import os
from app.models import UserQuery, TourGuideResponse
from app.agents.coordinator_agent import CoordinatorAgent
import logging

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

# Título y descripción
st.title("🏖️ Guía Turístico Virtual de Cuba")
st.markdown("""
Este sistema especializado te ayuda a explorar:
- 🏛️ Museos de arte, historia, ciencia y cultura
- 🚶 Excursiones urbanas y en la naturaleza
- 📍 Lugares de interés turístico
""")

# Inicializar el agente coordinador
@st.cache_resource
def get_coordinator():
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    return CoordinatorAgent(data_dir)

coordinator = get_coordinator()

# Helper async para procesar consultas
async def process_query(query: UserQuery) -> Optional[TourGuideResponse]:
    try:
        return await coordinator.coordinate(query)
    except Exception as e:
        logger.error(f"Error in Streamlit app: {str(e)}", exc_info=True)
        return None

# Área de chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# Interface principal
col1, col2 = st.columns([2, 1])

with col1:
    # Mostrar mensajes anteriores
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "confidence" in message:
                # Calcular color de confianza
                if message["confidence"] > 0.7:
                    conf_color = "green"
                elif message["confidence"] > 0.4:
                    conf_color = "yellow"
                else:
                    conf_color = "red"
                st.progress(message["confidence"], text=f"Confianza: {message['confidence']:.0%}")
                
            if "sources" in message and message["sources"]:
                st.caption(f"📚 Fuentes: {', '.join(message['sources'])}")
            
            # Mostrar mapa si está disponible
            if "map_data" in message and message["map_data"]:
                st.components.v1.html(
                    message["map_data"]._repr_html_(), 
                    height=400
                )

    # Input del usuario
    if prompt := st.chat_input("¿Qué te gustaría saber sobre Cuba?"):
        # Añadir mensaje del usuario
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generar respuesta
        with st.chat_message("assistant"):
            with st.spinner("Procesando tu consulta..."):
                query = UserQuery(text=prompt)
                response = asyncio.run(process_query(query))
                
                if response:
                    st.markdown(response.answer)
                    
                    # Guardar mensaje en el historial
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response.answer,
                        "sources": response.sources,
                        "confidence": response.confidence,
                        "map_data": response.map_data
                    })
                    
                    # Mostrar confianza
                    if response.confidence > 0.7:
                        conf_color = "green"
                    elif response.confidence > 0.4:
                        conf_color = "yellow"
                    else:
                        conf_color = "red"
                    st.progress(response.confidence, text=f"Confianza: {response.confidence:.0%}")
                    
                    # Mostrar fuentes
                    if response.sources:
                        st.caption(f"📚 Fuentes: {', '.join(response.sources)}")
                    
                    # Mostrar mapa si está disponible
                    if response.map_data:
                        st.components.v1.html(
                            response.map_data._repr_html_(), 
                            height=400
                        )
                else:
                    error_message = "Lo siento, ocurrió un error procesando tu consulta. Por favor, inténtalo de nuevo."
                    st.error(error_message)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_message,
                        "confidence": 0.1,
                        "sources": []
                    })
