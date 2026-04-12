"""Nix derivation modeling patterns."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NixHashAlgorithm(str, Enum):
    SHA256 = "sha256"
    SHA512 = "sha512"
    MD5 = "md5"


class BuildSystem(str, Enum):
    STDENV = "stdenv.mkDerivation"
    PYTHON = "python3Packages.buildPythonPackage"
    RUST = "rustPlatform.buildRustPackage"
    GO = "buildGoModule"
    CMAKE = "cmake"
    MESON = "meson"


@dataclass
class NixHash:
    algorithm: NixHashAlgorithm
    value: str

    def sri_string(self) -> str:
        return f"{self.algorithm.value}-{self.value}"

    def is_valid_length(self) -> bool:
        expected = {
            NixHashAlgorithm.SHA256: 64,
            NixHashAlgorithm.SHA512: 128,
            NixHashAlgorithm.MD5: 32,
        }
        return len(self.value) == expected.get(self.algorithm, 0)

    @classmethod
    def from_content(
        cls, content: str, algorithm: NixHashAlgorithm = NixHashAlgorithm.SHA256
    ) -> NixHash:
        if algorithm == NixHashAlgorithm.SHA512:
            h = hashlib.sha512(content.encode()).hexdigest()
        elif algorithm == NixHashAlgorithm.MD5:
            h = hashlib.md5(content.encode()).hexdigest()  # noqa: S324
        else:
            h = hashlib.sha256(content.encode()).hexdigest()
        return cls(algorithm=algorithm, value=h)


@dataclass
class DerivationOutput:
    name: str
    path: str
    hash: NixHash | None = None

    def is_fixed_output(self) -> bool:
        return self.hash is not None


@dataclass
class Derivation:
    name: str
    version: str
    build_system: BuildSystem = BuildSystem.STDENV
    src_hash: NixHash | None = None
    build_inputs: list[str] = field(default_factory=list)
    native_build_inputs: list[str] = field(default_factory=list)
    outputs: list[DerivationOutput] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    patches: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def store_path(self) -> str:
        h = hashlib.sha256(f"{self.name}-{self.version}".encode()).hexdigest()[:32]
        return f"/nix/store/{h}-{self.name}-{self.version}"

    def add_build_input(self, pkg: str) -> Derivation:
        self.build_inputs.append(pkg)
        return self

    def is_reproducible(self) -> bool:
        return self.src_hash is not None

    def to_nix_expr(self) -> str:
        return f'pkgs.{self.build_system.value} {{ name = "{self.name}"; version = "{self.version}"; }}'

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "build_system": self.build_system.value,
            "build_inputs": self.build_inputs,
            "reproducible": self.is_reproducible(),
        }


class DerivationBuilder:
    def __init__(self, name: str, version: str) -> None:
        self._name = name
        self._version = version
        self._build_system = BuildSystem.STDENV
        self._src_hash: NixHash | None = None
        self._build_inputs: list[str] = []

    def build_system(self, bs: BuildSystem) -> DerivationBuilder:
        self._build_system = bs
        return self

    def src_hash(self, h: NixHash) -> DerivationBuilder:
        self._src_hash = h
        return self

    def with_input(self, pkg: str) -> DerivationBuilder:
        self._build_inputs.append(pkg)
        return self

    def build(self) -> Derivation:
        return Derivation(
            name=self._name,
            version=self._version,
            build_system=self._build_system,
            src_hash=self._src_hash,
            build_inputs=list(self._build_inputs),
        )
