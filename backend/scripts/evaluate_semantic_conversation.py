"""Bounded live semantic checks. No writes, migrations, reindexing or service restarts."""
import asyncio
import json
import sys
import time
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings
from app.llm.ollama import Ollama
from app.orchestration.graph import build_graph
from app.agents.policies import owner

CASES=[
    ("opa","social",None),("opz","social",None),("eae mn","social",None),("fala cmg","social",None),
    ("salve mano meu vt n caiu","institutional","service_agent"),
    ("mn faltei no trampo tenho atestadu","institutional","frequency_agent"),
    ("faltei no curso e tenho atestadu","institutional","educational_agent"),
    ("fonha ponto onde gero?","institutional","frequency_agent"),
    ("preciso mandar atestado","clarify",None),
    ("faltei no curso, como marco na folha?","institutional","frequency_agent"),
    ("xqz qwr zzz","clarify",None),
    ("num fui pro batente hj e trouxe o papel do dotô","institutional","frequency_agent"),
    ("me perdi aqui, queria saber os dias q tem capacitação","institutional","educational_agent"),
]
async def main():
    settings=get_settings()
    results=[]; cache={}
    async with httpx.AsyncClient(base_url=settings.ollama_url,timeout=settings.ollama_timeout,trust_env=False) as client:
        model=Ollama(client,settings)
        for question,kind,agent in CASES:
            started=time.monotonic()
            value=await model.interpret(question,[],{})
            cache[question]=value
            actual_agent=owner(value["requests"][0]["topic"]) if value and value["requests"] else None
            row={"question":question,"expected_kind":kind,"expected_agent":agent,"result":value,"pass":bool(value and value["kind"]==kind and actual_agent==agent and (question not in {"opa","opz","eae mn"} or value["social"]=="greeting") and (question!="fala cmg" or value["social"]=="help")),"latency_ms":round((time.monotonic()-started)*1000)}
            results.append(row)
            Path("semantic-live.json").write_text(json.dumps({"model":settings.ollama_model,"classification":results},ensure_ascii=False,indent=2),encoding="utf-8")
            print(json.dumps(row,ensure_ascii=False),flush=True)
        class CachedOllama(Ollama):
            async def interpret(self,question,history,context):
                if question in cache and not history:return cache[question]
                return await super().interpret(question,history,context)
        live=CachedOllama(client,settings)
        graph=build_graph(None,live,settings)
        end_to_end=[]
        # No RAG/database calls needed for social or operational questions.
        for questions in [("opz",),("fala cmg",),("fonha ponto onde gero?",),("onde eu vejo os dias do curso?","e onde vejo isso msm?","ja fui la mas n achei")]:
            history=[]; flow={}
            for question in questions:
                started=time.monotonic()
                try:
                    result=await graph.ainvoke({"question":question,"history":history,"support_state":flow,"scopes":("education:contacts",),"chunks":[],"sources":[],"contacts":[]})
                    row={"question":question,"answer":result["answer"],"outcome":result.get("outcome"),"agent":result.get("agent"),"intent":result.get("semantic_intent"),"semantic_mode":result.get("semantic_mode"),"generation_mode":result.get("generation_mode"),"latency_ms":round((time.monotonic()-started)*1000)}
                    flow=result.get("support_state",{})
                    history.extend([{"role":"user","content":question,"topic_id":result.get("topic_id")},{"role":"assistant","content":result["answer"],"topic_id":result.get("topic_id")}])
                except Exception as error:
                    row={"question":question,"error":type(error).__name__,"latency_ms":round((time.monotonic()-started)*1000)}
                end_to_end.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
        Path("semantic-live.json").write_text(json.dumps({"model":settings.ollama_model,"classification":results,"end_to_end":end_to_end},ensure_ascii=False,indent=2),encoding="utf-8")
asyncio.run(main())
