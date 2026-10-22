import asyncio
import logging
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings
from app.llm.ollama import Ollama
from app.support.generation import verbalize
from app.support.operational import CONFIG

logging.basicConfig(format="%(message)s %(reason)s")


class Probe(Ollama):
    async def chat(self, messages):
        candidate = ""
        async for part in super().chat(messages):
            candidate += part
            yield part
        print("CANDIDATE:", candidate, flush=True)


async def run():
    s = get_settings()
    async with httpx.AsyncClient(base_url=s.ollama_url, timeout=s.ollama_timeout) as c:
        print(
            await verbalize(
                Probe(c, s),
                "frequency_agent",
                "Onde gero minha Folha Ponto?",
                [],
                f"Você pode acessar o [Conecta Jovem]({CONFIG['portal_url']}) para gerar ou obter sua Folha Ponto.",
                time.monotonic() + 60,
            )
        )


asyncio.run(run())
