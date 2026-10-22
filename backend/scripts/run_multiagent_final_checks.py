"""Reuses only the already-created isolated DB; does not create or migrate databases."""

import json
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings

report = json.loads(Path("multiagent-environment.json").read_text(encoding="utf-8"))
name = report["isolated_database"]
assert name.startswith("milioai_multiagent_")
url = make_url(get_settings().database_url).set(database=name)
env = dict(os.environ, DATABASE_URL=url.render_as_string(hide_password=False), RUN_DB_TESTS="1")
result = subprocess.run(
    [sys.executable, "-m", "pytest", "-m", "not live", "-q", "--tb=short"],
    env=env,
    text=True,
    capture_output=True,
)
print(result.stdout, flush=True)
Path("multiagent-final-checks.json").write_text(
    json.dumps(
        {
            "database": name,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        },
        indent=2,
    ),
    encoding="utf-8",
)
base = json.loads(Path("multiagent-live.json").read_text(encoding="utf-8"))
for scenario in (
    "generate_timesheet",
    "course_certificate",
    "work_certificate",
    "benefit_discount",
):
    run = subprocess.run(
        [sys.executable, "scripts/evaluate_multiagent.py", "--scenario", scenario],
        env=env,
        text=True,
        capture_output=True,
    )
    print(run.stdout, flush=True)
    if run.returncode:
        print(run.stderr, flush=True)
        continue
    current = json.loads(Path("multiagent-live.json").read_text(encoding="utf-8"))
    Path("multiagent-live-final-" + scenario + ".json").write_text(
        json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    base["results"] = [row for row in base["results"] if row["scenario"] != scenario] + current[
        "results"
    ]
base["note"] = (
    "Final changed generative flows plus preserved exact SPTrans and instructor evidence from prior bounded live run."
)
Path("multiagent-live-final.json").write_text(
    json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8"
)
