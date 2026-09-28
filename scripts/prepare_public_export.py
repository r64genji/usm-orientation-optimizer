#!/usr/bin/env python3
"""Public export preparation and privacy compliance audit script.

Verifies privacy invariants, checks for machine-specific path leakage,
and validates that git archive exports properly exclude unblurred media
and device-identifying hardware telemetry.
"""

from __future__ import annotations
import argparse
import io
import os
import re
import subprocess
import sys
import tarfile
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent

# Forbidden patterns in public source files (excluding legacy research logs)
FORBIDDEN_PATH_PATTERNS = [
    re.compile(r"/home/\w+/"),
]

# Sensitive / internal export patterns that must NEVER appear in public exports or public branch
FORBIDDEN_EXPORT_PATTERNS = [
    re.compile(r"^raw_data(/.*)?$", re.IGNORECASE),
    re.compile(r"^\.agent-native(/.*)?$", re.IGNORECASE),
    re.compile(r"^agent-native\.json$", re.IGNORECASE),
    re.compile(r"^AGENTS\.md$", re.IGNORECASE),
    re.compile(r"^\.scratch(/.*)?$", re.IGNORECASE),
    re.compile(r"^TASK_SPEC\.md$", re.IGNORECASE),
    re.compile(r"^docs/agents(/.*)?$", re.IGNORECASE),
    re.compile(r"^docs/plans(/.*)?$", re.IGNORECASE),
    re.compile(r"^docs/reviews(/.*)?$", re.IGNORECASE),
    re.compile(r"^research/logs(/.*)?$", re.IGNORECASE),
    re.compile(r"^research/prompts(/.*)?$", re.IGNORECASE),
    re.compile(r"^research/shared(/.*)?$", re.IGNORECASE),
    re.compile(r"^research/reports/00_AGENT_CONTEXT\.md$", re.IGNORECASE),
    re.compile(r"^(?:.*/)?\.git-index.*$", re.IGNORECASE),
    re.compile(r"^(?!uv\.lock$).*\.lock$", re.IGNORECASE),
    re.compile(r"^\.git(?!hub(/.*)?$).*", re.IGNORECASE),
    re.compile(r"^.*\.mp4$", re.IGNORECASE),
    re.compile(r"^.*\.zip$", re.IGNORECASE),
    re.compile(r"^.*/Metadata\.csv$", re.IGNORECASE),
]

# Required paths that MUST be present in public exports and public branch
REQUIRED_EXPORT_PATHS = [
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


def audit_export_manifest(paths: list[str]) -> list[str]:
    """Validate that paths contain zero forbidden entries and all required entries."""
    issues: list[str] = []
    path_set = set(p.strip("/") for p in paths)

    for p in paths:
        normalized = p.strip("/")
        for pat in FORBIDDEN_EXPORT_PATTERNS:
            if pat.search(normalized):
                issues.append(f"Forbidden path included in export manifest: {normalized}")
                break

    for req in REQUIRED_EXPORT_PATHS:
        if req not in path_set:
            issues.append(f"Required path missing from export manifest: {req}")

    return issues


def safe_extract_tar(tar: tarfile.TarFile, dest_dir: Path) -> None:
    """Safely extract tar archive preventing path traversal."""
    dest_resolved = dest_dir.resolve()
    for member in tar.getmembers():
        target_path = (dest_dir / member.name).resolve()
        if not str(target_path).startswith(str(dest_resolved)):
            raise ValueError(f"Path traversal detected in archive entry: {member.name}")
        if member.islnk() or member.issym():
            link_target = (dest_dir / member.linkname).resolve()
            if not str(link_target).startswith(str(dest_resolved)):
                raise ValueError(f"Symlink traversal detected: {member.name} -> {member.linkname}")
    if hasattr(tarfile, "data_filter"):
        tar.extractall(path=dest_dir, filter="data")
    else:
        tar.extractall(path=dest_dir)


def check_privacy_rules(repo_root: Path) -> list[str]:
    """Scan code and documentation for privacy or machine-specific leaks."""
    violations: list[str] = []

    # Files and directories to check for path leaks
    scan_paths = [
        repo_root / "usm_sim",
        repo_root / "operator_dashboard",
        repo_root / "proposal_site",
        repo_root / "scripts",
        repo_root / "tests",
        repo_root / "docs",
        repo_root / "research/reports",
        repo_root / ".github",
        repo_root / "pyproject.toml",
        repo_root / "README.md",
    ]

    for p in scan_paths:
        if not p.exists():
            continue
        files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file() and not f.name.endswith((".png", ".jpg", ".map", ".sqlite", ".pyc"))]
        for f in files:
            if "node_modules" in f.parts or "dist" in f.parts or ".git" in f.parts:
                continue
            rel = f.relative_to(repo_root)
            rel_str = str(rel).replace("\\", "/")
            if any(pat.search(rel_str) for pat in FORBIDDEN_EXPORT_PATTERNS):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pat in FORBIDDEN_PATH_PATTERNS:
                matches = pat.findall(content)
                if matches:
                    rel = f.relative_to(repo_root)
                    violations.append(f"Hardcoded absolute path found in {rel}: {matches[:3]}")

    return violations


