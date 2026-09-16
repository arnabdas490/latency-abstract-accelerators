from __future__ import annotations

from dataclasses import dataclass


class GeneratorElaborationError(Exception):
    """Base error for generator-elaboration failures."""


@dataclass(frozen=True)
class RTLArtifact:
    """
    Physical RTL artifact produced by generator elaboration.

    Multiple logical generator results may refer to the same physical
    source file while identifying different RTL modules within it.
    """

    path: str
    module: str
    sha256: str

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError(
                "RTL artifact path must be non-empty."
            )

        if not self.module:
            raise ValueError(
                "RTL module name must be non-empty."
            )

        if not self.sha256:
            raise ValueError(
                "RTL artifact SHA256 must be non-empty."
            )

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "module": self.module,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class GeneratorResult:
    """
    Logical result of elaborating one GeneratorDecl.

    This object is the semantic bridge between generator-specific
    mechanics and the latency-abstract compiler.

    The resolver should eventually receive timing facts derived from
    GeneratorResult objects rather than reading generator configuration
    files itself.
    """

    instance: str
    generator: str
    kernel: str
    latency_var: str
    latency: int
    rtl: RTLArtifact

    def __post_init__(self) -> None:
        if not self.instance:
            raise ValueError(
                "Generator-result instance must be non-empty."
            )

        if not self.generator:
            raise ValueError(
                "Generator-result generator must be non-empty."
            )

        if not self.kernel:
            raise ValueError(
                "Generator-result kernel must be non-empty."
            )

        if not self.latency_var:
            raise ValueError(
                "Generator-result latency variable must be non-empty."
            )

        if not isinstance(self.latency, int):
            raise TypeError(
                "Generator-result latency must be an integer."
            )

        if self.latency < 1:
            raise ValueError(
                "Generator-result latency must be at least one cycle."
            )

    def to_dict(self) -> dict:
        return {
            "instance": self.instance,
            "generator": self.generator,
            "kernel": self.kernel,
            "latency_var": self.latency_var,
            "latency": self.latency,
            "rtl": self.rtl.to_dict(),
        }


@dataclass(frozen=True)
class ElaborationResult:
    """
    Complete set of logical generator results for one program
    elaboration.

    V1.1 initially assumes each generator instance and each latency
    variable are produced exactly once.
    """

    generators: tuple[GeneratorResult, ...]

    def __post_init__(self) -> None:
        if not self.generators:
            raise ValueError(
                "Elaboration result cannot be empty."
            )

        instances = [
            result.instance
            for result in self.generators
        ]

        if len(instances) != len(set(instances)):
            raise ValueError(
                "Generator-result instances must be unique."
            )

        latency_vars = [
            result.latency_var
            for result in self.generators
        ]

        if len(latency_vars) != len(set(latency_vars)):
            raise ValueError(
                "Each latency variable must be produced exactly once."
            )

    def by_instance(self) -> dict[str, GeneratorResult]:
        return {
            result.instance: result
            for result in self.generators
        }

    def by_latency_var(self) -> dict[str, GeneratorResult]:
        return {
            result.latency_var: result
            for result in self.generators
        }

    def to_dict(self) -> dict:
        return {
            "generators": [
                result.to_dict()
                for result in self.generators
            ]
        }
