from __future__ import annotations

from dataclasses import dataclass

from lair.ast import (
    StaticPar,
    SymbolicProgram,
    TimingConst,
    TimingConstraint,
    TimingExpr,
    TimingMax,
    TimingVar,
)
from lair.environment import TimingEnvironment


class ResolutionError(Exception):
    """Base class for latency-resolution failures."""


class UnboundTimingVariable(ResolutionError):
    """Raised when resolution needs a timing fact that is unavailable."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(
            f"Unbound timing variable during resolution: {name}"
        )


@dataclass(frozen=True)
class ConstraintCheck:
    name: str
    left_value: int
    op: str
    right_value: int
    passed: bool

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "left_value": self.left_value,
            "op": self.op,
            "right_value": self.right_value,
            "passed": self.passed,
        }


class ConstraintViolation(ResolutionError):
    """
    Raised when one or more symbolic timing constraints fail.
    """

    def __init__(
        self,
        checks: tuple[ConstraintCheck, ...],
    ):
        self.checks = checks
        self.failures = tuple(
            check
            for check in checks
            if not check.passed
        )

        names = ", ".join(
            failure.name
            for failure in self.failures
        )

        super().__init__(
            f"Timing constraint violation: {names}"
        )


@dataclass(frozen=True)
class ResolvedTimingBinding:
    name: str
    value: int

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
        }


@dataclass(frozen=True)
class ResolvedGenerator:
    instance: str
    generator: str
    kernel: str
    latency_var: str
    latency: int

    def to_dict(self) -> dict:
        return {
            "instance": self.instance,
            "generator": self.generator,
            "kernel": self.kernel,
            "latency_var": self.latency_var,
            "latency": self.latency,
        }


@dataclass(frozen=True)
class ResolvedInvoke:
    component: str
    args: tuple[str, ...]
    latency: int

    def to_dict(self) -> dict:
        return {
            "component": self.component,
            "args": list(self.args),
            "latency": self.latency,
        }


@dataclass(frozen=True)
class ResolvedStaticPar:
    invokes: tuple[ResolvedInvoke, ...]
    latency: int

    def to_dict(self) -> dict:
        return {
            "kind": "resolved_static_par",
            "latency": self.latency,
            "invokes": [
                invoke.to_dict()
                for invoke in self.invokes
            ],
        }


@dataclass(frozen=True)
class ResolvedProgram:
    """
    Program after all required timing facts are concrete and all
    constraints have passed.
    """

    timing_values: dict[str, int]
    generators: tuple[ResolvedGenerator, ...]
    bindings: tuple[ResolvedTimingBinding, ...]
    constraint_checks: tuple[ConstraintCheck, ...]
    body: ResolvedStaticPar

    def to_dict(self) -> dict:
        return {
            "kind": "resolved_program",
            "timing_values": dict(self.timing_values),
            "generators": [
                generator.to_dict()
                for generator in self.generators
            ],
            "bindings": [
                binding.to_dict()
                for binding in self.bindings
            ],
            "constraint_checks": [
                check.to_dict()
                for check in self.constraint_checks
            ],
            "body": self.body.to_dict(),
        }


def evaluate_expr(
    expr: TimingExpr,
    values: dict[str, int],
) -> int:
    if isinstance(expr, TimingConst):
        return expr.value

    if isinstance(expr, TimingVar):
        try:
            return values[expr.name]
        except KeyError as exc:
            raise UnboundTimingVariable(
                expr.name
            ) from exc

    if isinstance(expr, TimingMax):
        return max(
            evaluate_expr(expr.left, values),
            evaluate_expr(expr.right, values),
        )

    raise TypeError(
        f"Unsupported timing expression: {type(expr).__name__}"
    )


def evaluate_constraint(
    constraint: TimingConstraint,
    values: dict[str, int],
) -> ConstraintCheck:
    left = evaluate_expr(
        constraint.left,
        values,
    )
    right = evaluate_expr(
        constraint.right,
        values,
    )

    if constraint.op == "<=":
        passed = left <= right
    elif constraint.op == ">=":
        passed = left >= right
    elif constraint.op == "==":
        passed = left == right
    else:
        raise TypeError(
            f"Unsupported constraint operator: {constraint.op}"
        )

    return ConstraintCheck(
        name=constraint.name,
        left_value=left,
        op=constraint.op,
        right_value=right,
        passed=passed,
    )


def resolve_static_par(
    body: StaticPar,
    component_latencies: dict[str, int],
) -> ResolvedStaticPar:
    invokes = []

    for invoke in body.invokes:
        try:
            latency = component_latencies[
                invoke.component
            ]
        except KeyError as exc:
            raise ResolutionError(
                "No resolved latency for component: "
                f"{invoke.component}"
            ) from exc

        invokes.append(
            ResolvedInvoke(
                component=invoke.component,
                args=invoke.args,
                latency=latency,
            )
        )

    resolved_invokes = tuple(invokes)

    return ResolvedStaticPar(
        invokes=resolved_invokes,
        latency=max(
            invoke.latency
            for invoke in resolved_invokes
        ),
    )


def resolve_program(
    program: SymbolicProgram,
    environment: TimingEnvironment,
) -> ResolvedProgram:
    """
    Resolve a symbolic latency-abstract program.

    The input environment contains generator-produced timing facts.
    Derived timing values are computed from the symbolic IR itself.

    If any constraint fails, no ResolvedProgram is returned.
    """

    values = environment.to_dict()

    # Generator latency variables must come from the timing environment.
    component_latencies: dict[str, int] = {}

    for generator in program.generators:
        name = generator.latency_var.name

        try:
            latency = values[name]
        except KeyError as exc:
            raise UnboundTimingVariable(
                name
            ) from exc

        component_latencies[
            generator.instance
        ] = latency

    # Evaluate symbolic timing bindings in program order.
    resolved_bindings = []

    for binding in program.bindings:
        target = binding.target.name

        if target in values:
            raise ResolutionError(
                "Derived timing variable was already supplied "
                f"by the environment: {target}"
            )

        value = evaluate_expr(
            binding.expr,
            values,
        )

        values[target] = value

        resolved_bindings.append(
            ResolvedTimingBinding(
                name=target,
                value=value,
            )
        )

    # Discharge symbolic timing constraints.
    checks = tuple(
        evaluate_constraint(
            constraint,
            values,
        )
        for constraint in program.constraints
    )

    if not all(
        check.passed
        for check in checks
    ):
        raise ConstraintViolation(checks)

    resolved_generators = tuple(
        ResolvedGenerator(
            instance=generator.instance,
            generator=generator.generator,
            kernel=generator.kernel,
            latency_var=generator.latency_var.name,
            latency=component_latencies[
                generator.instance
            ],
        )
        for generator in program.generators
    )

    resolved_body = resolve_static_par(
        program.body,
        component_latencies,
    )

    return ResolvedProgram(
        timing_values=dict(values),
        generators=resolved_generators,
        bindings=tuple(resolved_bindings),
        constraint_checks=checks,
        body=resolved_body,
    )
