"""Root pytest configuration and test categorization hooks."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-benchmark",
        action="store_true",
        default=False,
        help="Run expensive whole-campus benchmark and optimization loop tests",
    )
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run tests taking > 5 seconds (such as repeated full-cohort simulations)",
    )


def _marker_requested(markexpr: str, name: str) -> bool:
    import re
    if not markexpr:
        return False
    if re.search(rf"\bnot\s+{name}\b", markexpr):
        return False
    return bool(re.search(rf"\b{name}\b", markexpr))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    markexpr = config.getoption("-m") or ""
    run_benchmark = config.getoption("--run-benchmark") or _marker_requested(markexpr, "benchmark")
    run_slow = config.getoption("--run-slow") or _marker_requested(markexpr, "slow")
    skip_benchmark = pytest.mark.skip(
        reason="Benchmark test skipped; pass --run-benchmark or -m benchmark to execute"
    )
    skip_slow = pytest.mark.skip(
        reason="Slow test skipped; pass --run-slow or -m slow to execute"
    )

    for item in items:
        if "benchmark" in item.keywords and not run_benchmark:
            item.add_marker(skip_benchmark)
        if "slow" in item.keywords and not run_slow:
            item.add_marker(skip_slow)
