from __future__ import annotations

import io
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from scripts.prepare_public_export import (
    REPO_ROOT,
    audit_export_manifest,
    check_privacy_rules,
    create_clean_public_branch,
    safe_extract_tar,
    verify_git_archive_export,
)
from usm_sim import build_restu_17sep_replay, simulate


def test_audit_export_manifest_catches_forbidden_patterns() -> None:
    forbidden_samples = [
        "raw_data/sensor_logger/Location.csv",
        "raw_data/media/videos/video_1.mp4",
        ".agent-native/visual-docs/plan.mdx",
        "agent-native.json",
        "AGENTS.md",
        ".scratch/issues/01.md",
        "TASK_SPEC.md",
        "docs/agents/architecture.md",
        "docs/plans/review.md",
        "docs/reviews/audit.md",
        ".git-index.lock",
        "temp.lock",
        "unblurred.mp4",
        "hardware.zip",
        "device/Metadata.csv",
    ]
    for sample in forbidden_samples:
        issues = audit_export_manifest([sample])
        assert any("Forbidden path" in iss for iss in issues), f"Failed to flag {sample}"


def test_audit_export_manifest_catches_missing_required_paths() -> None:
    valid_sample = [
        ".github/workflows/ci.yml",
        ".github/workflows/pages.yml",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        "LICENSE",
        "README.md",
        "pyproject.toml",
        "uv.lock",
        "usm_sim/__init__.py",
        "operator_dashboard/__init__.py",
        "proposal_site/index.html",
        "docs/PRIVACY_AND_PUBLICATION.md",
        "tests/fixtures/gps/session_1_2026-09-17_morning_M08_to_DTSP_Location.csv",
        "tests/fixtures/gps/session_3_2026-09-18_morning_M01_Rainy_to_DTSP_Location.csv",
    ]
    assert audit_export_manifest(valid_sample) == []

    incomplete_sample = valid_sample[1:]  # Missing ci.yml
    issues = audit_export_manifest(incomplete_sample)
    assert any("Required path missing" in iss and "ci.yml" in iss for iss in issues)


def test_check_privacy_rules_clean() -> None:
    violations = check_privacy_rules(REPO_ROOT)
    assert violations == [], f"Privacy violations detected: {violations}"


def test_verify_git_archive_export_succeeds() -> None:
    if not (REPO_ROOT / ".git").exists():
        pytest.skip("Git archive export requires a git checkout")
    ok, issues = verify_git_archive_export(REPO_ROOT)
    assert ok, f"Git archive verification failed: {issues}"
    assert issues == []


def test_safe_extract_tar_rejects_path_traversal(tmp_path: Path) -> None:
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        member = tarfile.TarInfo(name="../escape.txt")
        member.size = 5
        tar.addfile(member, io.BytesIO(b"hello"))

    tar_stream.seek(0)
    with tarfile.open(fileobj=tar_stream, mode="r") as tar:
        with pytest.raises(ValueError, match="Path traversal detected"):
            safe_extract_tar(tar, tmp_path)


def test_create_clean_public_branch_orphan_and_valid() -> None:
    if not (REPO_ROOT / ".git").exists():
        pytest.skip("Public branch creation requires a git checkout")
    test_branch = "test-export-branch-orphan-check"
    try:
        ok, msg = create_clean_public_branch(REPO_ROOT, branch_name=test_branch)
        assert ok, f"Branch creation failed: {msg}"

        # Verify orphan commit: exactly 0 parents
        rev_out = subprocess.check_output(
            ["git", "rev-list", "--parents", "-n", "1", f"refs/heads/{test_branch}"],
            cwd=REPO_ROOT,
            text=True,
        ).strip().split()
        assert len(rev_out) == 1, f"Expected 0 parents for root commit, got {rev_out}"

        # Verify tree manifest: zero forbidden files, required files present
        tree_files = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", f"refs/heads/{test_branch}"],
            cwd=REPO_ROOT,
            text=True,
        ).splitlines()
        issues = audit_export_manifest(tree_files)
        assert issues == [], f"Manifest audit issues on test branch: {issues}"
    finally:
        subprocess.run(
            ["git", "update-ref", "-d", f"refs/heads/{test_branch}"],
            cwd=REPO_ROOT,
            capture_output=True,
        )


def test_extracted_archive_cli_simulation_smoke(tmp_path: Path) -> None:
    if not (REPO_ROOT / ".git").exists():
        pytest.skip("Git archive export requires a git checkout")
    # 1. Export git archive tar
    tar_bytes = subprocess.check_output(
        ["git", "archive", "--worktree-attributes", "--format=tar", "HEAD"],
        cwd=REPO_ROOT,
    )

    # 2. Extract into tmp_path
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        safe_extract_tar(tar, tmp_path)

    # Confirm raw_data does not exist in extracted directory
    assert not (tmp_path / "raw_data").exists()

    # 3. Test CLI artificial simulation execution
    cli_proc = subprocess.run(
        [sys.executable, "-m", "usm_sim", "simulate", "--case", "artificial", "--compact"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"status": "completed"' in cli_proc.stdout

    # 4. Test restu replay builder using fixture fallback
    scenario, policy = build_restu_17sep_replay(tmp_path)
    res = simulate(scenario, policy)
    assert res["status"] == "completed"
