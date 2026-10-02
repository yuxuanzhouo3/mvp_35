"""Pin and restore the CloudBase baseline tag. Never resets or force-pushes."""

import subprocess
from pathlib import Path

from rollback.baseline import BASELINE_TAG
from rollback.errors import RollbackError

SKIP_PREFIXES = ("rollback/", "project.md")


def _git(repo: Path, *args: str, check: bool = True) -> str:
    forbidden = " ".join(args)
    if any(token in forbidden for token in ("reset", "push", "clean")):
        raise RollbackError("回退代码只允许 checkout 指定路径，禁止 reset / push / clean")
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RollbackError(result.stderr.strip() or f"git {' '.join(args)} 失败")
    return result.stdout.strip()


def head(repo) -> str:
    return _git(Path(repo), "rev-parse", "HEAD")


def pin(repo) -> str:
    root = Path(repo)
    rev = head(root)
    existing = _git(root, "rev-parse", "-q", "--verify", f"refs/tags/{BASELINE_TAG}", check=False)
    if existing and existing != rev:
        raise RollbackError(f"{BASELINE_TAG} 已指向 {existing}，拒绝移动标签")
    if not existing:
        _git(root, "tag", BASELINE_TAG, rev)
    return rev


def changed_paths(repo) -> list[str]:
    root = Path(repo)
    raw = _git(root, "diff", "--name-only", BASELINE_TAG)
    paths = []
    for line in raw.splitlines():
        if not line or line.startswith(SKIP_PREFIXES):
            continue
        paths.append(line)
    return paths


def apply_baseline(repo, paths: list[str] | None = None) -> list[str]:
    root = Path(repo)
    _git(root, "rev-parse", "-q", "--verify", f"refs/tags/{BASELINE_TAG}")
    selected = list(paths) if paths is not None else changed_paths(root)
    blocked = [item for item in selected if item.startswith(SKIP_PREFIXES) or item.startswith(".git")]
    if blocked:
        raise RollbackError(f"这些路径不在代码回退范围内: {blocked}")
    if not selected:
        return []
    _git(root, "checkout", BASELINE_TAG, "--", *selected)
    return selected
