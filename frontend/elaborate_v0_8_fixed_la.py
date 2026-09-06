#!/usr/bin/env python3

import json
import subprocess
import sys
from pathlib import Path

RESOLVER = Path("frontend/resolve_v0_4_contract.py")
RESOLUTION = Path("results/v0_4_resolution.json")

OUTPUT = Path("examples/generated/v0_8_fixed_la.futil")
REPORT = Path("results/v0_8_fixed_la.json")


def main():
    OUTPUT.unlink(missing_ok=True)

    result = subprocess.run(
        [sys.executable, str(RESOLVER)],
        text=True,
        capture_output=True,
    )

    if result.stdout:
        print(result.stdout, end="")

    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")

    if result.returncode != 0:
        REPORT.write_text(
            json.dumps(
                {
                    "status": "rejected",
                    "resolver_exit_code": result.returncode,
                    "hardware_emitted": False,
                },
                indent=2,
            )
            + "\n"
        )

        print(
            "Timing-aware RTL composition blocked by contract.",
            file=sys.stderr,
        )
        sys.exit(result.returncode)

    resolution = json.loads(RESOLUTION.read_text())
    bindings = resolution["bindings"]

    la = int(bindings["L_A"])
    lb = int(bindings["L_B"])
    target = int(bindings["T"])

    program = f'''import "primitives/core.futil";
import "primitives/memories/comb.futil";

extern "../../baselines/v0_8_fixed_li_kernels.sv" {{
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

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(program)

    REPORT.write_text(
        json.dumps(
            {
                "status": "accepted",
                "hardware_emitted": True,
                "shared_rtl":
                    "baselines/v0_8_fixed_li_kernels.sv",
                "bindings": bindings,
                "interval_metadata": {
                    "kernel_a": la,
                    "kernel_b": lb,
                },
                "parallel_region_latency": target,
                "parent_uses_static_timing": True,
            },
            indent=2,
        )
        + "\n"
    )

    print()
    print("Generated timing-aware composition over SAME RTL")
    print(f"L_A = {la}")
    print(f"L_B = {lb}")
    print(f"T   = {target}")
    print("External RTL was NOT regenerated.")
    print(f"Calyx: {OUTPUT}")


if __name__ == "__main__":
    main()
