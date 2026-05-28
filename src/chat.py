"""Gemini API による会話生成"""
import asyncio

from google import genai
from google.genai import types


class Chat:
    def __init__(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        max_history: int = 20,
    ) -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.system_prompt = system_prompt
        self.max_history = max_history

    async def get_response(self, user_text: str, history: list[dict]) -> str:
        return await asyncio.get_running_loop().run_in_executor(
            None, self._get_response_sync, user_text, history
        )

    def _get_response_sync(self, user_text: str, history: list[dict]) -> str:
        contents = [
            {"role": msg["role"], "parts": [{"text": msg["content"]}]}
            for msg in history[-self.max_history:]
        ]
        contents.append({"role": "user", "parts": [{"text": user_text}]})

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt,
            ),
        )
        return response.text.strip()
