import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMError(Exception):
    """Excepción específica para errores del modelo de lenguaje."""
    pass

class LLM:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("FIREWORKS_API_KEY"),
            base_url="https://api.fireworks.ai/inference/v1"
        )
        self.model = "accounts/fireworks/models/llama-v3p1-8b-instruct"

    async def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        """
        Genera una respuesta utilizando el modelo de lenguaje.
        
        Args:
            system_prompt: El prompt del sistema que define el comportamiento
            user_prompt: La pregunta o solicitud del usuario
            
        Returns:
            str: La respuesta generada por el modelo
            
        Raises:
            LLMError: Si ocurre un error durante la generación de la respuesta
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1000,
                temperature=0.7,
                stop=None
            )

            response_text = completion.choices[0].message.content.strip()
            # Intentar parsear como JSON solo si parece ser JSON
            if response_text.startswith('[') and response_text.endswith(']'):
                try:
                    response_data = json.loads(response_text)
                    if isinstance(response_data, list) and len(response_data) > 0:
                        return response_data[-1].get("content", response_text)
                except json.JSONDecodeError:
                    pass
            return response_text
            
        except Exception as e:
            raise LLMError(f"Error generating response: {str(e)}")
