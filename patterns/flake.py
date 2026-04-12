"""Nix flake modeling patterns."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SystemPlatform(str, Enum):
    X86_64_LINUX = "x86_64-linux"
    AARCH64_LINUX = "aarch64-linux"
    X86_64_DARWIN = "x86_64-darwin"
    AARCH64_DARWIN = "aarch64-darwin"

    def is_linux(self) -> bool:
        return "linux" in self.value

    def is_darwin(self) -> bool:
        return "darwin" in self.value

    def is_arm(self) -> bool:
        return "aarch64" in self.value


class FlakeOutputType(str, Enum):
    PACKAGE = "packages"
    DEV_SHELL = "devShells"
    APP = "apps"
    OVERLAY = "overlays"
    MODULE = "nixosModules"
    TEMPLATE = "templates"
    CHECK = "checks"


@dataclass
class FlakeInput:
    name: str
    url: str
    follows: list[str] = field(default_factory=list)
    flake: bool = True

    def to_nix(self) -> str:
        lines = [f'{self.name}.url = "{self.url}";']
        lines.extend(f'{self.name}.inputs.{f}.follows = "{f}";' for f in self.follows)
        return "\n".join(lines)

    def is_nixpkgs(self) -> bool:
        return "nixpkgs" in self.url


@dataclass
class FlakeOutput:
    output_type: FlakeOutputType
    name: str
    systems: list[SystemPlatform] = field(default_factory=list)
    description: str = ""

    def per_system(self) -> bool:
        return len(self.systems) > 0

    def supports_platform(self, platform: SystemPlatform) -> bool:
        return not self.systems or platform in self.systems


@dataclass
class NixFlake:
    description: str
    inputs: list[FlakeInput] = field(default_factory=list)
    outputs: list[FlakeOutput] = field(default_factory=list)
    supported_systems: list[SystemPlatform] = field(
        default_factory=lambda: [
            SystemPlatform.X86_64_LINUX,
            SystemPlatform.AARCH64_LINUX,
        ]
    )

    def add_input(self, inp: FlakeInput) -> NixFlake:
        self.inputs.append(inp)
        return self

    def add_output(self, out: FlakeOutput) -> NixFlake:
        self.outputs.append(out)
        return self

    def has_dev_shell(self) -> bool:
        return any(o.output_type == FlakeOutputType.DEV_SHELL for o in self.outputs)

    def nixpkgs_input(self) -> FlakeInput | None:
        return next((i for i in self.inputs if i.is_nixpkgs()), None)

    def input_count(self) -> int:
        return len(self.inputs)

    def output_count(self) -> int:
        return len(self.outputs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "inputs": [i.name for i in self.inputs],
            "outputs": [o.name for o in self.outputs],
            "systems": [s.value for s in self.supported_systems],
        }


class NixFlakeBuilder:
    def __init__(self, description: str) -> None:
        self._description = description
        self._inputs: list[FlakeInput] = []
        self._outputs: list[FlakeOutput] = []
        self._systems: list[SystemPlatform] = [SystemPlatform.X86_64_LINUX]

    def input(self, name: str, url: str) -> NixFlakeBuilder:
        self._inputs.append(FlakeInput(name=name, url=url))
        return self

    def dev_shell(self, name: str = "default") -> NixFlakeBuilder:
        self._outputs.append(
            FlakeOutput(FlakeOutputType.DEV_SHELL, name, self._systems)
        )
        return self

    def package(self, name: str) -> NixFlakeBuilder:
        self._outputs.append(FlakeOutput(FlakeOutputType.PACKAGE, name, self._systems))
        return self

    def systems(self, *platforms: SystemPlatform) -> NixFlakeBuilder:
        self._systems = list(platforms)
        return self

    def build(self) -> NixFlake:
        return NixFlake(
            description=self._description,
            inputs=list(self._inputs),
            outputs=list(self._outputs),
            supported_systems=list(self._systems),
        )
