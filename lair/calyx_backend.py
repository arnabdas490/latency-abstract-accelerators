from __future__ import annotations

from pathlib import Path

from lair.resolver import (
    ResolvedComponent,
    ResolvedComponentProgram,
    ResolvedInvoke,
    ResolvedProgram,
    ResolvedStaticPar,
    ResolvedStaticSeq,
)


class CalyxLoweringError(Exception):
    """Raised when a resolved program cannot be lowered to Calyx."""


def _require_resolved_program(
    program: object,
) -> ResolvedProgram:
    if not isinstance(
        program,
        ResolvedProgram,
    ):
        raise TypeError(
            "Calyx backend accepts only ResolvedProgram; "
            f"received {type(program).__name__}"
        )

    return program


def _generator_by_instance(
    program: ResolvedProgram,
) -> dict[str, object]:
    return {
        generator.instance: generator
        for generator in program.generators
    }


def _validate_resolved_control(
    control: (
        ResolvedInvoke
        | ResolvedStaticPar
        | ResolvedStaticSeq
    ),
    component_latencies: dict[str, int],
) -> int:
    """
    Independently verify that resolved control timing agrees with
    generator timing and static-control composition semantics.

    Invoke:
        component latency

    StaticPar:
        max(child latencies)

    StaticSeq:
        sum(child latencies)
    """

    if isinstance(
        control,
        ResolvedInvoke,
    ):
        try:
            expected = component_latencies[
                control.component
            ]
        except KeyError as exc:
            raise CalyxLoweringError(
                "Resolved control invokes unknown component: "
                f"{control.component}"
            ) from exc

        if control.latency != expected:
            raise CalyxLoweringError(
                "Resolved invoke latency does not match "
                "generator latency for component "
                f"{control.component}."
            )

        return control.latency

    if isinstance(
        control,
        ResolvedStaticPar,
    ):
        child_latencies = [
            _validate_resolved_control(
                invoke,
                component_latencies,
            )
            for invoke in control.invokes
        ]

        expected = max(
            child_latencies
        )

        if control.latency != expected:
            raise CalyxLoweringError(
                "Resolved static-par latency is inconsistent "
                "with child latencies."
            )

        return control.latency

    if isinstance(
        control,
        ResolvedStaticSeq,
    ):
        child_latencies = [
            _validate_resolved_control(
                step,
                component_latencies,
            )
            for step in control.steps
        ]

        expected = sum(
            child_latencies
        )

        if control.latency != expected:
            raise CalyxLoweringError(
                "Resolved static-seq latency is inconsistent "
                "with child latencies."
            )

        return control.latency

    raise CalyxLoweringError(
        "Unsupported resolved control node: "
        f"{type(control).__name__}"
    )


def _lower_static_control(
    control: (
        ResolvedInvoke
        | ResolvedStaticPar
        | ResolvedStaticSeq
    ),
    *,
    cell_names: dict[str, str],
    indent: int,
    component_bodies: (
        dict[str, ResolvedComponent]
        | None
    ) = None,
    expansion_stack: tuple[str, ...] = (),
) -> list[str]:
    """
    Recursively lower already-resolved static control.

    Generator invokes become physical Calyx invokes.

    V1.3 user-component invokes may be expanded from resolved component
    bodies. This is backend implementation expansion only: timing has
    already been resolved before this stage.
    """

    pad = " " * indent

    if isinstance(
        control,
        ResolvedInvoke,
    ):
        if control.component in cell_names:
            cell = cell_names[
                control.component
            ]

            # The current toy backend supports the single x argument.
            if control.args != ("x",):
                raise CalyxLoweringError(
                    "Toy Calyx backend currently supports "
                    "invoke arguments exactly ('x',); "
                    f"got {control.args!r} for "
                    f"{control.component}."
                )

            return [
                f"{pad}static invoke "
                f"{cell}(x=x.out)();"
            ]

        if (
            component_bodies is not None
            and control.component
            in component_bodies
        ):
            name = control.component

            if name in expansion_stack:
                cycle = " -> ".join(
                    expansion_stack
                    + (
                        name,
                    )
                )

                raise CalyxLoweringError(
                    "Recursive component expansion reached "
                    f"backend: {cycle}"
                )

            component = (
                component_bodies[
                    name
                ]
            )

            if (
                control.latency
                != component.latency
            ):
                raise CalyxLoweringError(
                    "Resolved component invoke latency "
                    "does not match exported component "
                    f"latency for {name}."
                )

            return _lower_static_control(
                component.body,
                cell_names=cell_names,
                indent=indent,
                component_bodies=(
                    component_bodies
                ),
                expansion_stack=(
                    expansion_stack
                    + (
                        name,
                    )
                ),
            )

        raise CalyxLoweringError(
            "No Calyx cell or resolved component "
            "for invoke target: "
            f"{control.component}"
        )

    if isinstance(
        control,
        ResolvedStaticPar,
    ):
        lines = [
            f"{pad}static par {{"
        ]

        for invoke in control.invokes:
            lines.extend(
                _lower_static_control(
                    invoke,
                    cell_names=cell_names,
                    indent=indent + 2,
                    component_bodies=(
                        component_bodies
                    ),
                    expansion_stack=(
                        expansion_stack
                    ),
                )
            )

        lines.append(
            f"{pad}}}"
        )

        return lines

    if isinstance(
        control,
        ResolvedStaticSeq,
    ):
        lines = [
            f"{pad}static seq {{"
        ]

        for step in control.steps:
            lines.extend(
                _lower_static_control(
                    step,
                    cell_names=cell_names,
                    indent=indent + 2,
                    component_bodies=(
                        component_bodies
                    ),
                    expansion_stack=(
                        expansion_stack
                    ),
                )
            )

        lines.append(
            f"{pad}}}"
        )

        return lines

    raise CalyxLoweringError(
        "Unsupported resolved control node: "
        f"{type(control).__name__}"
    )

