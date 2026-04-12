"""Tests for lockfile.py."""

from __future__ import annotations

from patterns.lockfile import (
    LockEntry,
    LockFile,
    LockFileValidator,
    LockStatus,
    hash_derivation,
)


class TestLockEntry:
    def test_pinned(self):
        e = LockEntry("nixpkgs", "github:NixOS/nixpkgs", "abc123", "sha256-xyz")
        assert e.is_pinned() is True

    def test_not_pinned_no_rev(self):
        e = LockEntry("nixpkgs", "github:NixOS/nixpkgs", "", "sha256-xyz")
        assert e.is_pinned() is False

    def test_to_dict(self):
        e = LockEntry("nixpkgs", "url", "rev", "hash")
        d = e.to_dict()
        assert d["name"] == "nixpkgs"


class TestHashDerivation:
    def test_deterministic(self):
        h1 = hash_derivation("mylib", "1.0", ["openssl", "zlib"])
        h2 = hash_derivation("mylib", "1.0", ["zlib", "openssl"])
        assert h1 == h2

    def test_different_versions_differ(self):
        h1 = hash_derivation("mylib", "1.0", [])
        h2 = hash_derivation("mylib", "2.0", [])
        assert h1 != h2

    def test_length(self):
        h = hash_derivation("x", "1", [])
        assert len(h) == 32


class TestLockFile:
    def test_add_and_get(self):
        lf = LockFile()
        e = LockEntry("nixpkgs", "url", "rev", "hash")
        lf.add(e)
        assert lf.get("nixpkgs") is e

    def test_get_missing(self):
        assert LockFile().get("missing") is None

    def test_entry_count(self):
        lf = LockFile()
        lf.add(LockEntry("a", "u", "r", "h"))
        lf.add(LockEntry("b", "u", "r", "h"))
        assert lf.entry_count() == 2

    def test_is_complete(self):
        lf = LockFile()
        lf.add(LockEntry("nixpkgs", "u", "r", "h"))
        assert lf.is_complete(["nixpkgs"]) is True
        assert lf.is_complete(["nixpkgs", "missing"]) is False

    def test_all_pinned(self):
        lf = LockFile()
        lf.add(LockEntry("a", "u", "r", "h"))
        assert lf.all_pinned() is True

    def test_not_all_pinned(self):
        lf = LockFile()
        lf.add(LockEntry("a", "u", "", "h"))
        assert lf.all_pinned() is False

    def test_add_returns_self(self):
        lf = LockFile()
        assert lf.add(LockEntry("a", "u", "r", "h")) is lf

    def test_to_dict(self):
        lf = LockFile(version=7)
        d = lf.to_dict()
        assert d["version"] == 7


class TestLockFileValidator:
    def test_valid_lock(self):
        lf = LockFile()
        lf.add(LockEntry("nixpkgs", "u", "abc", "sha256-xyz"))
        v = LockFileValidator(lf)
        assert v.is_valid(["nixpkgs"]) is True

    def test_missing_entry(self):
        v = LockFileValidator(LockFile())
        issues = v.validate(["nixpkgs"])
        assert any("nixpkgs" in i for i in issues)

    def test_unpinned_entry(self):
        lf = LockFile()
        lf.add(LockEntry("nixpkgs", "u", "", ""))
        v = LockFileValidator(lf)
        issues = v.validate(["nixpkgs"])
        assert len(issues) > 0

    def test_status_locked(self):
        lf = LockFile()
        lf.add(LockEntry("nixpkgs", "u", "r", "h"))
        v = LockFileValidator(lf)
        assert v.status(["nixpkgs"]) == LockStatus.LOCKED

    def test_status_missing(self):
        v = LockFileValidator(LockFile())
        assert v.status(["nixpkgs"]) == LockStatus.MISSING

    def test_status_invalid(self):
        lf = LockFile()
        lf.add(LockEntry("nixpkgs", "u", "", ""))
        v = LockFileValidator(lf)
        assert v.status(["nixpkgs"]) == LockStatus.INVALID
