"""Gemini API による会話生成"""
import re
from collections.abc import AsyncIterator
from datetime import datetime

from google import genai
from google.genai import types

# この文字で区切って 1 文ずつ TTS に渡す
SENTENCE_END = re.compile(r'(.+?[。！？!?♪]+)', re.S)
WEEKDAYS = '月火水木金土日'


class Chat:
    def __init__(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        max_history: int = 20,
        thinking_level: str = 'minimal',
        timeout_sec: float = 10,
        max_retries: int = 3,
        google_search: bool = False,
        location: str = '',
    ) -> None:
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout_sec * 1000),  # ミリ秒
                retry_options=types.HttpRetryOptions(attempts=max_retries),
            ),
        )
        self.model = model
        self.max_history = max_history
        self.system_prompt = system_prompt
        self.location = location
        self.thinking_config = types.ThinkingConfig(thinking_level=thinking_level.upper())
        self.tools = [types.Tool(google_search=types.GoogleSearch())] if google_search else None

    def _config(self) -> types.GenerateContentConfig:
        """日時は毎回変わるので、リクエストごとにシステムプロンプトへ埋め込む"""
        now = datetime.now()
        context = f"\n\n【現在日時】{now:%Y年%m月%d日}（{WEEKDAYS[now.weekday()]}）{now:%H:%M}"
        if self.location:
            context += f"\n【ユーザーの住んでいる地域】{self.location}（天気などで場所の指定がないときはここを使う）"
        return types.GenerateContentConfig(
            system_instruction=self.system_prompt + context,
            thinking_config=self.thinking_config,
            tools=self.tools,
        )

    def _build_contents(self, user_text: str, history: list[dict]) -> list[dict]:
        contents = [
            {"role": msg["role"], "parts": [{"text": msg["content"]}]}
            for msg in history[-self.max_history:]
        ]
        contents.append({"role": "user", "parts": [{"text": user_text}]})
        return contents

    async def get_response(self, user_text: str, history: list[dict]) -> str:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=self._build_contents(user_text, history),
            config=self._config(),
        )
        return response.text.strip()

    async def stream_sentences(self, user_text: str, history: list[dict]) -> AsyncIterator[str]:
        """応答をストリーミングで受け取り、1 文できるごとに yield する"""
        buf = ''
        stream = await self.client.aio.models.generate_content_stream(
            model=self.model,
            contents=self._build_contents(user_text, history),
            config=self._config(),
        )
        async for chunk in stream:
            buf += chunk.text or ''
            while (m := SENTENCE_END.match(buf)):
                sentence = m.group(1).strip()
                buf = buf[m.end():]
                if sentence:
                    yield sentence
        if buf.strip():
            yield buf.strip()
