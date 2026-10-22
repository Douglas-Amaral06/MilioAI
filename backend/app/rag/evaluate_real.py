"""Sequential, resumable evaluation using real auth, message services, graph and providers.

This adapter never reads expected answers while executing a case. The offline
quality package remains a separate consumer of the recorded observations.
"""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy import select

import app.orchestration.graph as graph_module
from app.api.schemas import SendInput
from app.auth.dependencies import Principal
from app.core.config import get_settings
from app.core.log_context import request_id_context
from app.db.models import Conversation, Document, DocumentChunk, User
from app.main import create_app
from app.messages.service import execute, prepare

TRACE = ContextVar("evaluation_trace", default=None)
SAMPLE = ["FP-02", "FP-07", "VT-89", "VT-3854", "NEG-06", "CTX-01", "CTX-08", "AUTH-02"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    """Atomic per-case checkpoints; an interrupted case is replayed in a new conversation."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def inputs(case):
    return {k: case[k] for k in ("test_id", "question", "conversation_context", "run_context")}


def load_quality(folder):
    spec = importlib.util.spec_from_file_location("milio_quality", folder / "quality.py")
    quality = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(quality)
    return quality, quality.load_bundle(folder)


class PolicySettings:
    """Exercise production document filters in isolation, with unchanged dev authentication."""

    app_env = "production"

    def __init__(self, settings):
        self.settings = settings

    def __getattr__(self, name):
        return getattr(self.settings, name)

    def model_copy(self, **kwargs):
        return PolicySettings(self.settings.model_copy(**kwargs))


class CaptureLogs(logging.Handler):
    def emit(self, record):
        trace = TRACE.get()
        if trace is not None and record.name == "milioai":
            trace["logs"].append(
                {
                    "event": record.getMessage(),
                    **{
                        k: getattr(record, k)
                        for k in (
                            "error_type",
                            "coverage",
                            "chunk_count",
                            "repair_attempt",
                            "stage",
                            "domain",
                            "duration_ms",
                            "outcome",
                            "success",
                        )
                        if hasattr(record, k)
                    },
                }
            )


class ObservedGraph:
    def __init__(self, graph):
        self.graph = graph

    async def astream(self, state, **kwargs):
        trace = TRACE.get()
        if trace is not None:
            trace["initial_state"] = state
            trace["final_state"] = dict(state)
        async for mode, value in self.graph.astream(state, **kwargs):
            if trace is not None and mode == "updates":
                for node, update in value.items():
                    if update:
                        trace["updates"].append({"node": node, "state": update})
                        trace["final_state"].update(update)
            yield mode, value


async def inventory(app, bundle):
    records, mapping = [], {}
    aliases = {
        "rh_frequency": "folha-ponto",
        "beneficios.vale_transporte.segunda_via": "vt-segunda-via",
    }
    registry = {d["document_id"]: d for d in bundle["registry"]["documents"]}
    async with app.state.sessions() as session:
        for doc in (await session.scalars(select(Document).order_by(Document.id))).all():
            chunks = (
                await session.scalars(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == doc.id)
                    .order_by(DocumentChunk.chunk_index)
                )
            ).all()
            alias = aliases.get(doc.domain)
            registered = registry.get(alias, {})
            # Alias identity requires exact configured version plus domain and location inventory.
            # It does NOT assert equivalence to the dataset's separately versioned snapshot.
            if doc.is_test or doc.version != registered.get("runtime_kb_version_reference"):
                alias = None
            verified = None
            try:
                blob = app.state.storage.path(doc.storage_key)
                if blob.is_file() and digest(blob) == doc.sha256:
                    verified = doc.sha256
            except Exception:
                pass
            record = {
                "runtime_document_id": str(doc.id),
                "alias": alias,
                "name": doc.name,
                "domain": doc.domain,
                "runtime_version": doc.version,
                "dataset_version": registered.get("source_version"),
                "stored_blob_sha256": doc.sha256,
                "verified_blob_sha256": verified,
                "scope": doc.scope,
                "approved_runtime_flag": doc.approved,
                "status": doc.status,
                "validation_only": doc.validation_only,
                "institutionally_approved": False,
                "mapping_basis": "exact_domain_and_registered_runtime_version_with_full_chunk_inventory"
                if alias
                else "unmapped",
                "snapshot_equivalence": "not_established",
                "chunks": [
                    {
                        "id": str(c.id),
                        "page": c.page,
                        "section": c.section,
                        "benefit_code": c.benefit_code,
                        "sha256": c.sha256,
                        "content": c.content,
                        "attributes": c.attributes,
                    }
                    for c in chunks
                ],
            }
            records.append(record)
            mapping[str(doc.id)] = record
    return records, mapping


def reference(chunk, mapping):
    doc = mapping[chunk["document_id"]]
    return {
        "document_id": doc["alias"] or "unmapped:" + chunk["document_id"],
        "source_version": chunk["version"],
        "section_or_row": chunk.get("section"),
        "page": chunk.get("page"),
        "benefit_code": chunk.get("benefit_code"),
        "chunk_id": chunk["id"],
        "runtime_document_id": chunk["document_id"],
        "document_hash": doc["verified_blob_sha256"],
        "chunk_hash": chunk.get("sha256") or None,
    }


def export_result(raw, mapping):
    final = raw["turns"][-1] if raw.get("turns") else {}
    done = next((e["message"] for e in final.get("events", []) if e["event"] == "done"), None)
    state = final.get("final_state", {})
    calls = final.get("retrieval_calls", [])
    observed = bool(done)
    answer = done["content"] if done else None
    sources = done.get("sources", []) if done else []
    context = {"domain": None, "benefit_code": None}
    if state:
        flow = state.get("support_state", {})
        domain = state.get("domain")
        if state.get("vt_route") or state.get("detected_intent") == "transport_replacement":
            domain = "vale_transporte"
        elif done and done.get("outcome") == "operational":
            domain = "operational"
        context = {
            "domain": {
                "rh_frequency": "folha_ponto",
                "beneficios.vale_transporte.segunda_via": "vale_transporte",
            }.get(domain, domain),
            "benefit_code": flow.get("selected_card_code")
            if flow.get("vt_stage") == "active"
            else None,
        }
    outcome = done.get("outcome") if done else None
    behavior = None
    if done:
        behavior = (
            "clarify"
            if outcome in {"clarify", "card_selection"}
            else "fallback"
            if outcome in {"no_evidence", "out_of_scope"}
            else "answer"
        )
        if "**Ponto para revisão:**" in answer:
            behavior = "surface_conflict"
        if answer.startswith("Seu acesso não permite consultar os contatos educacionais."):
            behavior = "fallback"
    return {
        "test_id": raw["test_id"],
        "retrieval_status": "not_recorded"
        if any("error" in c for c in calls)
        else "observed"
        if final.get("initial_state") or calls
        else "not_recorded",
        "retrieved": [reference(c, mapping) for call in calls for c in call.get("chunks", [])],
        "citation_status": "observed" if observed else "not_recorded",
        "citations": [reference(c, mapping) for c in sources],
        "generation_status": "observed" if observed else "not_recorded",
        "answer": answer,
        "behavior": behavior,
        "context_status": "observed" if state else "not_recorded",
        "context": context,
    }


async def send_turn(app, principal, cid, payload, kind):
    trace = {
        "kind": kind,
        "payload": payload.model_dump(mode="json"),
        "retrieval_calls": [],
        "logs": [],
        "updates": [],
        "events": [],
    }
    token = TRACE.set(trace)
    correlation = request_id_context.set(str(payload.request_id))
    started = time.monotonic()
    try:
        prepared = await prepare(app.state.sessions, principal, cid, payload, app.state.settings)
        async for event in execute(app, principal, cid, payload, prepared):
            trace["events"].append(event)
    except Exception as error:
        trace["error"] = {"type": type(error).__name__, "code": getattr(error, "code", None)}
    finally:
        trace["duration_ms"] = round((time.monotonic() - started) * 1000)
        TRACE.reset(token)
        request_id_context.reset(correlation)
    return trace


async def run_case(app, principal, case, graphs, output):
    started = time.monotonic()
    raw = {
        "test_id": case["test_id"],
        "input": case,
        "started_at": datetime.now().astimezone().isoformat(),
        "effective_scopes": list(principal.scopes),
        "execution_environment": "development",
        "policy_profile": "production_document_filters_in_development"
        if case["run_context"]["environment"] == "corporate"
        else "local_review",
        "turns": [],
    }
    app.state.graph = graphs[case["run_context"]["environment"]]
    async with app.state.sessions() as session:
        conversation = Conversation(user_id=principal.id, title="RAG eval " + case["test_id"])
        session.add(conversation)
        await session.commit()
        cid = conversation.id
    raw["conversation_id"] = str(cid)
    scenario = case.get("scenario_input", {})
    for setup in scenario.get("setup_turns", []):
        raw["turns"].append(
            await send_turn(
                app,
                principal,
                cid,
                SendInput(request_id=uuid.uuid4(), **setup),
                "explicit_scenario_setup",
            )
        )
    for turn in case["conversation_context"]["prior_turns"]:
        if turn["role"] != "user":
            raise ValueError(
                "Assistant fixtures require an explicit separate adapter; never forge generated turns"
            )
        raw["turns"].append(
            await send_turn(
                app,
                principal,
                cid,
                SendInput(request_id=uuid.uuid4(), content=turn["content"]),
                "prior_user_replay",
            )
        )
    selected = case["conversation_context"]["selected_benefit_code"]
    if selected:
        async with app.state.sessions() as session:
            flow = (await session.get(Conversation, cid)).support_state
        if flow.get("selected_card_code") != selected or flow.get("vt_stage") != "active":
            raw["turns"].append(
                await send_turn(
                    app,
                    principal,
                    cid,
                    SendInput(request_id=uuid.uuid4(), action={"kind": "card_change"}),
                    "context_card_menu",
                )
            )
            raw["turns"].append(
                await send_turn(
                    app,
                    principal,
                    cid,
                    SendInput(
                        request_id=uuid.uuid4(),
                        action={"kind": "card_select", "benefit_code": selected},
                    ),
                    "context_card_selection",
                )
            )
    raw["turns"].append(
        await send_turn(
            app,
            principal,
            cid,
            SendInput(
                request_id=uuid.uuid4(), content=case["question"], topic_id=scenario.get("topic_id")
            ),
            "evaluated_question",
        )
    )
    raw["duration_ms"] = round((time.monotonic() - started) * 1000)
    raw["completed_at"] = datetime.now().astimezone().isoformat()
    save(output / "cases" / (case["test_id"] + ".json"), raw)
    return raw


async def run(args):
    quality, bundle = load_quality(args.package)
    quality.validate_bundle(bundle, root=args.package.parents[1])
    scenarios = (
        json.loads(args.scenario_contract.read_text(encoding="utf-8"))
        if args.scenario_contract
        else {}
    )
    for scenario in scenarios.values():
        if set(scenario) - {"topic_id", "setup_turns"}:
            raise ValueError("Scenario contract accepts only explicit user inputs")
        for setup in scenario.get("setup_turns", []):
            SendInput(request_id=uuid.uuid4(), **setup)
    settings = get_settings()
    if settings.app_env != "development" or settings.auth_mode != "development":
        raise ValueError("Use the existing authenticated development environment")
    app = create_app(settings)
    args.output.mkdir(parents=True, exist_ok=True)
    original_retrieve = graph_module.retrieve

    async def recorded_retrieve(
        session, model, config, question, scopes, domain, benefit_code=None
    ):
        trace = TRACE.get()
        call = {
            "query": question,
            "scopes": scopes,
            "domain": domain,
            "benefit_code": benefit_code,
            "app_env_filter": config.app_env,
            "version_filter": config.active_kb_version,
        }
        if trace is not None:
            trace["retrieval_calls"].append(call)
        started = time.monotonic()
        try:
            rows = await original_retrieve(
                session, model, config, question, scopes, domain, benefit_code=benefit_code
            )
            call["chunks"] = rows
            return rows
        except Exception as error:
            call["error"] = type(error).__name__
            raise
        finally:
            call["duration_ms"] = round((time.monotonic() - started) * 1000)

    handler = CaptureLogs()
    logger = logging.getLogger("milioai")
    logger.addHandler(handler)
    graph_module.retrieve = recorded_retrieve
    try:
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://evaluation",
                headers={"Authorization": "Bearer " + settings.dev_auth_token},
            ) as client:
                me = await client.get("/api/v1/me")
                me.raise_for_status()
                uid = uuid.UUID(me.json()["id"])
                async with app.state.sessions() as session:
                    user = await session.get(User, uid)
                    authorized = set(["test", *settings.dev_document_scopes, *user.scopes])
            records, mapping = await inventory(app, bundle)
            manifest_path = args.output / "manifest.json"
            signature = {
                "source_sha256": {
                    str(p.relative_to(Path(__file__).parents[2])): digest(p)
                    for p in sorted(Path(__file__).parents[1].rglob("*.py"))
                },
                "configuration_sha256": digest(
                    Path(__file__).parents[1] / "support" / "operational_guidance.json"
                ),
                "artifact_hashes": {
                    k: v for k, v in quality.export_template(bundle).items() if k.endswith("sha256")
                },
                "evaluator_sha256": digest(args.package / "quality.py"),
                "runtime_settings": {
                    k: getattr(settings, k)
                    for k in (
                        "ollama_model",
                        "embedding_model",
                        "embedding_dimensions",
                        "rag_top_k",
                        "rag_max_distance",
                        "active_kb_version",
                        "vt_kb_version",
                        "ollama_timeout",
                        "generation_limit",
                        "context_size",
                        "rag_profile",
                    )
                },
                "dataset_sha256": quality.sha256(args.package / "rag_eval_dataset.jsonl"),
                "scenario_contract_sha256": digest(args.scenario_contract)
                if args.scenario_contract
                else None,
                "inventory_sha256": hashlib.sha256(
                    json.dumps(records, sort_keys=True, default=str).encode()
                ).hexdigest(),
            }
            if manifest_path.exists():
                manifest = quality.read_json(manifest_path)
                if manifest["signature"] != signature:
                    raise ValueError("Resume rejected: code, dataset or document inventory changed")
            else:
                manifest = {
                    "run_id": "rag-real-" + uuid.uuid4().hex[:12],
                    "executed_at": datetime.now().astimezone().isoformat(),
                    "signature": signature,
                    "concurrency": 1,
                    "timeout_seconds_per_turn": settings.ollama_timeout,
                    "authenticated_user_id": str(uid),
                    "authorized_scopes": sorted(authorized),
                    "model": settings.ollama_model,
                    "embedding_model": settings.embedding_model,
                    "top_k": settings.rag_top_k,
                    "active_kb_version": settings.active_kb_version,
                    "auth_mode": settings.auth_mode,
                    "authentication_modified": False,
                    "corporate_cases": "real production document filters; development auth/host; not a production deployment test",
                }
                save(manifest_path, manifest)
                save(args.output / "document-crosswalk.json", records)
            graphs = {
                "local_review": ObservedGraph(app.state.graph),
                "corporate": ObservedGraph(
                    graph_module.build_graph(
                        app.state.sessions, app.state.ollama, PolicySettings(settings)
                    )
                ),
            }
            selected_ids = set(
                SAMPLE
                if args.sample
                else args.ids.split(",")
                if args.ids
                else [c["test_id"] for c in bundle["cases"]]
            )
            unknown = selected_ids - {c["test_id"] for c in bundle["cases"]}
            if unknown:
                raise ValueError("Unknown test IDs")
            for case in bundle["cases"]:
                if case["test_id"] not in selected_ids:
                    continue
                checkpoint = args.output / "cases" / (case["test_id"] + ".json")
                if checkpoint.exists():
                    continue
                wanted = set(case["run_context"]["scopes"])
                if not wanted <= authorized:
                    raise ValueError("Required scope unavailable for " + case["test_id"])
                # Attenuate a legitimately authenticated principal; never grant scopes or override auth.
                principal = Principal(uid, tuple(sorted(wanted)))
                actual_input = inputs(case)
                if case["test_id"] in scenarios:
                    actual_input["scenario_input"] = scenarios[case["test_id"]]
                raw = await run_case(app, principal, actual_input, graphs, args.output)
                regenerate(args.output, quality, bundle, mapping, manifest)
                print(
                    json.dumps(
                        {
                            "test_id": case["test_id"],
                            "duration_ms": raw["duration_ms"],
                            "completed": len(list((args.output / "cases").glob("*.json"))),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    finally:
        graph_module.retrieve = original_retrieve
        logger.removeHandler(handler)


def regenerate(output, quality, bundle, mapping, manifest):
    rows = [quality.read_json(p) for p in sorted((output / "cases").glob("*.json"))]
    export = quality.export_template(bundle)
    export.update(
        run_kind="real",
        run_id=manifest["run_id"],
        executed_at=manifest["executed_at"],
        results=[export_result(raw, mapping) for raw in rows],
    )
    quality.validate_export(export, bundle)
    save(output / "results.json", export)
    save(output / "quality-report.json", quality.evaluate(export, bundle))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--ids")
    parser.add_argument(
        "--scenario-contract",
        type=Path,
        help="Explicit user topic/actions; separate run, never inferred from expected answers",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Re-export recorded observations without authentication, DB or model calls",
    )
    args = parser.parse_args()
    if args.export_only:
        quality, bundle = load_quality(args.package)
        manifest = quality.read_json(args.output / "manifest.json")
        mapping = {
            d["runtime_document_id"]: d
            for d in quality.read_json(args.output / "document-crosswalk.json")
        }
        if manifest["signature"]["dataset_sha256"] != quality.sha256(
            args.package / "rag_eval_dataset.jsonl"
        ):
            raise ValueError("Dataset changed; cannot reinterpret recorded observations")
        regenerate(args.output, quality, bundle, mapping, manifest)
        save(
            args.output / "postprocessing-manifest.json",
            {
                "exporter_sha256": digest(__file__),
                "executed_at": datetime.now().astimezone().isoformat(),
                "model_or_database_calls": False,
                "execution_manifest_modified": False,
            },
        )
    else:
        asyncio.run(run(args))


if __name__ == "__main__":
    main()
