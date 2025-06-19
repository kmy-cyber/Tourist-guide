import os
import json
from openai import OpenAI
from dotenv import load_dotenv
import httpx

load_dotenv()

class LLMError(Exception):
    """Excepción específica para errores del modelo de lenguaje."""
    pass

class LLM:
    def __init__(self):
        self.api_key = os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY no está configurada en las variables de entorno")
            
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.mistral.ai/v1",
            timeout=httpx.Timeout(30.0)
        )
        # Modelos disponibles en Mistral AI
        self.model = "mistral-small"  # Alternativas: mistral-tiny, mistral-small, mistral-medium

    async def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        """
        Genera una respuesta utilizando la API de Mistral AI.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            # Crear parámetros de la solicitud
            params = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 1000,
                "temperature": 0.7
            }
            
            completion = self.client.chat.completions.create(**params)

            response_text = completion.choices[0].message.content.strip()
            
            # Intentar parsear como JSON solo si parece ser JSON
            if response_text.startswith(('{', '[')) and response_text.endswith(('}', ']')):
                try:
                    response_data = json.loads(response_text)
                    if isinstance(response_data, list) and len(response_data) > 0:
                        return response_data[-1].get("content", response_text)
                    elif isinstance(response_data, dict):
                        return response_data.get("content", response_text)
                except json.JSONDecodeError:
                    pass
            return response_text
            
        except Exception as e:
            error_msg = f"Error generating response: {str(e)}"
            
            # Manejar errores específicos de la API
            if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                status_code = e.response.status_code
                if status_code == 403:
                    error_msg = "Acceso no autorizado. Verifica tu API key de Mistral AI"
                elif status_code == 429:
                    error_msg = "Límite de tasa excedido. Espera antes de hacer más solicitudes"
                elif status_code == 402:
                    error_msg = "Límite de crédito excedido. Verifica tu plan de pago"
                elif status_code == 422:
                    # Manejar específicamente el error de validación
                    try:
                        error_details = e.response.json()
                        error_msg = f"Error de validación en la solicitud: {error_details.get('message', 'Detalles no disponibles')}"
                    except:
                        error_msg = "Error de validación en los parámetros de la solicitud"
            
            raise LLMError(error_msg) from e