def _lower_toy_resolved_control_to_calyx(
    program: ResolvedProgram,
    *,
    extern_rtl: str = (
        "../../baselines/"
        "v0_8_fixed_li_kernels.sv"
    ),
    component_bodies: (
        dict[str, ResolvedComponent]
        | None
    ) = None,
) -> str:
    """
    Lower resolved LAIR static control to ordinary Calyx/Piezo.

    Abstraction boundary:
      - accepts only ResolvedProgram;
      - does not read generator contracts;
      - does not resolve symbolic timing;
      - does not infer latency from RTL;
      - recursively validates and lowers already-resolved
        static control.

    The surrounding runtime-loop/data-path shell remains the
    two-generator toy experiment used by V1.0-V1.2.
    """

    program = _require_resolved_program(
        program
    )

    generators = _generator_by_instance(
        program
    )

    # V1.2 generalizes control composition, not generator-interface
    # generation. Preserve the established A/B toy-kernel shell.
    try:
        gen_a = generators["A"]
        gen_b = generators["B"]
    except KeyError as exc:
        raise CalyxLoweringError(
            "Toy backend requires generator instances A and B."
        ) from exc

    component_latencies = {
        generator.instance: generator.latency
        for generator in program.generators
    }

    if component_bodies is not None:
        component_latencies.update(
            {
                component.name:
                component.latency
                for component
                in component_bodies.values()
            }
        )

    _validate_resolved_control(
        program.body,
        component_latencies,
    )

    la = gen_a.latency
    lb = gen_b.latency

    cell_names = {
        "A": "a",
        "B": "b",
    }

    body_control = "\n".join(
        _lower_static_control(
            program.body,
            cell_names=cell_names,
            indent=10,
            component_bodies=component_bodies,
        )
    )

    return f'''import "primitives/core.futil";
import "primitives/memories/comb.futil";

extern "{extern_rtl}" {{
  primitive kernel_a_li(
    @interval({la}) @go go: 1,
    x: 32,
    @clk clk: 1,
    @reset reset: 1
  ) -> (
    @stable out: 32,
    @done done: 1
  );

  primitive kernel_b_li(
    @interval({lb}) @go go: 1,
    x: 32,
    @clk clk: 1,
    @reset reset: 1
  ) -> (
    @stable out: 32,
    @done done: 1
  );
}}

component main() -> () {{
  cells {{
    @external(1) mem = comb_mem_d1(32, 4, 2);
    x = std_reg(32);
    counter = std_reg(32);
    a = kernel_a_li();
    b = kernel_b_li();
    add_counter = std_add(32);
    add_final = std_add(32);
    lt = std_lt(32);
  }}

  wires {{
    group load_x {{
      mem.addr0 = 2'd0;
      x.in = mem.read_data;
      x.write_en = 1'b1;
      load_x[done] = x.done;
    }}

    group init_counter {{
      counter.in = 32'd0;
      counter.write_en = 1'b1;
      init_counter[done] = counter.done;
    }}

    comb group cond {{
      mem.addr0 = 2'd1;
      lt.left = counter.out;
      lt.right = mem.read_data;
    }}

    static<1> group incr_counter {{
      add_counter.left = counter.out;
      add_counter.right = 32'd1;
      counter.in = add_counter.out;
      counter.write_en = 1'b1;
    }}

    group write_result {{
      add_final.left = a.out;
      add_final.right = b.out;
      mem.addr0 = 2'd2;
      mem.write_data = add_final.out;
      mem.write_en = 1'b1;
      write_result[done] = mem.done;
    }}
  }}

  control {{
    seq {{
      load_x;
      init_counter;
      while lt.out with cond {{
        static seq {{
{body_control}
          incr_counter;
        }}
      }}
      write_result;
    }}
  }}
}}
'''


