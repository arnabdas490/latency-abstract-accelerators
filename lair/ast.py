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

    The region latency is inferred as the maximum latency of its
    invokes. If timing_var is present, the resolver may bind that
    variable to the inferred region latency.
    """

    invokes: tuple[Invoke, ...]
    timing_var: TimingVar | None = None

    def __post_init__(self) -> None:
        if not self.invokes:
            raise ValueError(
                "Static parallel region cannot be empty."
            )

    def to_dict(self) -> dict:
        data = {
            "kind": "static_par",
            "invokes": [
                invoke.to_dict()
                for invoke in self.invokes
            ],
        }

        # Preserve the exact V1.0 representation when no structural
        # timing variable is requested.
        if self.timing_var is not None:
            data["timing_var"] = (
                self.timing_var.to_dict()
            )

        return data


@dataclass(frozen=True)
class StaticSeq:
    """
    A statically composed sequential region.

    Its latency will be inferred structurally as the sum of the
    latencies of its steps.
    """

    steps: tuple[Invoke | StaticPar | StaticSeq, ...]
    timing_var: TimingVar | None = None

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError(
                "Static sequential region cannot be empty."
            )

    def to_dict(self) -> dict:
        data = {
            "kind": "static_seq",
            "steps": [
                step.to_dict()
                for step in self.steps
            ],
        }

        if self.timing_var is not None:
            data["timing_var"] = (
                self.timing_var.to_dict()
            )

        return data


def _iter_control_invokes(
    control: Invoke | StaticPar | StaticSeq,
):
    """Yield all Invoke nodes nested in symbolic static control."""

    if isinstance(control, Invoke):
        yield control
        return

    if isinstance(control, StaticPar):
        yield from control.invokes
        return

    if isinstance(control, StaticSeq):
        for step in control.steps:
            yield from _iter_control_invokes(
                step
            )
        return

    raise TypeError(
        "Unsupported symbolic control node: "
        f"{type(control).__name__}"
    )


def _iter_control_timing_vars(
    control: Invoke | StaticPar | StaticSeq,
):
    """Yield timing variables produced by structural control regions."""

    if isinstance(control, Invoke):
        return

    if isinstance(control, StaticPar):
        if control.timing_var is not None:
            yield control.timing_var

        return

    if isinstance(control, StaticSeq):
        if control.timing_var is not None:
            yield control.timing_var

        for step in control.steps:
            yield from _iter_control_timing_vars(
                step
            )

        return

    raise TypeError(
        "Unsupported symbolic control node: "
        f"{type(control).__name__}"
    )


# ---------------------------------------------------------------------------
# Reusable user components
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ComponentDecl:
    """
    Declares a reusable latency-abstract user component.

    The exported latency variable names the inferred latency of the
    component body. Its concrete value is intentionally absent from
    the symbolic IR.
    """

    name: str
    args: tuple[str, ...]
    latency_var: TimingVar
    body: StaticPar | StaticSeq

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError(
                "Component name must be non-empty."
            )

        if any(
            not arg
            for arg in self.args
        ):
            raise ValueError(
                "Component argument names must be non-empty."
            )

    def to_dict(self) -> dict:
        return {
            "kind": "component_decl",
            "name": self.name,
            "args": list(self.args),
            "latency_var": (
                self.latency_var.to_dict()
            ),
            "body": self.body.to_dict(),
        }


# ---------------------------------------------------------------------------
# Symbolic program
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SymbolicProgram:
    """
    Complete latency-abstract program before generator timing is known.

    Legacy V1.0-V1.2 programs use `body`.

    V1.3 component-based programs use `components` + `entry`.

    The two representations are intentionally serialized differently so
    historical canonical IR remains unchanged.
    """

    generators: tuple[GeneratorDecl, ...]
    bindings: tuple[TimingBinding, ...]
    constraints: tuple[TimingConstraint, ...]
    body: StaticPar | StaticSeq | None = None
    components: tuple[ComponentDecl, ...] = ()
    entry: str | None = None

    def __post_init__(self) -> None:
        generator_names = [
            generator.instance
            for generator in self.generators
        ]

        if (
            len(generator_names)
            != len(set(generator_names))
        ):
            raise ValueError(
                "Generator instance names must be unique."
            )

        binding_names = [
            binding.target.name
            for binding in self.bindings
        ]

        if (
            len(binding_names)
            != len(set(binding_names))
        ):
            raise ValueError(
                "Timing binding targets must be unique."
            )

        # Structural representation invariant only.
        #
        # Detailed V1.3 namespace, dependency, invocation, timing-name,
        # and recursion validation belongs to the dedicated component
        # validation stages added after this AST checkpoint.
        if (
            self.body is not None
            and self.components
        ):
            raise ValueError(
                "SymbolicProgram cannot contain both a legacy body "
                "and V1.3 component declarations."
            )

        if (
            self.body is None
            and not self.components
        ):
            raise ValueError(
                "SymbolicProgram requires either a legacy body "
                "or V1.3 component declarations."
            )

        if (
            self.components
            and self.entry is None
        ):
            raise ValueError(
                "Component-based SymbolicProgram requires an entry."
            )

        if (
            self.body is not None
            and self.entry is not None
        ):
            raise ValueError(
                "Legacy SymbolicProgram body cannot define "
                "a V1.3 entry component."
            )

        # Preserve all historical V1.0-V1.2 validation exactly for the
        # legacy single-body representation.
        if self.body is not None:
            declared = set(
                generator_names
            )

            for invoke in _iter_control_invokes(
                self.body
            ):
                if (
                    invoke.component
                    not in declared
                ):
                    raise ValueError(
                        "Invoke references undeclared component: "
                        f"{invoke.component}"
                    )

            generator_latency_names = {
                generator.latency_var.name
                for generator in self.generators
            }

            region_timing_names = [
                var.name
                for var
                in _iter_control_timing_vars(
                    self.body
                )
            ]

            if (
                len(region_timing_names)
                != len(
                    set(region_timing_names)
                )
            ):
                raise ValueError(
                    "Control-region timing variables must be unique."
                )

            reserved_names = (
                generator_latency_names
                | set(binding_names)
            )

            collisions = (
                reserved_names
                & set(region_timing_names)
            )

            if collisions:
                raise ValueError(
                    "Control-region timing variables collide with "
                    "existing timing variables: "
                    + ", ".join(
                        sorted(collisions)
                    )
                )


        else:
            # -----------------------------------------------------------
            # V1.3 component-program namespace validation
            # -----------------------------------------------------------

            component_names = [
                component.name
                for component in self.components
            ]

            if (
                len(component_names)
                != len(set(component_names))
            ):
                raise ValueError(
                    "Component names must be unique."
                )

            generator_name_set = set(
                generator_names
            )

            component_name_set = set(
                component_names
            )

            name_collisions = (
                generator_name_set
                & component_name_set
            )

            if name_collisions:
                raise ValueError(
                    "Generator/component names collide: "
                    + ", ".join(
                        sorted(name_collisions)
                    )
                )

            if (
                self.entry
                not in component_name_set
            ):
                raise ValueError(
                    "Entry references undeclared component: "
                    f"{self.entry}"
                )

            declared_invocation_targets = (
                generator_name_set
                | component_name_set
            )

            for component in self.components:
                for invoke in _iter_control_invokes(
                    component.body
                ):
                    if (
                        invoke.component
                        not in declared_invocation_targets
                    ):
                        raise ValueError(
                            "Invoke references undeclared "
                            "generator/component: "
                            f"{invoke.component}"
                        )

            generator_latency_name_list = [
                generator.latency_var.name
                for generator in self.generators
            ]

            if (
                len(generator_latency_name_list)
                != len(
                    set(
                        generator_latency_name_list
                    )
                )
            ):
                raise ValueError(
                    "Generator latency variables "
                    "must be unique in V1.3 programs."
                )

            generator_latency_names = set(
                generator_latency_name_list
            )

            component_timing_names = [
                component.latency_var.name
                for component in self.components
            ]

            if (
                len(component_timing_names)
                != len(
                    set(component_timing_names)
                )
            ):
                raise ValueError(
                    "Component timing exports "
                    "must be unique."
                )

            component_timing_name_set = set(
                component_timing_names
            )

            export_generator_collisions = (
                component_timing_name_set
                & generator_latency_names
            )

            if export_generator_collisions:
                raise ValueError(
                    "Component timing exports collide "
                    "with generator latency variables: "
                    + ", ".join(
                        sorted(
                            export_generator_collisions
                        )
                    )
                )

            export_binding_collisions = (
                component_timing_name_set
                & set(binding_names)
            )

            if export_binding_collisions:
                raise ValueError(
                    "Component timing exports collide "
                    "with explicit timing bindings: "
                    + ", ".join(
                        sorted(
                            export_binding_collisions
                        )
                    )
                )

            region_timing_names = []

            for component in self.components:
                region_timing_names.extend(
                    var.name
                    for var
                    in _iter_control_timing_vars(
                        component.body
                    )
                )

            if (
                len(region_timing_names)
                != len(
                    set(region_timing_names)
                )
            ):
                raise ValueError(
                    "Component control-region timing "
                    "variables must be unique."
                )

            region_timing_name_set = set(
                region_timing_names
            )

            region_reserved_collisions = (
                region_timing_name_set
                & (
                    generator_latency_names
                    | set(binding_names)
                    | component_timing_name_set
                )
            )

            if region_reserved_collisions:
                raise ValueError(
                    "Component control-region timing "
                    "variables collide with reserved "
                    "timing names: "
                    + ", ".join(
                        sorted(
                            region_reserved_collisions
                        )
                    )
                )

    def to_dict(self) -> dict:
        """
        Canonical structural representation.

        Concrete generator timing cannot appear here unless somebody
        explicitly encoded it as a TimingConst in the source IR.

        V1.3-only fields are omitted from legacy programs so historical
        canonical serialization remains byte-for-byte compatible after
        canonical JSON encoding.
        """

        data = {
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
        }

        if self.body is not None:
            data["body"] = (
                self.body.to_dict()
            )

        if self.components:
            data["components"] = [
                component.to_dict()
                for component
                in self.components
            ]

        if self.entry is not None:
            data["entry"] = self.entry

        return data
