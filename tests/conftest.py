from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ivi_chm.indexer import build_index  # noqa: E402

from ._support import MINI_HTML_DIR, REAL_HTML_DIR, load_cases  # noqa: E402


@pytest.fixture(scope="session")
def lookup_cases() -> list[dict[str, object]]:
    return load_cases()


@pytest.fixture(scope="session")
def real_index_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    index_dir = tmp_path_factory.mktemp("real-ivi-chm-index")
    index_file = index_dir / "index.sqlite3"
    build_index(REAL_HTML_DIR, index_file)
    return index_dir


@pytest.fixture(scope="session")
def mini_index_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    index_dir = tmp_path_factory.mktemp("mini-ivi-chm-index")
    index_file = index_dir / "index.sqlite3"
    build_index(MINI_HTML_DIR, index_file)
    return index_dir


@pytest.fixture(scope="session")
def mini_html_dir() -> Path:
    return MINI_HTML_DIR

