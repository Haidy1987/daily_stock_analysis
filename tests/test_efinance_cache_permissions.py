# -*- coding: utf-8 -*-
"""Smoke helpers for efinance cache directory permissions."""

from __future__ import annotations

from pathlib import Path


def resolve_efinance_data_dir() -> Path:
    import efinance

    return Path(efinance.__file__).resolve().parent / "data"


def test_resolve_efinance_data_dir_points_to_package_data() -> None:
    data_dir = resolve_efinance_data_dir()
    assert data_dir.name == "data"
    assert "efinance" in data_dir.as_posix()
