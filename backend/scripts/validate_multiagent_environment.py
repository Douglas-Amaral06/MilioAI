"""Creates a fresh disposable database; never upgrades the configured main database.
Run from backend. Keeps the isolated database and JSON evidence for review.
"""

import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings
from app.db.models import Document, DocumentChunk

settings = get_settings()
main_url = make_url(settings.database_url)
name = "milioai_multiagent_" + datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
assert name.startswith("milioai_multiagent_") and name.replace("_", "").isalnum()
report = {"isolated_database": name, "main_database_migrated": False}
main = create_engine(main_url)
with main.connect() as connection:
    report["main_revision_before"] = connection.execute(
        text("select version_num from alembic_version")
    ).scalar()
    report["main_messages_before"] = connection.execute(
        text("select count(*) from messages")
    ).scalar()
    report["inventory"] = [
        dict(r)
        for r in connection.execute(
            text(
                "select name,domain,scope,version,status,approved,validation_only,media_type from documents order by domain,name"
            )
        ).mappings()
    ]
    documents = list(connection.execute(select(Document.__table__)).mappings())
    chunks = list(connection.execute(select(DocumentChunk.__table__)).mappings())
admin = create_engine(main_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
with admin.connect() as connection:
    connection.execute(text('CREATE DATABASE "' + name + '"'))
admin.dispose()
test_url = main_url.set(database=name)
env = dict(
    os.environ, DATABASE_URL=test_url.render_as_string(hide_password=False), RUN_DB_TESTS="1"
)


def run(*args):
    result = subprocess.run([sys.executable, *args], env=env, text=True, capture_output=True)
    print(result.stdout, flush=True)
    if result.returncode:
        print(result.stderr, flush=True)
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


report["upgrade_0004"] = run("-m", "alembic", "upgrade", "0004")
if report["upgrade_0004"]["returncode"]:
    raise SystemExit("Isolated migration failed")
isolated = create_engine(test_url)
user, conversation, message, request = [uuid.uuid4() for _ in range(4)]
with isolated.begin() as c:
    c.execute(
        text(
            "insert into users(id,identity,scopes) values (:id,'multiagent-migration-sentinel','[]'::jsonb)"
        ),
        {"id": user},
    )
    c.execute(
        text("insert into conversations(id,user_id,title) values (:id,:user,'migration sentinel')"),
        {"id": conversation, "user": user},
    )
    c.execute(
        text(
            "insert into messages(id,conversation_id,request_id,role,content,status,sources) values (:id,:conversation,:request,'user','preserve original content','complete','[]'::jsonb)"
        ),
        {"id": message, "conversation": conversation, "request": request},
    )
report["upgrade_0005"] = run("-m", "alembic", "upgrade", "head")
with isolated.connect() as c:
    row = c.execute(
        text("select content,contacts from messages where id=:id"), {"id": message}
    ).one()
    report["migration_preserves_existing_message"] = (
        row.content == "preserve original content" and row.contacts == []
    )
with isolated.begin() as c:
    if documents:
        c.execute(Document.__table__.insert(), documents)
    if chunks:
        c.execute(DocumentChunk.__table__.insert(), chunks)
report["copied_authorized_corpus"] = {
    "documents": len(documents),
    "chunks": len(chunks),
    "reindexed": False,
}
if "--tests" in sys.argv:
    report["regression"] = run("-m", "pytest", "-m", "not live", "-q", "--tb=short")
if "--live" in sys.argv:
    report["live"] = run("scripts/evaluate_multiagent.py")
with main.connect() as c:
    report["main_revision_after"] = c.execute(
        text("select version_num from alembic_version")
    ).scalar()
    report["main_messages_after"] = c.execute(text("select count(*) from messages")).scalar()
report["main_revision_unchanged"] = report["main_revision_before"] == report["main_revision_after"]
Path("multiagent-environment.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
)
print(
    json.dumps(
        {
            k: v
            for k, v in report.items()
            if k not in {"inventory", "regression", "upgrade_0004", "upgrade_0005", "live"}
        },
        ensure_ascii=False,
        default=str,
    ),
    flush=True,
)
