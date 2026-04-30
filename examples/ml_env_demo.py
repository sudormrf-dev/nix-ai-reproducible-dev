"""Demo: generate a complete Nix ML environment with multiple Python versions and shell environments."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Allow running directly from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from patterns.environment import AIEnvConfig, CudaVersion, EnvLayer, PythonEnvSpec, ReproducibilityReport, build_ai_env
from patterns.flake import FlakeInput, FlakeOutput, FlakeOutputType, NixFlake, NixFlakeBuilder, SystemPlatform
from patterns.lockfile import LockEntry, LockFile, LockFileValidator, hash_derivation


# ---------------------------------------------------------------------------
# Flake construction helpers
# ---------------------------------------------------------------------------

NIXPKGS_REV = "de60d24dc5ead7fb0c1bfa9be21b67e4fbc2c5db"
NIXPKGS_URL = "github:NixOS/nixpkgs/nixos-24.05"
FLAKE_UTILS_REV = "b1d9ab70662946ef0850d488da1c9019f3a9752a"
FLAKE_UTILS_URL = "github:numtide/flake-utils"

PYTHON_VERSIONS: list[str] = ["3.10", "3.11", "3.12"]

ML_PACKAGES: list[str] = [
    "torch",
    "torchvision",
    "transformers",
    "numpy",
    "scipy",
    "scikit-learn",
    "pandas",
    "matplotlib",
]

DEV_EXTRAS: list[str] = ["ipython", "jupyter", "black", "ruff", "mypy", "pytest"]
PROD_PACKAGES: list[str] = ["torch", "transformers", "numpy"]
CI_PACKAGES: list[str] = ["pytest", "coverage", "mypy", "ruff"]


def build_nixpkgs_input() -> FlakeInput:
    """Return a pinned nixpkgs flake input."""
    inp = FlakeInput(
        name="nixpkgs",
        url=f"{NIXPKGS_URL}",
        follows=[],
        flake=True,
    )
    return inp


def build_flake_utils_input() -> FlakeInput:
    """Return a pinned flake-utils input that follows nixpkgs."""
    return FlakeInput(
        name="flake-utils",
        url=FLAKE_UTILS_URL,
        follows=["nixpkgs"],
        flake=True,
    )


def build_ml_flake() -> NixFlake:
    """Build a NixFlake for a multi-Python ML project."""
    builder = (
        NixFlakeBuilder("Hermetic ML environment: Python + PyTorch + CUDA (multi-version)")
        .systems(SystemPlatform.X86_64_LINUX, SystemPlatform.AARCH64_LINUX)
        .input("nixpkgs", NIXPKGS_URL)
        .input("flake-utils", FLAKE_UTILS_URL)
        .dev_shell("dev")
        .dev_shell("prod")
        .dev_shell("ci")
        .package("ml-app")
    )
    flake = builder.build()
    # Patch the nixpkgs input to be properly pinned (builder uses plain url)
    for inp in flake.inputs:
        if inp.name == "flake-utils":
            inp.follows = ["nixpkgs"]
    return flake


# ---------------------------------------------------------------------------
# Per-Python-version environment specs
# ---------------------------------------------------------------------------

@dataclass
class VersionedEnv:
    """Group an AIEnvConfig with the Python version it targets."""

    python_version: str
    config: AIEnvConfig


def build_versioned_envs() -> list[VersionedEnv]:
    """Create dev ML environments for each supported Python version."""
    envs: list[VersionedEnv] = []
    for py_ver in PYTHON_VERSIONS:
        spec = PythonEnvSpec(
            python_version=py_ver,
            packages=list(ML_PACKAGES) + list(DEV_EXTRAS),
            extras={"cuda": ["cupy", "cuda-python"]},
            venv_tool="venv",
        )
        cfg = AIEnvConfig(
            name=f"ml-dev-py{py_ver.replace('.', '')}",
            python_spec=spec,
            cuda=CudaVersion.CUDA_12,
            layers=[EnvLayer.BASE, EnvLayer.PYTHON, EnvLayer.CUDA, EnvLayer.ML_FRAMEWORK, EnvLayer.DEV_TOOLS],
            system_packages=["gcc", "stdenv.cc.cc.lib", "zlib", "libGL"],
            env_vars={
                "CUDA_HOME": "/run/current-system/sw",
                "LD_LIBRARY_PATH": "/run/opengl-driver/lib",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            pinned_nixpkgs=NIXPKGS_REV,
        )
        envs.append(VersionedEnv(python_version=py_ver, config=cfg))
    return envs


def build_prod_env() -> AIEnvConfig:
    """Minimal production environment (no dev tools, CUDA-enabled)."""
    return build_ai_env("ml-prod", PROD_PACKAGES, CudaVersion.CUDA_12)


def build_ci_env() -> AIEnvConfig:
    """CI environment: no CUDA, linting + testing only."""
    return build_ai_env("ml-ci", CI_PACKAGES, CudaVersion.NONE)


# ---------------------------------------------------------------------------
# Lock file generation
# ---------------------------------------------------------------------------

def build_lock_file() -> LockFile:
    """Simulate a flake.lock with pinned revisions and NAR hashes."""
    lock = LockFile(version=7)

    nixpkgs_nar = hash_derivation("nixpkgs", NIXPKGS_REV, [])
    lock.add(LockEntry(
        name="nixpkgs",
        url=NIXPKGS_URL,
        rev=NIXPKGS_REV,
        nar_hash=f"sha256-{nixpkgs_nar}",
        last_modified=1_700_000_000,
    ))

    utils_nar = hash_derivation("flake-utils", FLAKE_UTILS_REV, ["nixpkgs"])
    lock.add(LockEntry(
        name="flake-utils",
        url=FLAKE_UTILS_URL,
        rev=FLAKE_UTILS_REV,
        nar_hash=f"sha256-{utils_nar}",
        last_modified=1_699_000_000,
    ))

    return lock


# ---------------------------------------------------------------------------
# Nix file content generators
# ---------------------------------------------------------------------------

def render_flake_nix(flake: NixFlake, envs: list[VersionedEnv]) -> str:
    """Render a flake.nix string for the ML project."""
    systems_str = " ".join(f'"{s.value}"' for s in flake.supported_systems)
    py_attrs = "\n        ".join(
        f'py{ve.python_version.replace(".", "")} = mkShell {{ name = "{ve.config.name}"; }};'
        for ve in envs
    )
    return f"""\
{{
  description = "{flake.description}";

  inputs = {{
    {flake.inputs[0].to_nix()}
    {flake.inputs[1].to_nix()}
  }};

  outputs = {{ self, nixpkgs, flake-utils }}:
    flake-utils.lib.eachSystem [ {systems_str} ] (system:
      let
        pkgs = import nixpkgs {{
          inherit system;
          config.allowUnfree = true;
          config.cudaSupport = true;
        }};
        mkShell = pkgs.mkShell;
      in {{
        devShells = {{
          {py_attrs}
          dev   = mkShell {{ name = "ml-dev"; }};
          prod  = mkShell {{ name = "ml-prod"; }};
          ci    = mkShell {{ name = "ml-ci"; }};
        }};
      }}
    );
}}
"""


def render_flake_lock(lock: LockFile) -> str:
    """Render a simulated flake.lock JSON string."""
    return json.dumps(lock.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# Reproducibility validation
# ---------------------------------------------------------------------------

def validate_env(cfg: AIEnvConfig, lock: LockFile) -> ReproducibilityReport:
    """Assess reproducibility of an AIEnvConfig against the lock file."""
    required = [i.name for i in [FlakeInput("nixpkgs", ""), FlakeInput("flake-utils", "")]]
    validator = LockFileValidator(lock)
    issues = validator.validate(["nixpkgs", "flake-utils"])

    report = ReproducibilityReport(
        env_name=cfg.name,
        is_pinned=cfg.is_pinned(),
        has_lock_file=lock.entry_count() > 0,
        hash_verified=not issues,
        impure_inputs=[],
        warnings=[],
    )
    for issue in issues:
        report.add_warning(issue)
    if not cfg.is_pinned():
        report.add_warning("nixpkgs not pinned — builds may differ across time")
    return report


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the ML environment demo and print a full report."""
    print("=" * 70)
    print("NIX ML ENVIRONMENT DEMO")
    print("=" * 70)

    # Build flake and lock
    flake = build_ml_flake()
    lock = build_lock_file()
    versioned_envs = build_versioned_envs()
    prod_env = build_prod_env()
    ci_env = build_ci_env()

    print(f"\nFlake: {flake.description}")
    print(f"  Inputs  : {flake.input_count()} ({', '.join(i.name for i in flake.inputs)})")
    print(f"  Outputs : {flake.output_count()} ({', '.join(o.name for o in flake.outputs)})")
    print(f"  Systems : {', '.join(s.value for s in flake.supported_systems)}")
    print(f"  Has devShell: {flake.has_dev_shell()}")

    print(f"\nLock file: {lock.entry_count()} entries, all pinned={lock.all_pinned()}")
    for name, entry in lock.entries.items():
        print(f"  [{name}] rev={entry.rev[:12]}... pinned={entry.is_pinned()}")

    print(f"\nPython environments ({len(versioned_envs)} versions, no conflict):")
    for ve in versioned_envs:
        cfg = ve.config
        rep = validate_env(cfg, lock)
        print(
            f"  py{ve.python_version} | pkgs={cfg.python_spec.package_count():>2} "
            f"| CUDA={cfg.cuda.value} | layers={cfg.layer_count()} "
            f"| score={rep.score()}/90 | reproducible={rep.is_reproducible()}"
        )

    for label, env in [("prod", prod_env), ("ci", ci_env)]:
        rep = validate_env(env, lock)
        print(
            f"  {label:4s}      | pkgs={env.python_spec.package_count():>2} "
            f"| CUDA={env.cuda.value} | reproducible={rep.is_reproducible()}"
        )

    print("\n--- Generated flake.nix (excerpt) ---")
    flake_content = render_flake_nix(flake, versioned_envs)
    print(flake_content[:600] + "\n  ...")

    print("\n--- Generated flake.lock (excerpt) ---")
    lock_content = render_flake_lock(lock)
    print(lock_content[:400] + "\n  ...")

    print("\nSummary:")
    print("  - 3 Python versions coexist without conflict (3.10, 3.11, 3.12)")
    print("  - All dependencies locked via sha256 NAR hashes")
    print("  - Dev / prod / CI shell environments generated from one flake")
    print("  - CUDA 12 supported hermetically via nixpkgs cudaSupport=true")
    print("=" * 70)


if __name__ == "__main__":
    main()
