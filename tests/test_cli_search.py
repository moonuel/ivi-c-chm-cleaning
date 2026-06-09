from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests._support import MINI_HTML_DIR, REAL_HTML_DIR


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{SRC}{os.pathsep}{pythonpath}" if pythonpath else str(SRC)
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ivi_chm.cli", *args],
        cwd=ROOT,
        env=_cli_env(),
        text=True,
        capture_output=True,
        check=True,
    )


def test_cli_parse_outputs_json(mini_html_dir: Path) -> None:
    result = _run_cli("parse", str(mini_html_dir / "Mini_NormalizedAlias.html"))
    payload = json.loads(result.stdout)
    assert payload["symbol"] == "Mini_NormalizedAlias"
    assert payload["path_id"] == "Mini_NormalizedAlias"


def test_cli_index_and_search(real_index_dir: Path) -> None:
    index_dir = real_index_dir
    _run_cli("index", str(REAL_HTML_DIR), str(index_dir))

    result = _run_cli("search", "KTNA_ATTR_CACHE", str(index_dir))
    payload = json.loads(result.stdout)
    assert payload[0]["symbol"] == "KTNA_ATTR_CACHE"
    assert payload[0]["matched_on"] == "exact"


def test_cli_defaults_to_portable_sqlite_index(tmp_path: Path) -> None:
    index_file = tmp_path / "portable-index.sqlite3"
    _run_cli("index", str(REAL_HTML_DIR), str(index_file))

    result = _run_cli("search", "KTNA_ATTR_CACHE", str(index_file))
    payload = json.loads(result.stdout)
    assert payload[0]["symbol"] == "KTNA_ATTR_CACHE"


def test_cli_search_uses_documented_argument_order(mini_index_dir: Path) -> None:
    result = _run_cli("search", "mininormalizedalias", str(mini_index_dir))
    payload = json.loads(result.stdout)
    assert payload[0]["symbol"] == "Mini_NormalizedAlias"
    assert payload[0]["matched_on"] == "alias"
