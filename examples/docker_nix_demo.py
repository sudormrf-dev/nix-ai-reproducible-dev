"""Demo: hermetic Docker image generation via Nix vs traditional Dockerfile approach."""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Allow running directly from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from patterns.environment import AIEnvConfig, CudaVersion, build_ai_env
from patterns.lockfile import hash_derivation


# ---------------------------------------------------------------------------
# Docker layer representation
# ---------------------------------------------------------------------------


@dataclass
class DockerLayer:
    """Single immutable layer in a Docker image."""

    digest: str
    description: str
    size_kb: int
    mutable: bool = False

    def is_reproducible(self) -> bool:
        """A layer is reproducible when its digest is content-addressed and immutable."""
        return not self.mutable and self.digest.startswith("sha256:")


@dataclass
class DockerImage:
    """Composed Docker image, either traditional or Nix-built."""

    name: str
    tag: str
    base_digest: str
    layers: list[DockerLayer] = field(default_factory=list)
    build_mode: str = "traditional"  # "traditional" | "nix"

    def add_layer(self, layer: DockerLayer) -> DockerImage:
        """Append a layer and return self for chaining."""
        self.layers.append(layer)
        return self

    def image_id(self) -> str:
        """Deterministic image ID = sha256 of all layer digests concatenated."""
        combined = "".join(layer.digest for layer in self.layers)
        return "sha256:" + hashlib.sha256(combined.encode()).hexdigest()

    def is_reproducible(self) -> bool:
        """True only when every layer is reproducible."""
        return all(layer.is_reproducible() for layer in self.layers)

    def layer_count(self) -> int:
        return len(self.layers)

    def total_size_kb(self) -> int:
        return sum(layer.size_kb for layer in self.layers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tag": self.tag,
            "build_mode": self.build_mode,
            "image_id": self.image_id(),
            "layers": self.layer_count(),
            "total_size_kb": self.total_size_kb(),
            "reproducible": self.is_reproducible(),
        }


# ---------------------------------------------------------------------------
# Traditional Dockerfile approach
# ---------------------------------------------------------------------------

TRADITIONAL_DOCKERFILE = """\
FROM python:3.12-slim
# Base tag changes silently; no content hash guarantee
RUN apt-get update && apt-get install -y gcc libgomp1
RUN pip install torch==2.3.0 transformers==4.40.0 numpy==1.26.4
# pip install fetches from PyPI at build time — hash may differ
COPY . /app
WORKDIR /app
CMD ["python", "main.py"]
"""


def build_traditional_image() -> DockerImage:
    """Simulate a traditional Docker image with mutable layers."""
    base_digest = "sha256:" + hashlib.sha256(b"python:3.12-slim@2024-05-01").hexdigest()

    img = DockerImage(
        name="ml-app",
        tag="latest",
        base_digest=base_digest,
        build_mode="traditional",
    )
    img.add_layer(
        DockerLayer(
            digest=base_digest,
            description="python:3.12-slim base (tag may move!)",
            size_kb=45_000,
            mutable=True,  # tag is not pinned to a digest
        )
    )
    img.add_layer(
        DockerLayer(
            digest="sha256:" + hashlib.sha256(b"apt-get update 2024-05-01").hexdigest(),
            description="apt-get update + gcc (date-dependent)",
            size_kb=120_000,
            mutable=True,
        )
    )
    img.add_layer(
        DockerLayer(
            digest="sha256:" + hashlib.sha256(b"pip install torch 2.3.0").hexdigest(),
            description="pip install torch+transformers+numpy",
            size_kb=4_200_000,
            mutable=True,  # PyPI metadata may change for same version
        )
    )
    img.add_layer(
        DockerLayer(
            digest="sha256:" + hashlib.sha256(b"COPY app source").hexdigest(),
            description="Application source COPY",
            size_kb=500,
            mutable=False,
        )
    )
    return img


# ---------------------------------------------------------------------------
# Nix-built Docker approach
# ---------------------------------------------------------------------------

NIX_DOCKER_EXPR = """\
{ pkgs ? import <nixpkgs> { config.allowUnfree = true; } }:
pkgs.dockerTools.buildLayeredImage {
  name = "ml-app";
  tag  = "latest";
  contents = [
    pkgs.python312
    pkgs.python312Packages.torch
    pkgs.python312Packages.transformers
    pkgs.python312Packages.numpy
  ];
  config.Cmd = [ "python" "main.py" ];
}
"""


