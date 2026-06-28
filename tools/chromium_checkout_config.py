#!/usr/bin/env python3
"""Read local Chromium checkout configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path("chromium_checkout.local.json")
EXAMPLE_CONFIG = Path("chromium_checkout.local.json.example")


def default_config(repo_root: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "chromium_root": r"C:\src\chromium\src",
        "depot_tools": r"C:\src\depot_tools",
        "checkout_parent": r"C:\src\chromium",
    }


def load_config(repo_root: Path, config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or (repo_root / DEFAULT_CONFIG)
    if not path.exists():
        return default_config(repo_root)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError(f"unsupported config schema in {path}")
    return payload


def resolve_chromium_root(repo_root: Path, explicit: Path | None = None) -> Path | None:
    if explicit is not None:
        return explicit
    config = load_config(repo_root)
    chromium_root = config.get("chromium_root")
    if not isinstance(chromium_root, str) or not chromium_root:
        return None
    return Path(chromium_root)