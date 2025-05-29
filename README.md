# Guía Turístico Virtual - Sistema Inteligente de Recomendación

Un sistema avanzado de asistencia turística que combina inteligencia artificial, procesamiento de lenguaje natural y búsqueda semántica para proporcionar información precisa y contextual sobre destinos turísticos en Cuba, con especialización en museos y excursiones.

## Descripción General

Este proyecto implementa un asistente turístico virtual que utiliza tecnologías de última generación para ofrecer:

- 🤖 Procesamiento de lenguaje natural mediante Fireworks AI (Llama v3)
- 🔍 Búsqueda semántica vectorial para recuperación precisa de información
- 🗃️ Base de conocimientos especializada y actualizable
- 🌐 Interfaz web interactiva construida con Streamlit
- 📊 Sistema de confianza y validación de fuentes
- 🔄 Actualización automática de datos mediante web crawling

## Funcionalidades

- 💬 Chat interactivo con IA
- 🏛️ Base de datos especializada en museos y excursiones
- 🔍 Búsqueda semántica avanzada
- 📊 Procesamiento de datos estructurados
- 🌐 Múltiples fuentes de datos oficiales
- 📱 Interfaz responsive

## Arquitectura del Sistema

### 🧠 Componentes Principales

1. **Agente Virtual (TourGuideAgent)**
   - Motor principal de procesamiento de consultas
   - Gestión de contexto y confianza
   - Integración con LLM y base de conocimientos

2. **Modelo de Lenguaje (LLM)**
   - Basado en Fireworks AI (Llama v3)
   - Procesamiento contextual de consultas
   - Generación de respuestas naturales

3. **Base de Conocimientos (TourismKB)**
   - Almacenamiento vectorial de información
   - Búsqueda semántica avanzada
   - Sistema de actualización de datos

4. **Interfaz Web (Streamlit)**
   - Chat interactivo
   - Indicadores de confianza
   - Gestión de historial
   - Panel de control administrativo

### 🎯 Dominio Especializado

#### 🏛️ Museos
- **Categorías**: Arte, Historia, Ciencia, Cultura
- **Datos Estructurados**:
  - Información detallada y validada
  - Colecciones permanentes y temporales
  - Horarios y tarifas actualizados
  - Servicios y facilidades
  - Accesibilidad y ubicación
  - Metadatos de confiabilidad

#### 🚶 Excursiones
- **Categorías**: Urbanas, Naturaleza, Culturales
- **Datos Estructurados**:
  - Descripción detallada y verificada
  - Duración y nivel de dificultad
  - Servicios incluidos
  - Puntos de encuentro
  - Requisitos y recomendaciones
  - Indicadores de calidad de datos

## Arquitectura de Datos

### Fuentes de Datos
El sistema recolecta información de fuentes oficiales y confiables:

- 🏛️ **Museos**:
  - www.museoscuba.org (Oficial - Alta confiabilidad)
  - www.artcubanacional.cult.cu (Oficial - Alta confiabilidad)
  - www.ecured.cu (Enciclopedia - Media confiabilidad)

- 🚶 **Excursiones**:
  - www.cubatravel.cu (Oficial - Alta confiabilidad)
  - www.cnpc.cult.cu (Oficial - Alta confiabilidad)

### 🔄 Flujo de Datos

1. **Recolección (Crawler)**
   - Crawler especializado por tipo de contenido
   - Sistema de registro de actualizaciones
   - Gestión de fuentes por confiabilidad
   - Almacenamiento raw con timestamping

2. **Procesamiento (DataIngestionCoordinator)**
   - Validación de campos obligatorios
   - Normalización de formatos
   - Enriquecimiento de metadatos
   - Control de calidad de datos

3. **Vectorización (VectorStore)**
   - Generación de embeddings
   - Indexación semántica
   - Optimización de búsqueda
   - Gestión de versiones

4. **Recuperación (KnowledgeBase)**
   - Búsqueda contextual
   - Filtrado por relevancia
   - Scoring de confiabilidad
   - Caché de consultas frecuentes

### 📁 Estructura de Almacenamiento

```plaintext
data/
├── raw/              # Datos crudos del crawler
│   └── YYYYMMDD/     # Organizados por fecha
├── vectors/          # Índices vectoriales
│   ├── museums/      # Vectores de museos
│   ├── excursions/   # Vectores de excursiones
│   └── destinations/ # Vectores de destinos
└── cache/           # Caché de consultas frecuentes
```

## ⚙️ Configuración y Despliegue

### Requisitos del Sistema

- **Software**
  - Python 3.8+
  - pip (gestor de paquetes)
  - git (control de versiones)

