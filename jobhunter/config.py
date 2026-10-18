"""Paths and config loading. Everything is file-based so it is easy to hand-edit."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"

_CACHE: dict[str, dict] = {}


def load_yaml(name: str) -> dict:
    if name in _CACHE:
        return _CACHE[name]
    path = CONFIG_DIR / name
    data: dict = {}
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _CACHE[name] = data
    return data


def companies() -> dict:
    return load_yaml("companies.yaml")


def filters() -> dict:
    return load_yaml("filters.yaml")


def profile() -> dict:
    return load_yaml("profile.yaml")


def env() -> dict:
    load_dotenv(ROOT / ".env")
    return dict(os.environ)


def db_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / "jobs.db"
