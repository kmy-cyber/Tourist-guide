from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import re

# Tipos de consultas que el sistema puede identificar
QUERY_TYPES = {
    'CLIMA': 'clima',
    'MUSEO': 'museo',
    'EXCURSION': 'excursion',
    'TRANSPORTE': 'transporte',
    'ALOJAMIENTO': 'alojamiento',
    'RESTAURANTE': 'restaurante',
    'EVENTO': 'evento',
    'GENERAL': 'general'
}

class ConsultaInfo:
    """Clase para almacenar información extraída de una consulta"""
    def __init__(self):
        self.tipo: str = QUERY_TYPES['GENERAL']
        self.ciudad: Optional[str] = None
        self.fecha: Optional[datetime] = None
        self.categoria: Optional[str] = None
        self.restricciones: List[str] = []
        self.preferencias: Dict[str, str] = {}

def es_consulta_clima(texto: str) -> bool:
    """Detecta si la consulta del usuario es sobre el clima o el tiempo atmosférico."""
    palabras_clave = [
        "clima", "tiempo", "temperatura", "lluvia", "pronóstico", "tormenta", 
        "hace calor", "hace frío", "va a llover", "cómo está el clima", 
        "cómo estará el clima", "cómo está el tiempo", "cómo estará el tiempo",
        "soleado", "nublado", "humedad"
    ]
    texto_lower = texto.lower()
    return any(palabra in texto_lower for palabra in palabras_clave)

def extraer_ciudad(texto: str, lista_ciudades: list) -> str | None:
    """Extrae el nombre de la ciudad mencionada en el texto."""
    texto_lower = texto.lower()
    for ciudad in lista_ciudades:
        if ciudad.lower() in texto_lower:
            return ciudad
    return None

def extraer_fecha(texto: str) -> Optional[datetime]:
    """Extrae referencias temporales del texto."""
    # Primero intentar fechas relativas
    fecha = _procesar_fecha_relativa(texto)
    if fecha:
        return fecha
    
    # Si no hay fecha relativa, buscar formato específico
    return _procesar_fecha_formato(texto)

def _procesar_fecha_relativa(texto: str) -> Optional[datetime]:
    """Procesa fechas relativas como 'mañana', 'próxima semana', etc."""
    texto_lower = texto.lower()
    hoy = datetime.now()
    
    if "mañana" in texto_lower:
        return hoy + timedelta(days=1)
    if "pasado mañana" in texto_lower:
        return hoy + timedelta(days=2)
    if "próxima semana" in texto_lower or "semana que viene" in texto_lower:
        return hoy + timedelta(weeks=1)
    if "próximo mes" in texto_lower or "mes que viene" in texto_lower:
        if hoy.month == 12:
            return datetime(hoy.year + 1, 1, 1)
        return datetime(hoy.year, hoy.month + 1, 1)
    return None

def _procesar_fecha_formato(texto: str) -> Optional[datetime]:
    """Procesa fechas en formato dd/mm/yyyy o dd-mm-yyyy."""
    fecha_pattern = r'(\d{1,2})[-/](\d{1,2})(?:[-/](\d{2,4}))?'
    matches = re.findall(fecha_pattern, texto)
    
    if not matches:
        return None
        
    dia, mes, anio = matches[0]
    anio = int(anio) if anio else datetime.now().year
    if len(str(anio)) == 2:
        anio = 2000 + int(anio)
    
    try:
        return datetime(anio, int(mes), int(dia))
    except ValueError:
        return None

def identificar_tipo_consulta(texto: str) -> str:
    """Identifica el tipo principal de la consulta."""
    texto_lower = texto.lower()
    
    if es_consulta_clima(texto_lower):
        return QUERY_TYPES['CLIMA']
    
    # Patrones para museos
    if any(palabra in texto_lower for palabra in [
        "museo", "exhibición", "exposición", "galería", "arte", 
        "colección", "muestra", "obra"
    ]):
        return QUERY_TYPES['MUSEO']
    
    # Patrones para excursiones
    if any(palabra in texto_lower for palabra in [
        "excursión", "tour", "visita", "guía", "recorrido", "paseo",
        "caminata", "ruta", "senderismo", "aventura"
    ]):
        return QUERY_TYPES['EXCURSION']
    
    # Patrones para transporte
    if any(palabra in texto_lower for palabra in [
        "transporte", "bus", "taxi", "cómo llegar", "viaje", 
        "traslado", "aeropuerto", "terminal"
    ]):
        return QUERY_TYPES['TRANSPORTE']
    
    # Patrones para alojamiento
    if any(palabra in texto_lower for palabra in [
        "hotel", "hostal", "alojamiento", "habitación", "reserva",
        "dormir", "hospedaje", "casa particular"
    ]):
        return QUERY_TYPES['ALOJAMIENTO']
    
    # Patrones para restaurantes
    if any(palabra in texto_lower for palabra in [
        "restaurante", "comida", "cena", "almuerzo", "desayuno",
        "bar", "café", "donde comer", "gastronomía"
    ]):
        return QUERY_TYPES['RESTAURANTE']
    
    # Patrones para eventos
    if any(palabra in texto_lower for palabra in [
        "evento", "festival", "concierto", "show", "espectáculo",
        "función", "teatro", "música", "baile", "carnaval"
    ]):
        return QUERY_TYPES['EVENTO']
    
    return QUERY_TYPES['GENERAL']

def analizar_consulta(texto: str, lista_ciudades: List[str]) -> ConsultaInfo:
    """
    Analiza una consulta de usuario y extrae toda la información relevante.
    
    Args:
        texto (str): El texto de la consulta del usuario
        lista_ciudades (List[str]): Lista de ciudades válidas
        
    Returns:
        ConsultaInfo: Objeto con toda la información extraída de la consulta
    """
    info = ConsultaInfo()
    
    # Identificar el tipo principal de consulta
    info.tipo = identificar_tipo_consulta(texto)
    
    # Extraer ciudad si se menciona
    info.ciudad = extraer_ciudad(texto, lista_ciudades)
    
    # Extraer fecha si se menciona
    info.fecha = extraer_fecha(texto)
    
    # Identificar restricciones
    restricciones = []
    texto_lower = texto.lower()
    
    # Restricciones de accesibilidad
    if any(palabra in texto_lower for palabra in ["silla de ruedas", "discapacidad", "accesible"]):
        restricciones.append("accesibilidad")
    
    # Restricciones de horario
    if any(palabra in texto_lower for palabra in ["noche", "nocturno", "tarde", "mañana"]):
        restricciones.append("horario")
    
    # Restricciones de precio
    if any(palabra in texto_lower for palabra in ["barato", "económico", "precio", "costo", "gratis"]):
        restricciones.append("precio")
    
    # Restricciones de grupo
    if any(palabra in texto_lower for palabra in ["niños", "familia", "grupo grande", "pareja"]):
        restricciones.append("grupo")
    
    info.restricciones = restricciones
    
    return info
