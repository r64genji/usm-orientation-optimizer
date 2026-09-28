from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
INTERPRETER = Path(sys.executable)
REPO_ROOT = Path(__file__).resolve().parents[2]


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def artificial_full():
    return load_fixture("artificial_seed42_full.json")


@pytest.fixture
def artificial_compact():
    return load_fixture("artificial_seed42_compact.json")


@pytest.fixture
def artificial_unfinished():
    return load_fixture("artificial_unfinished_full.json")
