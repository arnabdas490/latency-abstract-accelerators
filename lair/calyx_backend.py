from __future__ import annotations

from pathlib import Path

from lair.resolver import ResolvedProgram


class CalyxLoweringError(Exception):
    """Raised when a resolved program cannot be lowered to Calyx."""


def _require_resolved_program(program: object) -> ResolvedProgram:
    if not isinstance(program, ResolvedProgram):
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


def lower_v1_pair_to_calyx(
    program: ResolvedProgram,
    *,
    extern_rtl: str = "../../baselines/v0_8_fixed_li_kernels.sv",
) -> str:
    """
    Lower the resolved V1.0 two-kernel example to ordinary Calyx/Piezo.

    Important abstraction boundary:
      - this function receives only ResolvedProgram;
      - it does not read generator contracts;
      - it does not resolve symbolic timing;
      - it does not infer latency from RTL.

    Concrete @interval values come exclusively from the resolved IR.
    """

    program = _require_resolved_program(program)

    generators = _generator_by_instance(program)

    try:
        gen_a = generators["A"]
        gen_b = generators["B"]
    except KeyError as exc:
        raise CalyxLoweringError(
            "V1.0 pair backend requires generator instances A and B."
        ) from exc

    invokes = {
        invoke.component: invoke
        for invoke in program.body.invokes
    }

    try:
        invoke_a = invokes["A"]
        invoke_b = invokes["B"]
    except KeyError as exc:
        raise CalyxLoweringError(
            "V1.0 pair backend requires invokes of A and B."
        ) from exc

    if invoke_a.latency != gen_a.latency:
        raise CalyxLoweringError(
            "Resolved invoke A latency does not match generator A."
        )

    if invoke_b.latency != gen_b.latency:
        raise CalyxLoweringError(
            "Resolved invoke B latency does not match generator B."
        )

    expected_parallel_latency = max(
        gen_a.latency,
        gen_b.latency,
    )

    if program.body.latency != expected_parallel_latency:
        raise CalyxLoweringError(
            "Resolved static-par latency is inconsistent with "
            "resolved generator latencies."
        )

    la = gen_a.latency
    lb = gen_b.latency

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
          static par {{
            static invoke a(x=x.out)();
            static invoke b(x=x.out)();
          }}
          incr_counter;
        }}
      }}
      write_result;
    }}
  }}
}}
'''


def write_v1_pair_calyx(
    program: ResolvedProgram,
    output: Path,
    *,
    extern_rtl: str = "../../baselines/v0_8_fixed_li_kernels.sv",
) -> None:
    """
    Lower an already-resolved program and write the resulting Calyx.

    No output file is created unless lowering succeeds.
    """

    text = lower_v1_pair_to_calyx(
        program,
        extern_rtl=extern_rtl,
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(text)
