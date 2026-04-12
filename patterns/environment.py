"""AI environment specification patterns for Nix."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CudaVersion(str, Enum):
    NONE = "none"
    CUDA_11 = "11"
    CUDA_12 = "12"
    CUDA_12_1 = "12.1"
    CUDA_12_4 = "12.4"

    def is_enabled(self) -> bool:
        return self != CudaVersion.NONE

    def major(self) -> int:
        if not self.is_enabled():
            return 0
        return int(self.value.split(".")[0])


class EnvLayer(str, Enum):
    BASE = "base"
    PYTHON = "python"
    CUDA = "cuda"
    ML_FRAMEWORK = "ml_framework"
    DEV_TOOLS = "dev_tools"
    CUSTOM = "custom"

    def is_optional(self) -> bool:
        return self in {EnvLayer.CUDA, EnvLayer.ML_FRAMEWORK, EnvLayer.CUSTOM}


@dataclass
class PythonEnvSpec:
    python_version: str = "3.12"
    packages: list[str] = field(default_factory=list)
    extras: dict[str, list[str]] = field(default_factory=dict)
    venv_tool: str = "venv"

    def add_package(self, name: str) -> PythonEnvSpec:
        self.packages.append(name)
        return self

    def package_count(self) -> int:
        return len(self.packages)

    def has_ml_packages(self) -> bool:
        ml = {"torch", "tensorflow", "jax", "transformers", "numpy"}
        return bool(ml & set(self.packages))

    def to_nix_packages(self) -> list[str]:
        return [f"python3Packages.{p.replace('-', '_')}" for p in self.packages]


@dataclass
class AIEnvConfig:
    name: str
    python_spec: PythonEnvSpec = field(default_factory=PythonEnvSpec)
    cuda: CudaVersion = CudaVersion.NONE
    layers: list[EnvLayer] = field(
        default_factory=lambda: [EnvLayer.BASE, EnvLayer.PYTHON]
    )
    system_packages: list[str] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)
    pinned_nixpkgs: str = ""

    def add_layer(self, layer: EnvLayer) -> AIEnvConfig:
        if layer not in self.layers:
            self.layers.append(layer)
        return self

    def has_cuda(self) -> bool:
        return self.cuda.is_enabled()

    def is_pinned(self) -> bool:
        return bool(self.pinned_nixpkgs)

    def layer_count(self) -> int:
        return len(self.layers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "python": self.python_spec.python_version,
            "cuda": self.cuda.value,
            "layers": [layer.value for layer in self.layers],
            "pinned": self.is_pinned(),
            "package_count": self.python_spec.package_count(),
        }


@dataclass
class ReproducibilityReport:
    env_name: str
    is_pinned: bool
    has_lock_file: bool
    hash_verified: bool
    impure_inputs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def is_reproducible(self) -> bool:
        return (
            self.is_pinned
            and self.has_lock_file
            and self.hash_verified
            and not self.impure_inputs
        )

    def score(self) -> int:
        pts = 0
        if self.is_pinned:
            pts += 30
        if self.has_lock_file:
            pts += 30
        if self.hash_verified:
            pts += 30
        pts -= len(self.impure_inputs) * 10
        return max(0, min(100, pts))

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def to_dict(self) -> dict[str, Any]:
        return {
            "env": self.env_name,
            "reproducible": self.is_reproducible(),
            "score": self.score(),
            "warnings": self.warnings,
        }


def build_ai_env(
    name: str, packages: list[str], cuda: CudaVersion = CudaVersion.NONE
) -> AIEnvConfig:
    spec = PythonEnvSpec(packages=packages)
    cfg = AIEnvConfig(name=name, python_spec=spec, cuda=cuda)
    if cuda.is_enabled():
        cfg.add_layer(EnvLayer.CUDA)
    if spec.has_ml_packages():
        cfg.add_layer(EnvLayer.ML_FRAMEWORK)
    return cfg
