# Guía Turístico Virtual - Fase 2

Sistema multiagente que actúa como guía turístico virtual para Cuba, especializado en museos y excursiones.

## Funcionalidades

- 💬 Chat interactivo con IA
- 🏛️ Base de datos especializada en museos y excursiones
- 🔍 Búsqueda semántica avanzada
- 📊 Procesamiento de datos estructurados
- 🌐 Múltiples fuentes de datos oficiales
- 📱 Interfaz responsive

## Dominio del Sistema

El sistema se especializa en dos áreas principales:

### 🏛️ Museos
- Información detallada
- Colecciones
- Horarios
- Precios
- Servicios
- Accesibilidad

### 🚶 Excursiones
- Descripción detallada
- Duración
- Nivel de dificultad
- Servicios incluidos
- Puntos de encuentro
- Requisitos

## Requisitos

- Python 3.8+
- Fireworks AI API key
- 2GB+ de espacio en disco (para embeddings)

## Instalación

1. Clonar el repositorio
2. Instalar dependencias:
```bash
pip install -r requirements.txt
```
3. Copiar `.env.example` a `.env` y configurar:
   - FIREWORKS_API_KEY
   - Otras configuraciones opcionales

## Estructura del Proyecto

```
app/
├── agent.py          # Agente principal
├── llm.py           # Interfaz con modelo de lenguaje
├── models.py        # Modelos de datos
├── knowledge_base.py # Base de conocimientos
└── data_managers/
    ├── crawler.py    # Recolección de datos
    └── vector_store.py # Almacenamiento vectorial

data/               # Datos procesados
├── raw/           # Datos sin procesar
└── processed/     # Datos estructurados

streamlit_app.py   # Interfaz de usuario
```

## Fuentes de Datos

- www.cubatravel.cu (Oficial)
- www.museoscuba.org
- www.ecured.cu
- www.artcubanacional.cult.cu
- www.cnpc.cult.cu

## Ejecutar la Aplicación

```bash
streamlit run streamlit_app.py
```

## Uso del Crawler

Para actualizar la base de datos:

```bash
python -m app.data_managers.crawler
```

## Estructura de Datos

### Museo
```json
{
  "id": "museum_123",
  "name": "Nombre del Museo",
  "type": "museum",
  "description": "Descripción detallada",
  "location": "Dirección",
  "schedule": {
    "type": "regular",
    "days": ["Lun", "Mar", "Mie", "Jue", "Vie"],
    "hours": [{"start": "09:00", "end": "17:00"}]
  },
  "price": {
    "type": "fixed",
    "amount": 5.0,
    "currency": "CUP"
  }
}
```

### Excursión
```json
{
  "id": "excursion_456",
  "name": "Nombre de la Excursión",
  "type": "excursion",
  "description": "Descripción detallada",
  "duration": {
    "type": "fixed",
    "minutes": 180
  },
  "difficulty_level": "medium",
  "price": {
    "type": "fixed",
    "amount": 25.0,
    "currency": "USD"
  }
}
```
