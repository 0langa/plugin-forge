"""Provider data-root resolution shared by install, registration, and audit."""

from __future__ import annotations

import os
from pathlib import Path

from plugin_forge.spec import Provider

_DEFAULT_KIMI_HOME = "~/.kimi-code"


def kimi_code_home() -> Path:
    """Return Kimi's data root, honoring its documented environment override."""
    configured = os.environ.get("KIMI_CODE_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".kimi-code"


def has_kimi_code_home_override() -> bool:
    return bool(os.environ.get("KIMI_CODE_HOME"))


def resolve_install_path(raw: str, provider: Provider) -> Path:
    """Expand canonical provider install targets without changing custom paths."""
    if provider is Provider.KIMI:
        normalized = raw.replace(chr(92), "/").rstrip("/")
        if normalized == _DEFAULT_KIMI_HOME:
            return kimi_code_home()
        if normalized.startswith(f"{_DEFAULT_KIMI_HOME}/"):
            suffix = normalized.removeprefix(f"{_DEFAULT_KIMI_HOME}/")
            return kimi_code_home().joinpath(*[part for part in suffix.split("/") if part])
    return Path(raw).expanduser()
