import streamlit as st
import asyncio
import os
from app.agent import TourGuideAgent
from app.models import UserQuery

# Configuración de la página
st.set_page_config(
    page_title="Guía Turístico Cuba",
    page_icon="🏖️",
    layout="wide"
)

# Título y descripción
st.title("🏖️ Guía Turístico Virtual de Cuba")
st.markdown("""
Este es un prototipo de un sistema de guía turístico virtual que utiliza 
inteligencia artificial para responder preguntas sobre turismo en Cuba.
""")

# Inicializar el agente
@st.cache_resource
def get_agent():
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    return TourGuideAgent(data_dir)

agent = get_agent()

# Helper async para llamar al agente
async def fetch_response(prompt: str):
    return await agent.process_query(UserQuery(text=prompt))

# Área de chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar mensajes anteriores
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "confidence" in message:
            st.progress(message["confidence"], text="Nivel de confianza")
        if "sources" in message and message["sources"]:
            st.caption(f"Fuentes: {', '.join(message['sources'])}")

# Input del usuario
if prompt := st.chat_input("¿Qué te gustaría saber sobre Cuba?"):
    # Añadimos el mensaje del usuario al historial
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generamos la respuesta
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            # try:
            # Ejecuta la llamada async de forma sencilla
            response = asyncio.run(fetch_response(prompt))

            print("-"*20)
            print("resoponse")
            print(response)
            print("-"*20)

            # Renderizamos la respuesta
            st.markdown(response.answer)
            if response.confidence is not None:
                st.progress(response.confidence, text="Nivel de confianza")
            if response.sources:
                st.caption(f"Fuentes: {', '.join(response.sources)}")

            # Guardamos en el historial
            st.session_state.messages.append({
                "role": "assistant",
                "content": response.answer,
                "confidence": response.confidence,
                "sources": response.sources
            })

            # except Exception as e:
            #     st.error(f"Lo siento, hubo un error al procesar tu consulta: {e}")
            #     if "FIREWORKS_API_KEY" not in os.environ:
            #         st.warning(
            #             "⚠️ No se encontró la API key de Fireworks. "
            #             "Asegúrate de configurar el archivo .env con tu API key."
            #         )

# Sidebar con información adicional
with st.sidebar:
    st.header("Sobre el Proyecto")
    st.markdown("""
    Este es un prototipo de un sistema multiagente que actúa como guía turístico
    virtual para Cuba. El sistema utiliza:
    
    - 🤖 Inteligencia Artificial
    - 📚 Base de conocimientos local
    - 💬 Procesamiento de lenguaje natural
    
    Para probar el sistema, simplemente escribe una pregunta en el chat sobre:
    - Lugares turísticos
    - Historia y cultura
    - Recomendaciones de viaje
    - Actividades y atracciones
    """)
    
    # Botón para limpiar el historial
    if st.button("Limpiar Historial"):
        st.session_state.messages = []
        st.rerun()
