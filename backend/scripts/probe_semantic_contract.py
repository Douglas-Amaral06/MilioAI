import asyncio,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from app.core.config import get_settings
from app.llm.ollama import Ollama
async def run():
 s=get_settings()
 async with httpx.AsyncClient(base_url=s.ollama_url,timeout=60) as c:
  model=Ollama(c,s)
  for q in ['salve mano meu vt n caiu','mn faltei no trampo tenho atestadu','opz']:
   print(q,await model.interpret(q,[],{}),flush=True)
asyncio.run(run())
