import asyncio
import json

import httpx

from app.agents.rh_frequency import prompt
from app.core.config import get_settings


async def main():
    settings = get_settings()
    chunks = [
        {
            "id": "1be38623-ae01-4f1b-bd02-a43bbd8c0100",
            "excerpt": "Material fictício de teste. O prazo fictício para envio de atestado é de 3 dias úteis após o retorno.",
            "is_test": True,
        }
    ]
    async with httpx.AsyncClient(
        base_url=settings.ollama_url, timeout=120, trust_env=False
    ) as client:
        async with client.stream(
            "POST",
            "/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": prompt("Qual o prazo fictício para atestado? /no_think", [], chunks),
                "stream": True,
                "think": settings.ollama_think,
                "options": {
                    "num_predict": settings.generation_limit,
                    "num_ctx": 4096,
                    "temperature": 0,
                },
            },
        ) as response:
            print("status", response.status_code)
            answer = ""
            async for line in response.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if data.get("error"):
                    print("provider error", data["error"])
                answer += data.get("message", {}).get("content", "")
                if data.get("done"):
                    print("done", data.get("done_reason"), "tokens", data.get("eval_count"))
            print("answer", answer)


asyncio.run(main())
