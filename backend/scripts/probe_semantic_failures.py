import asyncio,sys,time,json,logging
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from app.core.config import get_settings
from app.llm.ollama import Ollama
from app.support.generation import verbalize
from app.support.operational import CONFIG
class Reason(logging.Handler):
 def emit(self,record):
  if hasattr(record,'reason'):print('REJECTED',record.reason,flush=True)
logging.getLogger('milioai').setLevel(logging.INFO);logging.getLogger('milioai').addHandler(Reason())
class Probe(Ollama):
 async def _structured(self,*args,**kwargs):
  result=await super()._structured(*args,**kwargs)
  print('RAW',json.dumps(result,ensure_ascii=False),'USAGE',self.last_structured_usage,flush=True)
  return result
async def main():
 s=get_settings()
 async with httpx.AsyncClient(base_url=s.ollama_url,timeout=60) as c:
  m=Probe(c,s)
  for q in ['faltei no curso e tenho atestadu','faltei no curso, como marco na folha?']:
   print('INTERPRETED',await m.interpret(q,[],{}),flush=True)
  factual=f'Canal autorizado: [Conecta Jovem]({CONFIG["portal_url"]}). Finalidade: consultar seu calendário educacional.'
  print(await verbalize(m,'educational_agent','Onde vejo o calendário?',[],factual,time.monotonic()+60),flush=True)
asyncio.run(main())
