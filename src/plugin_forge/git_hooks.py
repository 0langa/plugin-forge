"""Git hook logic. Invoked by the small shell wrappers under `git_hook_templates/`.

`pre_commit`  — block if provider manifests diverge from forge.yaml.
`pre_push`    — block if marketplace jsons are stale vs plugin version.
`install`     — copy hook wrappers into a target repo's `.git/hooks/`.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


HOOKS = ("pre-commit", "pre-push")


def _repo_root() -> Path:
    return Path(os.getcwd()).resolve()


def _template_dir() -> Path:
    return (Path(__file__).parent.parent.parent / "git_hook_templates").resolve()


def pre_commit() -> int:
    repo = _repo_root()
    forge_yaml = repo / "forge.yaml"
    if not forge_yaml.exists():
        return 0
    from plugin_forge import sync
    from plugin_forge.spec import ForgeSpec

    try:
        spec = ForgeSpec.load(forge_yaml)
    except Exception as exc:
        print(f"[forge] forge.yaml invalid: {exc}", file=sys.stderr)
        return 1
    report = sync.check(spec, repo)
    if report.is_clean:
        return 0
    print("[forge] BLOCK: manifest drift vs forge.yaml", file=sys.stderr)
    for d in report.drift:
        print(f"  {d.provider.value}: {d.kind} — {d.message}", file=sys.stderr)
    print("  fix: python -m plugin_forge sync --fix", file=sys.stderr)
    print("  bypass: append [skip-forge] to commit message or use --no-verify", file=sys.stderr)
    return 1


def pre_push() -> int:
    repo = _repo_root()
    forge_yaml = repo / "forge.yaml"
    if not forge_yaml.exists():
        return 0
    from plugin_forge import status

    st = status.probe(repo)
    if st.marketplace_synced is False:
        print("[forge] BLOCK: marketplace out of sync", file=sys.stderr)
        for note in st.marketplace_notes:
            print(f"  {note}", file=sys.stderr)
        print("  fix: python -m plugin_forge register-marketplace", file=sys.stderr)
        print("  bypass: [skip-forge] in commit or --no-verify", file=sys.stderr)
        return 1
    return 0


def install_hooks(target_repo: Path) -> list[Path]:
    """Copy hook wrappers into `<target_repo>/.git/hooks/`, chaining if present."""
    hooks_dir = target_repo / ".git" / "hooks"
    if not hooks_dir.is_dir():
        raise FileNotFoundError(f"{hooks_dir} does not exist — is this a git repo?")

    installed: list[Path] = []
    tmpl = _template_dir()
    for name in HOOKS:
        src = tmpl / name
        dst = hooks_dir / name
        if not src.exists():
            continue
        if dst.exists() and _is_forge_hook(dst):
            installed.append(dst)
            continue
        if dst.exists():
            existing = dst.read_text(encoding="utf-8")
            new = src.read_text(encoding="utf-8") + "\n\n# --- chained original ---\n" + existing
            dst.write_text(new, encoding="utf-8")
        else:
            shutil.copy2(src, dst)
        os.chmod(dst, 0o755)
        installed.append(dst)
    return installed


def _is_forge_hook(path: Path) -> bool:
    try:
        return "plugin_forge.git_hooks" in path.read_text(encoding="utf-8")
    except Exception:
        return False


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python -m plugin_forge.git_hooks {pre_commit|pre_push|install <repo>}", file=sys.stderr)
        return 2
    cmd = argv[0]
    if cmd == "pre_commit":
        return pre_commit()
    if cmd == "pre_push":
        return pre_push()
    if cmd == "install":
        repo = Path(argv[1]).resolve() if len(argv) > 1 else _repo_root()
        installed = install_hooks(repo)
        for p in installed:
            print(f"installed {p}")
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
