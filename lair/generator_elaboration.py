from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
from pathlib import Path

from lair.ast import SymbolicProgram
from lair.environment import TimingEnvironment


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


@dataclass(frozen=True)
class ToyGeneratorConfig:
    """
    Configuration supplied to the toy hardware generator.

    Values are keyed by logical generator instance, such as A and B.
    These are generator parameters, not compiler timing facts.
    """

    latencies: Mapping[str, int]

    def __post_init__(self) -> None:
        copied = dict(self.latencies)

        for instance, latency in copied.items():
            if not instance:
                raise ValueError(
                    "Toy-generator instance name must be non-empty."
                )

            if not isinstance(latency, int):
                raise TypeError(
                    f"Toy-generator latency for {instance} "
                    "must be an integer."
                )

            if latency < 1:
                raise ValueError(
                    f"Toy-generator latency for {instance} "
                    "must be at least one cycle."
                )

        object.__setattr__(
            self,
            "latencies",
            copied,
        )

    def latency_for(self, instance: str) -> int:
        try:
            return self.latencies[instance]
        except KeyError as exc:
            raise GeneratorElaborationError(
                "Missing toy-generator configuration for "
                f"instance {instance}."
            ) from exc


def _toy_sv_kernel(
    module: str,
    cycles: int,
    add_const: int,
) -> str:
    """
    Emit the same fixed-latency RTL used by the V0.8/V0.9 experiments.
    """

    return f'''
module {module} (
    input  logic        clk,
    input  logic        reset,
    input  logic        go,
    input  logic [31:0] x,
    output logic [31:0] out,
    output logic        done
);

    localparam integer LATENCY = {cycles};
    localparam integer COUNT_W =
        (LATENCY <= 1) ? 1 : $clog2(LATENCY + 1);

    logic busy;
    logic [COUNT_W-1:0] count;
    logic [31:0] saved_x;

    always_ff @(posedge clk) begin
        if (reset) begin
            busy    <= 1'b0;
            count   <= '0;
            saved_x <= '0;
            out     <= '0;
            done    <= 1'b0;
        end else begin
            done <= 1'b0;

            if (!busy && go) begin
                saved_x <= x;

                if (LATENCY == 1) begin
                    out  <= x + 32'd{add_const};
                    done <= 1'b1;
                    busy <= 1'b0;
                end else begin
                    busy  <= 1'b1;
                    count <= COUNT_W'(LATENCY - 1);
                end
            end else if (busy) begin
                if (count == 1) begin
                    out   <= saved_x + 32'd{add_const};
                    done  <= 1'b1;
                    busy  <= 1'b0;
                    count <= '0;
                end else begin
                    count <= count - 1'b1;
                end
            end
        end
    end

endmodule
'''


_TOY_KERNELS = {
    "kernel_a": {
        "module": "kernel_a_li",
        "add_const": 1,
    },
    "kernel_b": {
        "module": "kernel_b_li",
        "add_const": 2,
    },
}


def elaborate_toy_generators(
    program: SymbolicProgram,
    config: ToyGeneratorConfig,
    rtl_output: Path,
) -> ElaborationResult:
    """
    Elaborate all toy-generator declarations in a symbolic program.

    All declarations/configuration are validated before RTL is written.
    The current toy backend emits both logical kernels into one shared
    SystemVerilog artifact.
    """

    planned = []

    for decl in program.generators:
        if decl.generator != "toy_generator":
            raise GeneratorElaborationError(
                "Toy elaborator cannot handle generator "
                f"{decl.generator!r} for instance {decl.instance}."
            )

        try:
            spec = _TOY_KERNELS[decl.kernel]
        except KeyError as exc:
            raise GeneratorElaborationError(
                f"Unsupported toy kernel: {decl.kernel}"
            ) from exc

        latency = config.latency_for(
            decl.instance
        )

        planned.append(
            (
                decl,
                latency,
                spec["module"],
                spec["add_const"],
            )
        )

    if not planned:
        raise GeneratorElaborationError(
            "Program contains no toy generators to elaborate."
        )

    rtl_text = "\n".join(
        _toy_sv_kernel(
            module=module,
            cycles=latency,
            add_const=add_const,
        )
        for _, latency, module, add_const in planned
    )

    rtl_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    rtl_output.write_text(rtl_text)

    sha256 = hashlib.sha256(
        rtl_output.read_bytes()
    ).hexdigest()

    results = tuple(
        GeneratorResult(
            instance=decl.instance,
            generator=decl.generator,
            kernel=decl.kernel,
            latency_var=decl.latency_var.name,
            latency=latency,
            rtl=RTLArtifact(
                path=str(rtl_output),
                module=module,
                sha256=sha256,
            ),
        )
        for decl, latency, module, _ in planned
    )

    return ElaborationResult(
        generators=results,
    )


def timing_environment_from_elaboration(
    elaboration: ElaborationResult,
) -> TimingEnvironment:
    """
    Convert generator-produced timing facts into the compiler timing
    environment.

    This is the only V1.1 bridge from GeneratorResult latency metadata
    to the symbolic timing resolver.
    """

    return TimingEnvironment(
        {
            result.latency_var: result.latency
            for result in elaboration.generators
        }
    )