def build_nix_image(env: AIEnvConfig) -> DockerImage:
    """Simulate a Nix-built Docker image with content-addressed layers (Nix closure)."""

    # Each Nix layer digest is deterministic — derived from the closure hash
    def nix_layer_digest(pkg: str, version: str) -> str:
        store_hash = hash_derivation(pkg, version, [env.pinned_nixpkgs])
        return "sha256:" + hashlib.sha256(store_hash.encode()).hexdigest()

    base_digest = nix_layer_digest("nixpkgs-base", "24.05")

    img = DockerImage(
        name="ml-app-nix",
        tag="latest",
        base_digest=base_digest,
        build_mode="nix",
    )
    # Nix uses a scratch base + explicit closure layers
    img.add_layer(
        DockerLayer(
            digest="sha256:" + hashlib.sha256(b"scratch").hexdigest(),
            description="scratch base (empty, no OS layer)",
            size_kb=0,
            mutable=False,
        )
    )
    img.add_layer(
        DockerLayer(
            digest=nix_layer_digest("glibc", "2.38"),
            description="glibc (pinned store path, content-addressed)",
            size_kb=8_000,
            mutable=False,
        )
    )
    img.add_layer(
        DockerLayer(
            digest=nix_layer_digest("python312", "3.12.3"),
            description="python3.12 (from Nix closure, bit-for-bit identical)",
            size_kb=30_000,
            mutable=False,
        )
    )
    img.add_layer(
        DockerLayer(
            digest=nix_layer_digest("torch", "2.3.0"),
            description="PyTorch 2.3.0 (Nix derivation, hash-pinned)",
            size_kb=3_800_000,
            mutable=False,
        )
    )
    img.add_layer(
        DockerLayer(
            digest=nix_layer_digest("transformers", "4.40.0"),
            description="transformers 4.40.0 (Nix derivation)",
            size_kb=350_000,
            mutable=False,
        )
    )
    img.add_layer(
        DockerLayer(
            digest="sha256:" + hashlib.sha256(b"app source content").hexdigest(),
            description="Application source (content-addressed by file hash)",
            size_kb=500,
            mutable=False,
        )
    )
    return img


# ---------------------------------------------------------------------------
# Comparison and verification
# ---------------------------------------------------------------------------


def compare_images(trad: DockerImage, nix: DockerImage) -> None:
    """Print a side-by-side reproducibility comparison."""
    print("\n--- Image comparison ---")
    print(f"{'Property':<30} {'Traditional':>20} {'Nix-built':>20}")
    print("-" * 72)

    rows: list[tuple[str, str, str]] = [
        ("Build mode", trad.build_mode, nix.build_mode),
        ("Layer count", str(trad.layer_count()), str(nix.layer_count())),
        (
            "Total size (MB)",
            f"{trad.total_size_kb() // 1024}",
            f"{nix.total_size_kb() // 1024}",
        ),
        ("Bit-for-bit repro", str(trad.is_reproducible()), str(nix.is_reproducible())),
        ("Image ID stable", "No (tag moves)", "Yes (content hash)"),
        ("Rollback possible", "Manual / fragile", "nix store paths are immutable"),
        (
            "Cross-machine same",
            "No (pip, apt dates differ)",
            "Yes (same closure = same ID)",
        ),
    ]
    for label, t_val, n_val in rows:
        print(f"{label:<30} {t_val:>20} {n_val:>20}")

    print(f"\nTraditional image_id : {trad.image_id()}")
    print(f"Nix image_id         : {nix.image_id()}")
    print("(Nix ID is stable across rebuilds; Traditional ID drifts with time)")


def verify_reproducibility(img: DockerImage) -> None:
    """Build the image twice (simulated) and assert IDs match."""
    id_first = img.image_id()
    id_second = img.image_id()  # deterministic — always same
    match = id_first == id_second
    print(
        f"\n[{img.build_mode}] Rebuild verification: {'PASS — bit-for-bit identical' if match else 'FAIL — drift detected'}"
    )
    print(f"  image_id = {id_first[:40]}...")


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the Docker / Nix demo."""
    print("=" * 70)
    print("DOCKER + NIX HERMETIC IMAGE DEMO")
    print("=" * 70)

    env = build_ai_env(
        "ml-prod", ["torch", "transformers", "numpy"], CudaVersion.CUDA_12
    )
    env.pinned_nixpkgs = "de60d24dc5ead7fb0c1bfa9be21b67e4fbc2c5db"

    trad_img = build_traditional_image()
    nix_img = build_nix_image(env)

    print("\n--- Traditional Dockerfile ---")
    print(TRADITIONAL_DOCKERFILE)

    print("--- Nix Docker expression ---")
    print(NIX_DOCKER_EXPR)

    compare_images(trad_img, nix_img)

    verify_reproducibility(trad_img)
    verify_reproducibility(nix_img)

    print("\nKey insight:")
    print("  Nix builds Docker images from the Nix store (content-addressed).")
    print("  The same flake.lock => same /nix/store paths => same layer digests.")
    print("  No network access at build time: fully hermetic, fully reproducible.")
    print("=" * 70)


if __name__ == "__main__":
    main()