def verify_git_archive_export(repo_root: Path) -> tuple[bool, list[str]]:
    """Test `git archive` generation and verify sensitive files are excluded and required files present."""
    try:
        proc = subprocess.run(
            ["git", "archive", "--worktree-attributes", "--format=tar", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            check=True,
        )
    except Exception as exc:
        return False, [f"Failed to run git archive: {exc}"]

    tar_bytes = io.BytesIO(proc.stdout)
    with tarfile.open(fileobj=tar_bytes, mode="r:") as tar:
        names = [m.name for m in tar.getmembers() if not m.isdir()]

    issues = audit_export_manifest(names)
    return len(issues) == 0, issues


def create_clean_public_branch(repo_root: Path, branch_name: str = "public-release") -> tuple[bool, str]:
    """Create an orphan public release branch from a sanitized export tree.

    This ensures that historical private blobs (videos, hardware zips, device UUIDs)
    never exist anywhere in the public branch's commit history, completely eliminating
    the risk of leaking historical blobs when pushed to a public remote.
    """
    try:
        proc = subprocess.run(
            ["git", "archive", "--worktree-attributes", "--format=tar", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            check=True,
        )
        tar_bytes = proc.stdout

        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as tar:
            names = [m.name for m in tar.getmembers() if not m.isdir()]
        manifest_issues = audit_export_manifest(names)
        if manifest_issues:
            return False, f"Export manifest audit failed: {manifest_issues[:3]}"

        import tempfile
        with tempfile.TemporaryDirectory() as work_dir, tempfile.TemporaryDirectory() as index_dir:
            work_path = Path(work_dir)
            with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as tar:
                safe_extract_tar(tar, work_path)

            env = dict(os.environ)
            env["GIT_WORK_TREE"] = str(work_path)
            index_file = Path(index_dir) / "index"
            env["GIT_INDEX_FILE"] = str(index_file)

            # Ensure git author and committer identity are set even in clean CI environments
            for key, config_key, default_val in [
                ("GIT_AUTHOR_NAME", "user.name", "abe"),
                ("GIT_AUTHOR_EMAIL", "user.email", "abe@debian"),
                ("GIT_COMMITTER_NAME", "user.name", "abe"),
                ("GIT_COMMITTER_EMAIL", "user.email", "abe@debian"),
            ]:
                if not env.get(key):
                    try:
                        cfg_val = subprocess.check_output(
                            ["git", "config", config_key], cwd=repo_root, text=True
                        ).strip()
                        env[key] = cfg_val or default_val
                    except Exception:
                        env[key] = default_val

            subprocess.run(["git", "add", "-A"], cwd=repo_root, env=env, check=True)
            tree_proc = subprocess.run(
                ["git", "write-tree"],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            tree_oid = tree_proc.stdout.strip()

            commit_msg = "feat(release): initial public release of USM orientation movement simulator & optimizer"
            commit_proc = subprocess.run(
                ["git", "commit-tree", tree_oid, "-m", commit_msg],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            commit_oid = commit_proc.stdout.strip()

            subprocess.run(
                ["git", "update-ref", f"refs/heads/{branch_name}", commit_oid],
                cwd=repo_root,
                check=True,
            )

            parent_check = subprocess.run(
                ["git", "rev-list", "--parents", "-n", "1", commit_oid],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            parents = parent_check.stdout.strip().split()
            if len(parents) != 1:
                return False, f"Public release branch is not an orphan root commit: {parents}"

            tree_files_proc = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", commit_oid],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            branch_files = tree_files_proc.stdout.splitlines()
            branch_issues = audit_export_manifest(branch_files)
            if branch_issues:
                return False, f"Public release branch tree failed manifest audit: {branch_issues[:3]}"

            subprocess.run(
                ["git", "fsck", "--full", commit_oid],
                cwd=repo_root,
                capture_output=True,
                check=True,
            )

            return True, f"Successfully created clean public branch '{branch_name}' (commit {commit_oid[:8]})."
    except Exception as exc:
        return False, f"Failed to create public branch: {exc}"

def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and prepare public release export.")
    parser.add_argument("--verify-only", action="store_true", help="Only verify compliance without writing output.")
    parser.add_argument("--output", "-o", type=Path, help="Target tar.gz archive path.")
    parser.add_argument("--create-public-branch", metavar="BRANCH", nargs="?", const="public-release", help="Create clean-history orphan branch for public GitHub remote.")
    args = parser.parse_args()

    print("[*] Auditing repository for privacy compliance and path portability...")
    path_violations = check_privacy_rules(REPO_ROOT)
    if path_violations:
        print("[!] Path portability violations found:")
        for v in path_violations:
            print(f"    - {v}")
    else:
        print("[+] Zero hardcoded user paths found in active source packages.")

    print("[*] Testing git export-ignore rules against git archive...")
    ok, export_issues = verify_git_archive_export(REPO_ROOT)
    if not ok:
        print("[!] Git archive export contains sensitive files:")
        for iss in export_issues:
            print(f"    - {iss}")
    else:
        print("[+] Git archive export satisfies all privacy, data policy, and export manifest assertions.")

    if path_violations or not ok:
        return 1
    if args.output:
        print(f"[*] Creating export archive: {args.output}")
        with open(args.output, "wb") as f_out:
            subprocess.run(
                ["git", "archive", "--worktree-attributes", "--format=tar.gz", "--prefix=usm-orientation-optimizer/", "HEAD"],
                cwd=REPO_ROOT,
                stdout=f_out,
                check=True,
            )
        print(f"[+] Successfully wrote {args.output}")

    if args.create_public_branch:
        print(f"[*] Building clean-history public branch '{args.create_public_branch}'...")
        b_ok, msg = create_clean_public_branch(REPO_ROOT, args.create_public_branch)
        if not b_ok:
            print(f"[!] {msg}")
            return 1
        print(f"[+] {msg}")

    print("[+] All privacy and export compliance checks passed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
