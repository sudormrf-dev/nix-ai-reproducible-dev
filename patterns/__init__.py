"""Nix patterns for reproducible AI development environments."""

from __future__ import annotations

from patterns.derivation import (
    BuildSystem,
    Derivation,
    DerivationBuilder,
    DerivationOutput,
    NixHash,
    NixHashAlgorithm,
)
from patterns.environment import (
    AIEnvConfig,
    CudaVersion,
    EnvLayer,
    PythonEnvSpec,
    ReproducibilityReport,
    build_ai_env,
)
from patterns.flake import (
    FlakeInput,
    FlakeOutput,
    FlakeOutputType,
    NixFlake,
    NixFlakeBuilder,
    SystemPlatform,
)
from patterns.lockfile import (
    LockEntry,
    LockFile,
    LockFileValidator,
    LockStatus,
    hash_derivation,
)

__all__ = [
    "AIEnvConfig",
    "BuildSystem",
    "CudaVersion",
    "Derivation",
    "DerivationBuilder",
    "DerivationOutput",
    "EnvLayer",
    "FlakeInput",
    "FlakeOutput",
    "FlakeOutputType",
    "LockEntry",
    "LockFile",
    "LockFileValidator",
    "LockStatus",
    "NixFlake",
    "NixFlakeBuilder",
    "NixHash",
    "NixHashAlgorithm",
    "PythonEnvSpec",
    "ReproducibilityReport",
    "SystemPlatform",
    "build_ai_env",
    "hash_derivation",
]
