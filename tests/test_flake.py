"""Tests for flake.py."""

from __future__ import annotations

from patterns.flake import (
    FlakeInput,
    FlakeOutput,
    FlakeOutputType,
    NixFlake,
    NixFlakeBuilder,
    SystemPlatform,
)


class TestSystemPlatform:
    def test_linux(self):
        assert SystemPlatform.X86_64_LINUX.is_linux() is True
        assert SystemPlatform.X86_64_DARWIN.is_linux() is False

    def test_darwin(self):
        assert SystemPlatform.AARCH64_DARWIN.is_darwin() is True

    def test_arm(self):
        assert SystemPlatform.AARCH64_LINUX.is_arm() is True
        assert SystemPlatform.X86_64_LINUX.is_arm() is False


class TestFlakeInput:
    def test_to_nix(self):
        inp = FlakeInput("nixpkgs", "github:NixOS/nixpkgs/nixpkgs-unstable")
        nix = inp.to_nix()
        assert "nixpkgs" in nix

    def test_is_nixpkgs(self):
        inp = FlakeInput("nixpkgs", "github:NixOS/nixpkgs")
        assert inp.is_nixpkgs() is True

    def test_not_nixpkgs(self):
        inp = FlakeInput("flake-utils", "github:numtide/flake-utils")
        assert inp.is_nixpkgs() is False

    def test_follows(self):
        inp = FlakeInput(
            "home-manager", "github:nix-community/home-manager", follows=["nixpkgs"]
        )
        nix = inp.to_nix()
        assert "follows" in nix


class TestFlakeOutput:
    def test_per_system_true(self):
        o = FlakeOutput(
            FlakeOutputType.DEV_SHELL, "default", [SystemPlatform.X86_64_LINUX]
        )
        assert o.per_system() is True

    def test_per_system_false(self):
        o = FlakeOutput(FlakeOutputType.OVERLAY, "default")
        assert o.per_system() is False

    def test_supports_platform(self):
        o = FlakeOutput(FlakeOutputType.PACKAGE, "x", [SystemPlatform.X86_64_LINUX])
        assert o.supports_platform(SystemPlatform.X86_64_LINUX) is True
        assert o.supports_platform(SystemPlatform.AARCH64_DARWIN) is False

    def test_supports_all_when_empty(self):
        o = FlakeOutput(FlakeOutputType.OVERLAY, "x")
        assert o.supports_platform(SystemPlatform.AARCH64_DARWIN) is True


class TestNixFlake:
    def test_add_input(self):
        f = NixFlake("test")
        f.add_input(FlakeInput("nixpkgs", "github:NixOS/nixpkgs"))
        assert f.input_count() == 1

    def test_has_dev_shell(self):
        f = NixFlake("test")
        f.add_output(FlakeOutput(FlakeOutputType.DEV_SHELL, "default"))
        assert f.has_dev_shell() is True

    def test_no_dev_shell(self):
        f = NixFlake("test")
        assert f.has_dev_shell() is False

    def test_nixpkgs_input(self):
        f = NixFlake("test")
        inp = FlakeInput("nixpkgs", "github:NixOS/nixpkgs")
        f.add_input(inp)
        assert f.nixpkgs_input() is inp

    def test_to_dict(self):
        f = NixFlake("my AI env")
        d = f.to_dict()
        assert d["description"] == "my AI env"


class TestNixFlakeBuilder:
    def test_build(self):
        f = (
            NixFlakeBuilder("AI dev")
            .input("nixpkgs", "github:NixOS/nixpkgs")
            .dev_shell()
            .build()
        )
        assert f.has_dev_shell() is True
        assert f.input_count() == 1

    def test_package(self):
        f = NixFlakeBuilder("x").package("myApp").build()
        assert f.output_count() == 1

    def test_systems(self):
        f = (
            NixFlakeBuilder("x")
            .systems(SystemPlatform.X86_64_LINUX, SystemPlatform.AARCH64_LINUX)
            .build()
        )
        assert len(f.supported_systems) == 2

    def test_chaining(self):
        b = NixFlakeBuilder("x")
        assert b.input("n", "u") is b
