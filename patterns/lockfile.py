"""Nix lock file patterns."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LockStatus(str, Enum):
    LOCKED = "locked"
    OUTDATED = "outdated"
    MISSING = "missing"
    INVALID = "invalid"

    def is_ok(self) -> bool:
        return self == LockStatus.LOCKED


@dataclass
class LockEntry:
    name: str
    url: str
    rev: str
    nar_hash: str
    last_modified: int = 0
    flake: bool = True

    def is_pinned(self) -> bool:
        return bool(self.rev) and bool(self.nar_hash)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "rev": self.rev,
            "nar_hash": self.nar_hash,
        }


def hash_derivation(name: str, version: str, inputs: list[str]) -> str:
    content = f"{name}-{version}-{','.join(sorted(inputs))}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]


@dataclass
class LockFile:
    version: int = 7
    entries: dict[str, LockEntry] = field(default_factory=dict)

    def add(self, entry: LockEntry) -> LockFile:
        self.entries[entry.name] = entry
        return self

    def get(self, name: str) -> LockEntry | None:
        return self.entries.get(name)

    def is_complete(self, required: list[str]) -> bool:
        return all(n in self.entries for n in required)

    def entry_count(self) -> int:
        return len(self.entries)

    def all_pinned(self) -> bool:
        return all(e.is_pinned() for e in self.entries.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "nodes": {k: v.to_dict() for k, v in self.entries.items()},
        }


class LockFileValidator:
    def __init__(self, lock: LockFile) -> None:
        self._lock = lock

    def validate(self, required_inputs: list[str]) -> list[str]:
        issues: list[str] = []
        issues = [
            f"Missing lock entry: {name}"
            for name in required_inputs
            if name not in self._lock.entries
        ]
        issues += [
            f"Unpinned entry: {name}"
            for name, entry in self._lock.entries.items()
            if not entry.is_pinned()
        ]
        return issues

    def status(self, required_inputs: list[str]) -> LockStatus:
        if not self._lock.entries:
            return LockStatus.MISSING
        issues = self.validate(required_inputs)
        if issues:
            return LockStatus.INVALID
        return LockStatus.LOCKED

    def is_valid(self, required_inputs: list[str]) -> bool:
        return self.status(required_inputs).is_ok()
