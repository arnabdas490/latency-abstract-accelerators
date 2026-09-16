from __future__ import annotations

from dataclasses import dataclass

from lair.ast import (
    ComponentDecl,
    Invoke,
    StaticPar,
    StaticSeq,
    SymbolicProgram,
    TimingConst,
    TimingConstraint,
    TimingExpr,
    TimingMax,
    TimingVar,
    _iter_control_invokes,
)
from lair.environment import TimingEnvironment
from lair.component_timing import (
    ComponentTimingInterface,
)
from lair.component_graph import (
    topological_component_order,
)


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
class ResolvedStaticSeq:
    steps: tuple[
        ResolvedInvoke
        | ResolvedStaticPar
        | "ResolvedStaticSeq",
        ...
    ]
    latency: int

    def to_dict(self) -> dict:
        return {
            "kind": "resolved_static_seq",
            "latency": self.latency,
            "steps": [
                step.to_dict()
                for step in self.steps
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
    body: ResolvedStaticPar | ResolvedStaticSeq

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


def _bind_control_timing(
    name: str,
    latency: int,
    values: dict[str, int],
) -> None:
    """
    Publish a timing fact inferred from control structure.

    Structural timing is compiler-derived and therefore cannot be
    overridden by generator/environment timing facts.
    """

    if name in values:
        raise ResolutionError(
            "Control-derived timing variable was already supplied: "
            f"{name}"
        )

    values[name] = latency


def resolve_control(
    control: Invoke | StaticPar | StaticSeq,
    component_latencies: dict[str, int],
    values: dict[str, int],
) -> (
    ResolvedInvoke
    | ResolvedStaticPar
    | ResolvedStaticSeq
):
    """
    Recursively infer latency from static control structure.

    Invoke:
        latency(component)

    StaticPar:
        max(child latencies)

    StaticSeq:
        sum(child latencies)
    """

    if isinstance(control, Invoke):
        try:
            latency = component_latencies[
                control.component
            ]
        except KeyError as exc:
            raise ResolutionError(
                "No resolved latency for component: "
                f"{control.component}"
            ) from exc

        return ResolvedInvoke(
            component=control.component,
            args=control.args,
            latency=latency,
        )

    if isinstance(control, StaticPar):
        resolved_invokes = tuple(
            resolve_control(
                invoke,
                component_latencies,
                values,
            )
            for invoke in control.invokes
        )

        if not all(
            isinstance(
                invoke,
                ResolvedInvoke,
            )
            for invoke in resolved_invokes
        ):
            raise ResolutionError(
                "StaticPar resolved to a non-invoke child."
            )

        latency = max(
            invoke.latency
            for invoke in resolved_invokes
        )

        if control.timing_var is not None:
            _bind_control_timing(
                control.timing_var.name,
                latency,
                values,
            )

        return ResolvedStaticPar(
            invokes=resolved_invokes,
            latency=latency,
        )

    if isinstance(control, StaticSeq):
        resolved_steps = tuple(
            resolve_control(
                step,
                component_latencies,
                values,
            )
            for step in control.steps
        )

        latency = sum(
            step.latency
            for step in resolved_steps
        )

        if control.timing_var is not None:
            _bind_control_timing(
                control.timing_var.name,
                latency,
                values,
            )

        return ResolvedStaticSeq(
            steps=resolved_steps,
            latency=latency,
        )

    raise TypeError(
        "Unsupported symbolic control node: "
        f"{type(control).__name__}"
    )



@dataclass(frozen=True)
class ResolvedComponent:
    """
    A resolved reusable user component.

    This object may retain implementation structure for lowering and
    debugging. Parents must not consume this object for timing; they
    consume only ComponentTimingInterface.
    """

    name: str
    args: tuple[str, ...]
    latency: int
    body: (
        ResolvedStaticPar
        | ResolvedStaticSeq
    )
    timing_values: dict[str, int]

    def timing_interface(
        self,
    ) -> ComponentTimingInterface:
        return ComponentTimingInterface(
            component=self.name,
            latency=self.latency,
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "args": list(self.args),
            "latency": self.latency,
            "timing_values": dict(
                self.timing_values
            ),
            "body": self.body.to_dict(),
        }


def resolve_component_control(
    control: StaticPar | StaticSeq,
    *,
    generator_latencies: dict[str, int],
    component_interfaces: dict[
        str,
        ComponentTimingInterface,
    ],
) -> tuple[
    ResolvedStaticPar | ResolvedStaticSeq,
    dict[str, int],
]:
    """
    Resolve one component body from only the timing facts visible at
    that component boundary.

    Generator leaves are supplied explicitly through generator_latencies.

    User-component calls are supplied only through
    ComponentTimingInterface objects.

    A fresh local timing namespace is used for structural timing facts;
    no global TimingEnvironment is visible here.
    """

    available: dict[str, int] = dict(
        generator_latencies
    )

    for name, interface in (
        component_interfaces.items()
    ):
        if name != interface.component:
            raise ResolutionError(
                "Component timing interface key/name mismatch: "
                f"{name} != {interface.component}"
            )

        if name in available:
            raise ResolutionError(
                "Timing source supplied as both generator "
                "and component interface: "
                f"{name}"
            )

        available[name] = interface.latency

    local_values: dict[str, int] = {}

    resolved = resolve_control(
        control,
        available,
        local_values,
    )

    if not isinstance(
        resolved,
        (
            ResolvedStaticPar,
            ResolvedStaticSeq,
        ),
    ):
        raise ResolutionError(
            "Component body must resolve to static "
            "parallel or sequential control."
        )

    return (
        resolved,
        local_values,
    )


def resolve_component_decl(
    component: ComponentDecl,
    *,
    generator_latencies: dict[str, int],
    component_interfaces: dict[
        str,
        ComponentTimingInterface,
    ],
) -> ResolvedComponent:
    """
    Resolve one reusable component and construct its concrete timing
    result without exposing its body through the public timing interface.
    """

    resolved_body, local_values = (
        resolve_component_control(
            component.body,
            generator_latencies=(
                generator_latencies
            ),
            component_interfaces=(
                component_interfaces
            ),
        )
    )

    export_name = (
        component.latency_var.name
    )

    if export_name in local_values:
        raise ResolutionError(
            "Component timing export was already "
            "derived internally: "
            f"{export_name}"
        )

    component_values = dict(
        local_values
    )

    component_values[
        export_name
    ] = resolved_body.latency

    return ResolvedComponent(
        name=component.name,
        args=component.args,
        latency=resolved_body.latency,
        body=resolved_body,
        timing_values=component_values,
    )


def resolve_static_par(
    body: StaticPar,
    component_latencies: dict[str, int],
) -> ResolvedStaticPar:
    """
    Backward-compatible V1.0 helper.

    New code should use resolve_control().
    """

    resolved = resolve_control(
        body,
        component_latencies,
        {},
    )

    if not isinstance(
        resolved,
        ResolvedStaticPar,
    ):
        raise ResolutionError(
            "Expected resolved static parallel region."
        )

    return resolved


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

    # Infer timing directly from the accelerator control tree.
    #
    # Any named control-region timings become ordinary timing facts
    # available to later symbolic bindings and constraints.
    resolved_body = resolve_control(
        program.body,
        component_latencies,
        values,
    )

    # Evaluate explicit symbolic timing bindings in program order.
    #
    # These remain useful for user-defined relationships, but control
    # composition itself no longer requires handwritten equations.
    resolved_bindings = []

    for binding in program.bindings:
        target = binding.target.name

        if target in values:
            raise ResolutionError(
                "Derived timing variable was already supplied "
                f"or inferred: {target}"
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

    # Discharge constraints only after generator timing, structural
    # timing, and explicit symbolic bindings are all available.
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
        raise ConstraintViolation(
            checks
        )

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

    return ResolvedProgram(
        timing_values=dict(values),
        generators=resolved_generators,
        bindings=tuple(resolved_bindings),
        constraint_checks=checks,
        body=resolved_body,
    )


@dataclass(frozen=True)
class ResolvedComponentProgram:
    """
    Fully resolved V1.3 reusable-component program.

    Program-level timing_values contain generator-produced facts,
    component timing exports, and explicit top-level bindings.

    Internal component timing facts remain encapsulated inside each
    ResolvedComponent.
    """

    timing_values: dict[str, int]
    generators: tuple[ResolvedGenerator, ...]
    bindings: tuple[ResolvedTimingBinding, ...]
    constraint_checks: tuple[ConstraintCheck, ...]
    components: tuple[ResolvedComponent, ...]
    entry: str

    def to_dict(self) -> dict:
        return {
            "kind": "resolved_component_program",
            "timing_values": dict(
                self.timing_values
            ),
            "generators": [
                generator.to_dict()
                for generator
                in self.generators
            ],
            "bindings": [
                binding.to_dict()
                for binding
                in self.bindings
            ],
            "constraint_checks": [
                check.to_dict()
                for check
                in self.constraint_checks
            ],
            "components": [
                component.to_dict()
                for component
                in self.components
            ],
            "entry": self.entry,
        }


def resolve_component_program(
    program: SymbolicProgram,
    environment: TimingEnvironment,
) -> ResolvedComponentProgram:
    """
    Resolve a V1.3 reusable-component program bottom-up.

    Each component receives only:
      * directly invoked generator latencies, and
      * directly invoked child ComponentTimingInterface objects.

    Parents therefore do not receive descendant implementations or
    unrelated generator timing facts.

    After component resolution, exported component timings are combined
    with generator timing facts in the program-level namespace for
    top-level bindings and constraints.
    """

    if not program.components:
        raise ResolutionError(
            "Expected a V1.3 component program."
        )

    if program.entry is None:
        raise ResolutionError(
            "V1.3 component program has no entry."
        )

    environment_values = (
        environment.to_dict()
    )

    generator_latencies: dict[
        str,
        int,
    ] = {}

    for generator in program.generators:
        variable = (
            generator.latency_var.name
        )

        try:
            latency = (
                environment_values[
                    variable
                ]
            )
        except KeyError as exc:
            raise UnboundTimingVariable(
                variable
            ) from exc

        generator_latencies[
            generator.instance
        ] = latency

    generator_names = set(
        generator_latencies
    )

    component_by_name = {
        component.name: component
        for component
        in program.components
    }

    component_names = set(
        component_by_name
    )

    interfaces: dict[
        str,
        ComponentTimingInterface,
    ] = {}

    resolved_components: list[
        ResolvedComponent
    ] = []

    for component_name in (
        topological_component_order(
            program
        )
    ):
        component = (
            component_by_name[
                component_name
            ]
        )

        targets = tuple(
            invoke.component
            for invoke
            in _iter_control_invokes(
                component.body
            )
        )

        direct_generator_latencies = {
            target:
            generator_latencies[
                target
            ]
            for target in targets
            if target
            in generator_names
        }

        direct_component_interfaces = {
            target:
            interfaces[
                target
            ]
            for target in targets
            if target
            in component_names
        }

        resolved_component = (
            resolve_component_decl(
                component,
                generator_latencies=(
                    direct_generator_latencies
                ),
                component_interfaces=(
                    direct_component_interfaces
                ),
            )
        )

        resolved_components.append(
            resolved_component
        )

        interfaces[
            component_name
        ] = (
            resolved_component
            .timing_interface()
        )

    # ---------------------------------------------------------------
    # Program-level namespace.
    #
    # This namespace may see generator timing facts and PUBLIC component
    # exports. It deliberately does not receive component-local timing.
    # ---------------------------------------------------------------
    values = dict(
        environment_values
    )

    for resolved_component in (
        resolved_components
    ):
        declaration = (
            component_by_name[
                resolved_component.name
            ]
        )

        export_name = (
            declaration
            .latency_var
            .name
        )

        if export_name in values:
            raise ResolutionError(
                "Component timing export was already "
                "supplied at program scope: "
                f"{export_name}"
            )

        values[
            export_name
        ] = (
            resolved_component.latency
        )

    resolved_bindings = []

    for binding in program.bindings:
        target = (
            binding.target.name
        )

        if target in values:
            raise ResolutionError(
                "Derived timing variable was already "
                "supplied or inferred: "
                f"{target}"
            )

        value = evaluate_expr(
            binding.expr,
            values,
        )

        values[
            target
        ] = value

        resolved_bindings.append(
            ResolvedTimingBinding(
                name=target,
                value=value,
            )
        )

    checks = tuple(
        evaluate_constraint(
            constraint,
            values,
        )
        for constraint
        in program.constraints
    )

    if not all(
        check.passed
        for check
        in checks
    ):
        raise ConstraintViolation(
            checks
        )

    resolved_generators = tuple(
        ResolvedGenerator(
            instance=generator.instance,
            generator=generator.generator,
            kernel=generator.kernel,
            latency_var=(
                generator.latency_var.name
            ),
            latency=generator_latencies[
                generator.instance
            ],
        )
        for generator
        in program.generators
    )

    return ResolvedComponentProgram(
        timing_values=dict(
            values
        ),
        generators=resolved_generators,
        bindings=tuple(
            resolved_bindings
        ),
        constraint_checks=checks,
        components=tuple(
            resolved_components
        ),
        entry=program.entry,
    )
