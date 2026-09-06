#!/usr/bin/env python3

import json
from pathlib import Path

A_CONTRACT = Path("contracts/kernel_a.json")
B_CONTRACT = Path("contracts/kernel_b.json")

SV = Path("baselines/v0_8_fixed_li_kernels.sv")
FUTIL = Path("baselines/v0_8_fixed_li.futil")
REPORT = Path("results/v0_8_fixed_li_baseline.json")


def latency(path):
    value = int(json.loads(path.read_text())["latency"])
    if value < 1:
        raise ValueError("Latency must be >= 1")
    return value


def sv_kernel(module, cycles, add_const):
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


def main():
    la = latency(A_CONTRACT)
    lb = latency(B_CONTRACT)

    SV.write_text(
        sv_kernel("kernel_a_li", la, 1)
        + "\n"
        + sv_kernel("kernel_b_li", lb, 2)
    )

    program = '''import "primitives/core.futil";
import "primitives/memories/comb.futil";

extern "v0_8_fixed_li_kernels.sv" {
  primitive kernel_a_li(
    @go go: 1,
    x: 32,
    @clk clk: 1,
    @reset reset: 1
  ) -> (
    @stable out: 32,
    @done done: 1
  );

  primitive kernel_b_li(
    @go go: 1,
    x: 32,
    @clk clk: 1,
    @reset reset: 1
  ) -> (
    @stable out: 32,
    @done done: 1
  );
}

component main() -> () {
  cells {
    @external(1) mem = comb_mem_d1(32, 4, 2);

    x = std_reg(32);
    counter = std_reg(32);

    a = kernel_a_li();
    b = kernel_b_li();

    add_counter = std_add(32);
    add_final = std_add(32);
    lt = std_lt(32);
  }

  wires {
    group load_x {
      mem.addr0 = 2'd0;
      x.in = mem.read_data;
      x.write_en = 1'b1;
      load_x[done] = x.done;
    }

    group init_counter {
      counter.in = 32'd0;
      counter.write_en = 1'b1;
      init_counter[done] = counter.done;
    }

    comb group cond {
      mem.addr0 = 2'd1;
      lt.left = counter.out;
      lt.right = mem.read_data;
    }

    group incr_counter {
      add_counter.left = counter.out;
      add_counter.right = 32'd1;

      counter.in = add_counter.out;
      counter.write_en = 1'b1;

      incr_counter[done] = counter.done;
    }

    group write_result {
      add_final.left = a.out;
      add_final.right = b.out;

      mem.addr0 = 2'd2;
      mem.write_data = add_final.out;
      mem.write_en = 1'b1;

      write_result[done] = mem.done;
    }
  }

  control {
    seq {
      load_x;
      init_counter;

      while lt.out with cond {
        seq {
          par {
            invoke a(x=x.out)();
            invoke b(x=x.out)();
          }

          incr_counter;
        }
      }

      write_result;
    }
  }
}
'''

    FUTIL.write_text(program)

    REPORT.write_text(
        json.dumps(
            {
                "baseline": "opaque_fixed_latency_li",
                "actual_kernel_latencies": {
                    "L_A": la,
                    "L_B": lb,
                },
                "parent_receives_latency_metadata": False,
                "interface": "go/done",
                "calyx_static_annotations": False,
            },
            indent=2,
        )
        + "\n"
    )

    print("Generated opaque fixed-latency LI baseline")
    print(f"Actual RTL latency A = {la}")
    print(f"Actual RTL latency B = {lb}")
    print("Calyx parent timing metadata = NONE")
    print(f"RTL:   {SV}")
    print(f"Calyx: {FUTIL}")


if __name__ == "__main__":
    main()
