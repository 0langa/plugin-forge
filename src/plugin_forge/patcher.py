"""Transactional settings.json patcher.

Rules:
    - Every apply writes a `.forge-backup.<ts>` copy of the target file first.
    - The apply is computed as a deep-merge over the existing JSON. Keys added
      by the patch are tracked in an install-receipt so uninstall can remove
      exactly what was added and no more.
    - On any exception during apply, the original file is restored from backup.
    - Patches are keyed by (plugin_name, target_path). Reinstalling replaces
      the prior receipt for that key.

The receipt is stored at:
    ~/.plugin-forge/receipts/<plugin>__<hashed_target>.json

Consumers should treat the receipt as opaque; use `unapply()` to reverse.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RECEIPTS_DIR = Path.home() / ".plugin-forge" / "receipts"


@dataclass(frozen=True)
class Receipt:
    plugin: str
    target: Path
    backup: Path
    added_paths: list[list[str]]
    scalar_overrides: dict[str, Any]
    timestamp: float

    def to_json(self) -> dict[str, Any]:
        return {
            "plugin": self.plugin,
            "target": str(self.target),
            "backup": str(self.backup),
            "added_paths": self.added_paths,
            "scalar_overrides": self.scalar_overrides,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Receipt:
        return cls(
            plugin=data["plugin"],
            target=Path(data["target"]),
            backup=Path(data["backup"]),
            added_paths=data["added_paths"],
            scalar_overrides=data["scalar_overrides"],
            timestamp=data["timestamp"],
        )


def _receipt_path(plugin: str, target: Path) -> Path:
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(str(target.resolve()).encode("utf-8")).hexdigest()[:12]
    return RECEIPTS_DIR / f"{plugin}__{digest}.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"target {path} is not valid JSON: {exc}") from exc


def _backup(target: Path) -> Path:
    ts = int(time.time())
    backup = target.with_suffix(target.suffix + f".forge-backup.{ts}")
    if target.exists():
        shutil.copy2(target, backup)
    else:
        backup.write_text("{}", encoding="utf-8")
    return backup


def apply(plugin: str, target: Path, patch: dict[str, Any], *, dry_run: bool = False) -> Receipt:
    """Deep-merge `patch` into JSON at `target`, tracking additions for later reversal.

    If `dry_run`, returns the intended receipt without writing anything.
    """
    if not isinstance(patch, dict):
        raise TypeError("patch must be a dict")

    target = target.resolve()
    original = _load_json(target)
    merged = json.loads(json.dumps(original))

    added_paths: list[list[str]] = []
    scalar_overrides: dict[str, Any] = {}

    _deep_merge(merged, patch, path=[], added=added_paths, overrides=scalar_overrides, original=original)

    if dry_run:
        return Receipt(
            plugin=plugin,
            target=target,
            backup=target.with_suffix(target.suffix + ".forge-backup.dry"),
            added_paths=added_paths,
            scalar_overrides=scalar_overrides,
            timestamp=time.time(),
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    backup = _backup(target)
    try:
        target.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    except Exception:
        if backup.exists():
            shutil.copy2(backup, target)
        raise

    receipt = Receipt(
        plugin=plugin,
        target=target,
        backup=backup,
        added_paths=added_paths,
        scalar_overrides=scalar_overrides,
        timestamp=time.time(),
    )
    _receipt_path(plugin, target).write_text(
        json.dumps(receipt.to_json(), indent=2), encoding="utf-8"
    )
    return receipt


def _deep_merge(
    dst: dict[str, Any],
    src: dict[str, Any],
    *,
    path: list[str],
    added: list[list[str]],
    overrides: dict[str, Any],
    original: dict[str, Any] | None,
) -> None:
    for key, val in src.items():
        cur_path = [*path, key]
        original_here = original.get(key) if isinstance(original, dict) else None
        if isinstance(val, dict) and isinstance(dst.get(key), dict):
            _deep_merge(
                dst[key],
                val,
                path=cur_path,
                added=added,
                overrides=overrides,
                original=original_here if isinstance(original_here, dict) else None,
            )
        else:
            existed = key in dst
            if not existed:
                added.append(cur_path)
            else:
                overrides[".".join(cur_path)] = dst[key]
            dst[key] = val


def unapply(plugin: str, target: Path) -> bool:
    """Reverse a previous `apply()` using the stored receipt.

    Removes only keys we added and restores scalar overrides. Returns True if a
    receipt was found and reversed, False otherwise.
    """
    target = target.resolve()
    rpath = _receipt_path(plugin, target)
    if not rpath.exists():
        return False
    receipt = Receipt.from_json(json.loads(rpath.read_text(encoding="utf-8")))

    if not receipt.target.exists():
        rpath.unlink(missing_ok=True)
        return True

    current = _load_json(receipt.target)

    for override_path, prior_value in receipt.scalar_overrides.items():
        _set_at(current, override_path.split("."), prior_value)

    for added_path in receipt.added_paths:
        _delete_at(current, added_path)

    _prune_empty(current)

    receipt.target.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    rpath.unlink(missing_ok=True)
    return True


def _set_at(root: dict[str, Any], path: list[str], value: Any) -> None:
    cur: Any = root
    for key in path[:-1]:
        if not isinstance(cur, dict) or key not in cur:
            return
        cur = cur[key]
    if isinstance(cur, dict) and path[-1] in cur:
        cur[path[-1]] = value


def _delete_at(root: dict[str, Any], path: list[str]) -> None:
    cur: Any = root
    for key in path[:-1]:
        if not isinstance(cur, dict) or key not in cur:
            return
        cur = cur[key]
    if isinstance(cur, dict):
        cur.pop(path[-1], None)


def _prune_empty(root: dict[str, Any]) -> None:
    to_delete = []
    for key, val in list(root.items()):
        if isinstance(val, dict):
            _prune_empty(val)
            if not val:
                to_delete.append(key)
    for key in to_delete:
        root.pop(key, None)


def restore_from_backup(plugin: str, target: Path) -> bool:
    """Emergency reset: restore the file from the most-recent backup captured for `plugin`."""
    target = target.resolve()
    rpath = _receipt_path(plugin, target)
    if not rpath.exists():
        return False
    receipt = Receipt.from_json(json.loads(rpath.read_text(encoding="utf-8")))
    if not receipt.backup.exists():
        return False
    shutil.copy2(receipt.backup, receipt.target)
    rpath.unlink(missing_ok=True)
    return True
