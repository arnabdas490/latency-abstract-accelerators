#!/usr/bin/env python3

import json
from pathlib import Path

CONTRACT = Path("contracts/toy_kernel.json")
OUTPUT = Path("examples/generated/v0_2_generated.futil")


def main():
    contract = json.loads(CONTRACT.read_text())
    latency = int(contract["latency"])

    if latency < 1:
        raise ValueError("Latency must be at least 1 cycle.")

    if latency == 1:
        delay_group = ""
        kernel_control = "incr;"
    else:
        delay_group = """
    static<1> group delay {
    }
"""
        kernel_control = f"""static seq {{
          static repeat {latency - 1} {{
            delay;
          }}
          incr;
        }}"""

    program = f'''import "primitives/core.futil";
import "primitives/memories/comb.futil";

component main() -> () {{
  cells {{
    @external(1) mem = comb_mem_d1(32, 2, 1);

    counter = std_reg(32);
    add = std_add(32);
    lt = std_lt(32);
  }}

  wires {{
    group init {{
      counter.in = 32'd0;
      counter.write_en = 1'b1;
      init[done] = counter.done;
    }}
{delay_group}
    static<1> group incr {{
      add.left = counter.out;
      add.right = 32'd1;
      counter.in = add.out;
      counter.write_en = 1'b1;
    }}

    comb group cond {{
      mem.addr0 = 1'd0;
      lt.left = counter.out;
      lt.right = mem.read_data;
    }}

    group write {{
      mem.addr0 = 1'd1;
      mem.write_data = counter.out;
      mem.write_en = 1'b1;
      write[done] = mem.done;
    }}
  }}

  control {{
    seq {{
      init;

      while lt.out with cond {{
        {kernel_control}
      }}

      write;
    }}
  }}
}}
'''

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(program)

    print(f"Resolved latency L={latency}")
    print(f"Emitted {OUTPUT}")


if __name__ == "__main__":
    main()
