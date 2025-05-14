import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLM:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("FIREWORKS_API_KEY"),
            base_url="https://api.fireworks.ai/inference/v1"
        )
        self.model = "accounts/fireworks/models/llama-v3p1-8b-instruct"

    async def generate(self, prompt: str, context: str = "") -> str:
        messages = [
            {"role": "system", "content": "Eres un guía turístico experto en Cuba. " + context},
            {"role": "user", "content": prompt}
        ]

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=1000,
            temperature=0.7,
            stop=None
        )

        try:
            response_text = completion.choices[0].message.content.strip()
            response_data = json.loads(response_text)
            if isinstance(response_data, list) and len(response_data) > 0:
                return response_data[-1].get("content", response_text)
            return response_text
        except json.JSONDecodeError:
            return response_text
