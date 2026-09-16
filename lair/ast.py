from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias


# ---------------------------------------------------------------------------
# Timing expressions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimingVar:
    """A symbolic timing variable whose value may be unresolved."""

    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Timing variable name must be non-empty.")

    def to_dict(self) -> dict:
        return {
            "kind": "timing_var",
            "name": self.name,
        }


@dataclass(frozen=True)
class TimingConst:
    """A concrete integer timing value."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("Timing constants must be non-negative.")

    def to_dict(self) -> dict:
        return {
            "kind": "timing_const",
            "value": self.value,
        }


@dataclass(frozen=True)
class TimingMax:
    """Maximum of two timing expressions."""

    left: TimingExpr
    right: TimingExpr

    def to_dict(self) -> dict:
        return {
            "kind": "timing_max",
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }


TimingExpr: TypeAlias = TimingVar | TimingConst | TimingMax


# ---------------------------------------------------------------------------
# Symbolic timing definitions and constraints
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimingBinding:
    """
    Defines a symbolic timing variable in terms of a timing expression.

    Example:
        T = max(L_A, L_B)
    """

    target: TimingVar
    expr: TimingExpr

    def to_dict(self) -> dict:
        return {
            "kind": "timing_binding",
            "target": self.target.to_dict(),
            "expr": self.expr.to_dict(),
        }


ConstraintOp: TypeAlias = Literal["<=", ">=", "=="]


@dataclass(frozen=True)
class TimingConstraint:
    """A symbolic timing relationship that must hold after resolution."""

    name: str
    left: TimingExpr
    op: ConstraintOp
    right: TimingExpr

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Constraint name must be non-empty.")

        if self.op not in {"<=", ">=", "=="}:
            raise ValueError(f"Unsupported constraint operator: {self.op}")

    def to_dict(self) -> dict:
        return {
            "kind": "timing_constraint",
            "name": self.name,
            "left": self.left.to_dict(),
            "op": self.op,
            "right": self.right.to_dict(),
        }


# ---------------------------------------------------------------------------
# Generated components
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GeneratorDecl:
    """
    Declares a generated hardware component.

    The component's concrete latency is intentionally absent here.
    Instead, generator elaboration will eventually bind latency_var.
    """

    instance: str
    generator: str
    kernel: str
    latency_var: TimingVar

    def __post_init__(self) -> None:
        if not self.instance:
            raise ValueError("Generator instance name must be non-empty.")
        if not self.generator:
            raise ValueError("Generator name must be non-empty.")
        if not self.kernel:
            raise ValueError("Kernel name must be non-empty.")

    def to_dict(self) -> dict:
        return {
            "kind": "generator_decl",
            "instance": self.instance,
            "generator": self.generator,
            "kernel": self.kernel,
            "latency_var": self.latency_var.to_dict(),
        }


# ---------------------------------------------------------------------------
# Accelerator control
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Invoke:
    """Invoke a generated component with symbolic timing."""

    component: str
    args: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.component:
            raise ValueError("Invoke component must be non-empty.")

    def to_dict(self) -> dict:
        return {
            "kind": "invoke",
            "component": self.component,
            "args": list(self.args),
        }


@dataclass(frozen=True)
class StaticPar:
    """
    A statically composed parallel region.

    At the symbolic stage, its exact duration may still be unresolved.
    """

    invokes: tuple[Invoke, ...]

    def __post_init__(self) -> None:
        if not self.invokes:
            raise ValueError("Static parallel region cannot be empty.")

    def to_dict(self) -> dict:
        return {
            "kind": "static_par",
            "invokes": [
                invoke.to_dict()
                for invoke in self.invokes
            ],
        }


# ---------------------------------------------------------------------------
# Symbolic program
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SymbolicProgram:
    """
    Complete latency-abstract program before generator timing is known.
    """

    generators: tuple[GeneratorDecl, ...]
    bindings: tuple[TimingBinding, ...]
    constraints: tuple[TimingConstraint, ...]
    body: StaticPar

    def __post_init__(self) -> None:
        generator_names = [
            generator.instance
            for generator in self.generators
        ]

        if len(generator_names) != len(set(generator_names)):
            raise ValueError("Generator instance names must be unique.")

        binding_names = [
            binding.target.name
            for binding in self.bindings
        ]

        if len(binding_names) != len(set(binding_names)):
            raise ValueError("Timing binding targets must be unique.")

        declared = set(generator_names)

        for invoke in self.body.invokes:
            if invoke.component not in declared:
                raise ValueError(
                    "Invoke references undeclared component: "
                    f"{invoke.component}"
                )

    def to_dict(self) -> dict:
        """
        Canonical structural representation.

        Concrete generator timing cannot appear here unless somebody
        explicitly encoded it as a TimingConst in the source IR.
        """

        return {
            "kind": "symbolic_program",
            "generators": [
                generator.to_dict()
                for generator in self.generators
            ],
            "bindings": [
                binding.to_dict()
                for binding in self.bindings
            ],
            "constraints": [
                constraint.to_dict()
                for constraint in self.constraints
            ],
            "body": self.body.to_dict(),
        }