def lower_resolved_program_to_calyx(
    program: ResolvedProgram,
    *,
    extern_rtl: str = (
        "../../baselines/"
        "v0_8_fixed_li_kernels.sv"
    ),
) -> str:
    """
    Historical V1.0-V1.2 resolved-program lowering.
    """

    program = _require_resolved_program(
        program
    )

    return _lower_toy_resolved_control_to_calyx(
        program,
        extern_rtl=extern_rtl,
    )


def lower_resolved_component_program_to_calyx(
    program: ResolvedComponentProgram,
    *,
    extern_rtl: str = (
        "../../baselines/"
        "v0_8_fixed_li_kernels.sv"
    ),
) -> str:
    """
    Lower V1.3 after component timing has already been resolved.

    Reusable components remain modular through timing resolution.
    At this final toy-backend stage, resolved component bodies are
    expanded into the established A/B Calyx shell.
    """

    if not isinstance(
        program,
        ResolvedComponentProgram,
    ):
        raise TypeError(
            "V1.3 Calyx backend accepts only "
            "ResolvedComponentProgram; "
            f"received {type(program).__name__}"
        )

    component_bodies = {
        component.name:
        component
        for component
        in program.components
    }

    try:
        entry = component_bodies[
            program.entry
        ]
    except KeyError as exc:
        raise CalyxLoweringError(
            "Resolved entry component is missing: "
            f"{program.entry}"
        ) from exc

    # Validate every reusable component independently against the
    # resolved generator/component latency namespace.
    component_latencies = {
        generator.instance:
        generator.latency
        for generator
        in program.generators
    }

    component_latencies.update(
        {
            component.name:
            component.latency
            for component
            in program.components
        }
    )

    for component in (
        program.components
    ):
        body_latency = (
            _validate_resolved_control(
                component.body,
                component_latencies,
            )
        )

        if (
            body_latency
            != component.latency
        ):
            raise CalyxLoweringError(
                "Resolved component body latency "
                "does not match exported latency "
                f"for {component.name}."
            )

    # Reuse the established toy shell. The synthetic legacy wrapper is
    # only a backend adapter around already-resolved IR; no symbolic or
    # generator timing analysis occurs here.
    adapter = ResolvedProgram(
        timing_values=(
            program.timing_values
        ),
        generators=(
            program.generators
        ),
        bindings=(
            program.bindings
        ),
        constraint_checks=(
            program.constraint_checks
        ),
        body=entry.body,
    )

    return _lower_toy_resolved_control_to_calyx(
        adapter,
        extern_rtl=extern_rtl,
        component_bodies=(
            component_bodies
        ),
    )


def write_resolved_program_calyx(
    program: (
        ResolvedProgram
        | ResolvedComponentProgram
    ),
    output: Path,
    *,
    extern_rtl: str = (
        "../../baselines/"
        "v0_8_fixed_li_kernels.sv"
    ),
) -> None:
    """
    Lower an already-resolved program and write concrete Calyx.

    No output file is created unless lowering succeeds.
    """

    if isinstance(
        program,
        ResolvedComponentProgram,
    ):
        text = (
            lower_resolved_component_program_to_calyx(
                program,
                extern_rtl=extern_rtl,
            )
        )
    elif isinstance(
        program,
        ResolvedProgram,
    ):
        text = (
            lower_resolved_program_to_calyx(
                program,
                extern_rtl=extern_rtl,
            )
        )
    else:
        raise TypeError(
            "Calyx writer accepts only resolved "
            "LAIR programs; received "
            f"{type(program).__name__}"
        )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        text
    )



# ---------------------------------------------------------------------------
# Backward-compatible V1.0/V1.1 entry points.
# ---------------------------------------------------------------------------

def lower_v1_pair_to_calyx(
    program: ResolvedProgram,
    *,
    extern_rtl: str = (
        "../../baselines/"
        "v0_8_fixed_li_kernels.sv"
    ),
) -> str:
    return lower_resolved_program_to_calyx(
        program,
        extern_rtl=extern_rtl,
    )


def write_v1_pair_calyx(
    program: ResolvedProgram,
    output: Path,
    *,
    extern_rtl: str = (
        "../../baselines/"
        "v0_8_fixed_li_kernels.sv"
    ),
) -> None:
    write_resolved_program_calyx(
        program,
        output,
        extern_rtl=extern_rtl,
    )
