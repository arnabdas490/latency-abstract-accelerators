#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(65536),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def make_testbench() -> str:
    return r'''
`timescale 1ns/1ps

module tb;
  logic clk = 0;
  logic reset = 1;

  logic go_a = 0;
  logic go_b = 0;

  logic [31:0] x = 32'd10;

  logic [31:0] out_a;
  logic [31:0] out_b;

  logic done_a;
  logic done_b;

  integer cycle = 0;
  integer start_a = -1;
  integer start_b = -1;

  logic seen_a = 0;
  logic seen_b = 0;

  kernel_a_li a (
    .clk(clk),
    .reset(reset),
    .go(go_a),
    .x(x),
    .out(out_a),
    .done(done_a)
  );

  kernel_b_li b (
    .clk(clk),
    .reset(reset),
    .go(go_b),
    .x(x),
    .out(out_b),
    .done(done_b)
  );

  always #5 clk = ~clk;

  always @(posedge clk) begin
    cycle <= cycle + 1;

    if (go_a && start_a < 0)
      start_a <= cycle;

    if (go_b && start_b < 0)
      start_b <= cycle;

    if (done_a) begin
      $display(
        "A_DONE cycle=%0d start=%0d elapsed=%0d out=%0d",
        cycle,
        start_a,
        cycle - start_a,
        out_a
      );

      seen_a <= 1'b1;
    end

    if (done_b) begin
      $display(
        "B_DONE cycle=%0d start=%0d elapsed=%0d out=%0d",
        cycle,
        start_b,
        cycle - start_b,
        out_b
      );

      seen_b <= 1'b1;
    end

    if ((seen_a || done_a) && (seen_b || done_b))
      $finish;
  end

  initial begin
    repeat (2) @(negedge clk);

    reset = 0;

    @(negedge clk);

    go_a = 1;
    go_b = 1;

    @(negedge clk);

    go_a = 0;
    go_b = 0;
  end
endmodule
'''


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--rtl",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--expected-a",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--expected-b",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    rtl = args.rtl.resolve()

    if not rtl.exists():
        raise SystemExit(
            f"RTL file does not exist: {rtl}"
        )

    with tempfile.TemporaryDirectory(
        prefix="v1_1_latency_"
    ) as td:
        td = Path(td)

        tb = td / "tb.sv"
        obj = td / "obj"

        tb.write_text(
            make_testbench()
        )

        compile_result = subprocess.run(
            [
                "verilator",
                "--binary",
                "--timing",
                "--top-module",
                "tb",
                "-Wno-fatal",
                str(tb),
                str(rtl),
                "--Mdir",
                str(obj),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        if compile_result.returncode != 0:
            print(compile_result.stdout)
            print(compile_result.stderr)

            raise SystemExit(
                "Verilator compilation failed."
            )

        sim_result = subprocess.run(
            [
                str(obj / "Vtb"),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        if sim_result.returncode != 0:
            print(sim_result.stdout)
            print(sim_result.stderr)

            raise SystemExit(
                "RTL latency simulation failed."
            )

        text = (
            sim_result.stdout
            + "\n"
            + sim_result.stderr
        )

    a_match = re.search(
        r"A_DONE cycle=(\d+) start=(\d+) "
        r"elapsed=(\d+) out=(\d+)",
        text,
    )

    b_match = re.search(
        r"B_DONE cycle=(\d+) start=(\d+) "
        r"elapsed=(\d+) out=(\d+)",
        text,
    )

    if a_match is None or b_match is None:
        print(text)

        raise SystemExit(
            "Could not parse latency-check output."
        )

    measured_a = int(
        a_match.group(3)
    )

    measured_b = int(
        b_match.group(3)
    )

    out_a = int(
        a_match.group(4)
    )

    out_b = int(
        b_match.group(4)
    )

    timing_correct = (
        measured_a == args.expected_a
        and measured_b == args.expected_b
    )

    functional_correct = (
        out_a == 11
        and out_b == 12
    )

    report = {
        "rtl": str(rtl),
        "expected_go_to_done_cycles": {
            "kernel_a": args.expected_a,
            "kernel_b": args.expected_b,
        },
        "measured_go_to_done_cycles": {
            "kernel_a": measured_a,
            "kernel_b": measured_b,
        },
        "outputs_for_x_10": {
            "kernel_a": out_a,
            "kernel_b": out_b,
        },
        "timing_correct": timing_correct,
        "functional_correct": functional_correct,
        "rtl_sha256": sha256(rtl),
    }

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        json.dumps(
            report,
            indent=2,
        )
        + "\n"
    )

    print("===== V1.1 RTL LATENCY VALIDATION =====")

    print(
        f"A expected={args.expected_a}, "
        f"measured={measured_a}"
    )

    print(
        f"B expected={args.expected_b}, "
        f"measured={measured_b}"
    )

    print(
        f"A(10) = {out_a}"
    )

    print(
        f"B(10) = {out_b}"
    )

    print(
        "timing_correct =",
        timing_correct,
    )

    print(
        "functional_correct =",
        functional_correct,
    )

    print(
        "RTL SHA256 =",
        report["rtl_sha256"],
    )

    if not timing_correct or not functional_correct:
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