- **Hardware Recomendado**
  - CPU: 2+ cores
  - RAM: 4GB+ 
  - Almacenamiento: 2GB+ (principalmente para embeddings)

- **Credenciales**
  - Fireworks AI API key (modelo LLaMA)

### Instalación

1. **Clonar el Repositorio**
   ```bash
   git clone <repository-url>
   cd sim-ia-sri
   ```

2. **Crear y Activar Entorno Virtual**
   ```bash
   python -m venv venv
   # En Windows
   .\venv\Scripts\activate
   # En Unix
   source venv/bin/activate
   ```

3. **Instalar Dependencias**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar Variables de Entorno**
   ```bash
   cp .env.example .env
   # Editar .env y agregar:
   # FIREWORKS_API_KEY=tu-api-key
   # Otras configuraciones opcionales
   ```

### Verificación de Instalación

```bash
python -c "from app.agent import TourGuideAgent; print('✅ Instalación correcta')"
```

## 📂 Estructura del Proyecto

```
app/
├── agent.py           # Agente principal de procesamiento
│   ├── TourGuideAgent # Clase principal del sistema
│   ├── _build_context # Generador de contexto para LLM 
│   └── _calculate_confidence # Sistema de confiabilidad
│
├── llm.py            # Interfaz con modelo de lenguaje
│   ├── LLM           # Wrapper para Fireworks AI
│   └── generate      # Generación de respuestas
│
├── knowledge_base.py  # Gestión de conocimiento
│   ├── TourismKB     # Clase principal de conocimiento
│   ├── search        # Motor de búsqueda semántica
│   └── refresh_data  # Actualización de datos
│
├── models.py         # Modelos de datos
│   ├── UserQuery     # Estructura de consultas
│   └── TourGuideResponse # Formato de respuestas
│
└── data_managers/    # Gestión de datos
    ├── crawler.py     # Web scraping especializado
    ├── data_ingestion.py # Coordinador de ingesta
    └── vector_store.py  # Almacén vectorial

data/                # Repositorio de datos
├── raw/             # Datos crudos del crawler
├── vectors/         # Índices vectoriales
│   ├── museums/     # Vectores de museos
│   ├── excursions/  # Vectores de excursiones
│   └── destinations/ # Vectores de destinos
└── cache/          # Caché de consultas

streamlit_app.py    # Interfaz web interactiva
```

## Ejecutar la Aplicación

```bash
streamlit run streamlit_app.py
```

## 🚀 Uso y Operación

### Iniciar la Aplicación

```bash
streamlit run streamlit_app.py
```

La interfaz web estará disponible en `http://localhost:8501`

### Funciones Administrativas

1. **Actualización de Datos**
   ```bash
   # Actualización manual del crawler
   python -m app.data_managers.crawler
   
   # O usar el botón "Actualizar Base de Datos" en la interfaz
   ```

2. **Monitoreo**
   - Logs en `app.log`
   - Panel de confianza en la interfaz
   - Indicadores de fuentes

### Interacción con el Sistema

1. **Consultas Efectivas**
   - Ser específico con ubicaciones y tipos
   - Incluir preferencias de horario/precio
   - Especificar tipo de actividad

2. **Interpretación de Respuestas**
   - Indicador de confianza (0-100%)
   - Referencias a fuentes
   - Sugerencias relacionadas

## 📊 Modelos de Datos

### Museos
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

### Excursiones
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
  },
  "source_info": {
    "type": "official",
    "url": "https://www.cubatravel.cu",
    "reliability": "high",
    "last_updated": "2025-06-15"
  },
  "metadata": {
    "category": "cultural",
    "tags": ["historia", "arquitectura"],
    "accessibility": "medium",
    "languages": ["es", "en"]
  }
}
```

## 🔍 Características Técnicas

### Sistema de Confiabilidad

El sistema implementa un algoritmo de confiabilidad basado en:
- Calidad de las fuentes
- Frecuencia de actualización
- Completitud de datos
- Consistencia de información

### Búsqueda Semántica

Utiliza embeddings vectoriales para:
- Entender el contexto de las consultas
- Relacionar información similar
- Priorizar resultados relevantes
- Mantener consistencia temática

### Gestión de Sesiones

- Historial de conversación
- Contexto persistente
- Cache de consultas frecuentes
- Estado de actualizaciones

## 🤝 Contribución

1. Fork el repositorio
2. Cree una rama para su feature (`git checkout -b feature/AmazingFeature`)
3. Commit sus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abra un Pull Request

## 📝 Licencia

Este proyecto está licenciado bajo la Licencia MIT - ver el archivo `LICENSE` para detalles.

## 📧 Contacto

Para preguntas y soporte, por favor abra un issue en el repositorio.
