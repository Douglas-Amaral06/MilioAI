import asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from app.core.config import get_settings
from app.support.semantics import Interpretation
async def main():
 s=get_settings()
 async with httpx.AsyncClient(base_url=s.ollama_url,timeout=60) as c:
  for schema in [Interpretation.model_json_schema(),{'type':'object','properties':{'kind':{'type':'string','enum':['social','institutional','clarify']}},'required':['kind'],'additionalProperties':False}]:
   payload={'model':s.ollama_model,'stream':False,'think':False,'format':schema,'messages':[{'role':'system','content':'Classifique o pedido em português. social = só cumprimento ou despedida, institutional = dúvida sobre curso, trabalho, benefícios ou folha ponto; clarify = sem intenção compreensível. Priorize o pedido institucional quando houver saudação junto. Retorne JSON do schema. /no_think'},{'role':'user','content':'salve mano meu vt n caiu'}],'options':{'temperature':0,'num_predict':400,'num_ctx':4096}}
   r=await c.post('/api/chat',json=payload);r.raise_for_status();v=r.json();print(json.dumps({k:v.get(k) for k in ['message','prompt_eval_count','eval_count','done_reason']},ensure_ascii=False),flush=True)
asyncio.run(main())
