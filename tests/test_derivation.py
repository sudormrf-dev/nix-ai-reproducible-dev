"""Tests for derivation.py."""

from __future__ import annotations

from patterns.derivation import (
    BuildSystem,
    Derivation,
    DerivationBuilder,
    DerivationOutput,
    NixHash,
    NixHashAlgorithm,
)


class TestNixHash:
    def test_sri_string(self):
        h = NixHash(NixHashAlgorithm.SHA256, "a" * 64)
        assert h.sri_string() == f"sha256-{'a' * 64}"

    def test_valid_length_sha256(self):
        h = NixHash(NixHashAlgorithm.SHA256, "a" * 64)
        assert h.is_valid_length() is True

    def test_invalid_length(self):
        h = NixHash(NixHashAlgorithm.SHA256, "short")
        assert h.is_valid_length() is False

    def test_from_content(self):
        h = NixHash.from_content("hello")
        assert len(h.value) == 64
        assert h.algorithm == NixHashAlgorithm.SHA256

    def test_from_content_sha512(self):
        h = NixHash.from_content("hello", NixHashAlgorithm.SHA512)
        assert len(h.value) == 128

    def test_from_content_md5(self):
        h = NixHash.from_content("hello", NixHashAlgorithm.MD5)
        assert len(h.value) == 32


class TestDerivationOutput:
    def test_fixed_output_with_hash(self):
        h = NixHash(NixHashAlgorithm.SHA256, "a" * 64)
        o = DerivationOutput("out", "/nix/store/x", hash=h)
        assert o.is_fixed_output() is True

    def test_not_fixed_without_hash(self):
        o = DerivationOutput("out", "/nix/store/x")
        assert o.is_fixed_output() is False


class TestDerivation:
    def test_store_path_format(self):
        d = Derivation("mylib", "1.0")
        assert d.store_path().startswith("/nix/store/")
        assert "mylib" in d.store_path()

    def test_not_reproducible_without_hash(self):
        d = Derivation("mylib", "1.0")
        assert d.is_reproducible() is False

    def test_reproducible_with_hash(self):
        h = NixHash.from_content("src")
        d = Derivation("mylib", "1.0", src_hash=h)
        assert d.is_reproducible() is True

    def test_add_build_input(self):
        d = Derivation("lib", "1.0")
        d.add_build_input("openssl")
        assert "openssl" in d.build_inputs

    def test_add_input_returns_self(self):
        d = Derivation("lib", "1.0")
        assert d.add_build_input("x") is d

    def test_to_dict(self):
        d = Derivation("lib", "1.0")
        dd = d.to_dict()
        assert dd["name"] == "lib"
        assert "reproducible" in dd

    def test_to_nix_expr(self):
        d = Derivation("lib", "1.0", build_system=BuildSystem.PYTHON)
        expr = d.to_nix_expr()
        assert "lib" in expr


class TestDerivationBuilder:
    def test_build(self):
        d = DerivationBuilder("mylib", "2.0").build()
        assert d.name == "mylib"
        assert d.version == "2.0"

    def test_build_system(self):
        d = DerivationBuilder("x", "1").build_system(BuildSystem.PYTHON).build()
        assert d.build_system == BuildSystem.PYTHON

    def test_src_hash(self):
        h = NixHash.from_content("src")
        d = DerivationBuilder("x", "1").src_hash(h).build()
        assert d.is_reproducible() is True

    def test_with_input(self):
        d = DerivationBuilder("x", "1").with_input("zlib").build()
        assert "zlib" in d.build_inputs

    def test_chaining(self):
        b = DerivationBuilder("x", "1")
        assert b.with_input("y") is b
