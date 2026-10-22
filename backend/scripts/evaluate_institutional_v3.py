"""Bounded, versioned real local evaluation. Never edits historical observations.

Uses the caller's existing credentials/scopes. Requires an explicitly isolated
database name, cloned by the operator; migrations apply only to that database.
"""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import dotenv_values
from sqlalchemy.engine import URL

from app.core.config import Settings
from app.main import create_app
from app.support.grounding import deterministic_grounding

FP07 = [
    "Faltei no curso, coloco FALTA?",
    "Na aula que faltei, escrevo CURSO?",
    "Posso trocar CURSO por FALTA?",
    "Como evito desconto duplicado por falta no curso?",
]
FP13 = [
    "Com quem tiro dúvidas e quando devo procurar ajuda?",
    "Quem me ajuda com a folha ponto?",
    "Qual contato da Frequência?",
    "E com quem falo antes do prazo?",
]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def evaluate(args):
    args.output.mkdir(parents=True, exist_ok=False)
    original = Settings(_env_file=args.env_file)
    if original.app_env != "development" or original.auth_mode != "development":
        raise ValueError("This runner requires existing local development authorization")
    if not args.database.startswith("milioai_sprint2_"):
        raise ValueError("An isolated Sprint 2 database is required")
    local_env = dotenv_values(args.env_file)
    database = URL.create(
        "postgresql+psycopg",
        username=local_env.get("POSTGRES_USER", "milioai"),
        password=local_env["POSTGRES_PASSWORD"],
        host="127.0.0.1",
        port=5433,
        database=args.database,
    )
    changes = {
        "database_url": database.render_as_string(hide_password=False),
        "ollama_url": "http://127.0.0.1:11434",
        "storage_path": args.output / "private",
    }
    settings = original.model_copy(update=changes)
    env = dict(
        os.environ, **{k: v for k, v in dotenv_values(args.env_file).items() if v is not None}
    )
    env.update(
        DATABASE_URL=changes["database_url"],
        OLLAMA_URL=changes["ollama_url"],
        STORAGE_PATH=str(changes["storage_path"]),
    )
    with (args.output / "migration.log").open("w", encoding="utf-8") as log:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
    app = create_app(settings)
    start = time.monotonic()
    rows = []
    manifest = {
        "contract": "3.0.0",
        "kind": "real_local_integration",
        "database": args.database,
        "started_at": datetime.now(UTC).isoformat(),
        "max_seconds": args.max_seconds,
        "repeat": args.repeat,
        "model": settings.ollama_model,
        "kb_version": settings.active_kb_version,
        "human_acceptance": None,
        "historical_results_modified": False,
        "files": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path("app").rglob("*"))
            if p.suffix in {".py", ".json"}
        },
    }
    save(args.output / "manifest.json", manifest)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://local-evaluation",
            headers={"Authorization": "Bearer " + settings.dev_auth_token},
            timeout=settings.ollama_timeout,
        ) as client:
            for case, questions in [("FP-07", FP07), ("FP-13", FP13)]:
                for index, question in enumerate(questions):
                    for repeat in range(args.repeat):
                        if time.monotonic() - start >= args.max_seconds:
                            save(
                                args.output / "summary.json",
                                {
                                    "status": "duration_limit",
                                    "observations": rows,
                                    "human_acceptance": None,
                                },
                            )
                            return
                        created = await client.post(
                            "/api/v1/conversations",
                            json={"title": f"Sprint 2 v3 {case} P{index + 1} R{repeat + 1}"},
                        )
                        created.raise_for_status()
                        cid = created.json()["id"]
                        trace = []
                        # Observe real graph updates and custom events without replacing any node.
                        actual_graph = app.state.graph

                        class Observe:
                            def __init__(self, graph, updates):
                                self.graph, self.updates = graph, updates

                            async def astream(self, *a, **kw):
                                async for mode, value in self.graph.astream(*a, **kw):
                                    if mode == "updates":
                                        self.updates.append(value)
                                    yield mode, value

                        app.state.graph = Observe(actual_graph, trace)
                        started = time.monotonic()
                        try:
                            async with asyncio.timeout(
                                min(
                                    settings.ollama_timeout + 5,
                                    args.max_seconds - (time.monotonic() - start),
                                )
                            ):
                                response = await client.post(
                                    f"/api/v1/conversations/{cid}/messages",
                                    json={
                                        "request_id": str(uuid.uuid4()),
                                        "topic_id": "folha_ponto",
                                        "content": question,
                                    },
                                )
                        finally:
                            app.state.graph = actual_graph
                        value = response.json()
                        supported = False
                        documentary = next(
                            (u["validate"] for u in reversed(trace) if "validate" in u), {}
                        )
                        if response.status_code == 201 and value.get("sources"):
                            try:
                                deterministic_grounding(
                                    documentary["answer"], documentary["sources"]
                                )
                                supported = True
                            except ValueError:
                                pass
                        passed = supported and value.get("outcome") == "answered"
                        if case == "FP-07":
                            passed = passed and "manter o preenchimento como CURSO" in value.get(
                                "content", ""
                            )
                        else:
                            contacts = value.get("contacts", [])
                            passed = (
                                passed
                                and "antes do prazo final" in value.get("content", "")
                                and any(c["url"] == "https://wa.me/5511970806028" for c in contacts)
                            )
                        reloaded = await client.get(f"/api/v1/conversations/{cid}/messages")
                        persisted = reloaded.status_code == 200 and any(
                            m.get("id") == value.get("id")
                            and m.get("contacts", []) == value.get("contacts", [])
                            for m in reloaded.json()
                        )
                        row = {
                            "id": f"{case}-P{index + 1}-R{repeat + 1}",
                            "question": question,
                            "http_status": response.status_code,
                            "technical_contract_passed": bool(passed and persisted),
                            "persisted": persisted,
                            "human_acceptance": None,
                            "duration_ms": round((time.monotonic() - started) * 1000),
                            "message": value,
                            "trace": trace,
                        }
                        rows.append(row)
                        save(args.output / (row["id"] + ".json"), row)
                        save(
                            args.output / "summary.json",
                            {
                                "status": "running",
                                "completed": len(rows),
                                "technical_passed": sum(
                                    r["technical_contract_passed"] for r in rows
                                ),
                                "human_acceptance": None,
                            },
                        )
                        print(
                            json.dumps(
                                {
                                    k: row[k]
                                    for k in [
                                        "id",
                                        "http_status",
                                        "technical_contract_passed",
                                        "persisted",
                                        "duration_ms",
                                    ]
                                }
                            ),
                            flush=True,
                        )
    save(
        args.output / "summary.json",
        {
            "status": "complete",
            "completed": len(rows),
            "technical_passed": sum(r["technical_contract_passed"] for r in rows),
            "human_acceptance": None,
            "duration_seconds": round(time.monotonic() - start, 2),
        },
    )


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeat", type=int, choices=[1, 2, 3], default=2)
    parser.add_argument("--max-seconds", type=int, choices=range(60, 1201), default=600)
    asyncio.run(evaluate(parser.parse_args()))
