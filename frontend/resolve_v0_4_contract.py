#!/usr/bin/env python3

import json
import sys
from pathlib import Path

SPEC = Path("contracts/v0_4_pair_contract.json")
A_CONTRACT = Path("contracts/kernel_a.json")
B_CONTRACT = Path("contracts/kernel_b.json")
OUTPUT = Path("results/v0_4_resolution.json")


class ContractViolation(Exception):
    pass


def load_json(path):
    return json.loads(path.read_text())


def resolve_value(value, env):
    if isinstance(value, int):
        return value

    if isinstance(value, str):
        if value not in env:
            raise KeyError(f"Unresolved symbol: {value}")
        return env[value]

    raise TypeError(f"Unsupported value: {value!r}")


def eval_expr(expr, env):
    op = expr["op"]
    args = [resolve_value(arg, env) for arg in expr["args"]]

    if op == "max":
        return max(args)

    if op == "sub":
        if len(args) != 2:
            raise ValueError("sub requires exactly two arguments")
        return args[0] - args[1]

    raise ValueError(f"Unknown expression operator: {op}")


def check_constraint(constraint, env):
    lhs = resolve_value(constraint["lhs"], env)
    rhs = resolve_value(constraint["rhs"], env)
    op = constraint["op"]

    if op == "ge":
        passed = lhs >= rhs
        relation = ">="
    elif op == "le":
        passed = lhs <= rhs
        relation = "<="
    elif op == "eq":
        passed = lhs == rhs
        relation = "=="
    else:
        raise ValueError(f"Unknown constraint operator: {op}")

    return {
        "name": constraint["name"],
        "passed": passed,
        "lhs_value": lhs,
        "rhs_value": rhs,
        "relation": relation,
    }


def main():
    spec = load_json(SPEC)
    a = load_json(A_CONTRACT)
    b = load_json(B_CONTRACT)

    env = {
        "L_A": int(a["latency"]),
        "L_B": int(b["latency"]),
    }

    # Resolve symbolic derived values in declaration order.
    for symbol, expr in spec["derived"].items():
        env[symbol] = eval_expr(expr, env)

    checks = [
        check_constraint(constraint, env)
        for constraint in spec["constraints"]
    ]

    report = {
        "contract": spec["name"],
        "bindings": env,
        "constraints": checks,
        "valid": all(check["passed"] for check in checks),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")

    print("Resolved timing environment:")
    for symbol in ["L_A", "L_B", "T", "D_A", "D_B"]:
        print(f"  {symbol} = {env[symbol]}")

    print("\nConstraint checks:")
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        print(
            f"  [{status}] {check['name']}: "
            f"{check['lhs_value']} "
            f"{check['relation']} "
            f"{check['rhs_value']}"
        )

    if not report["valid"]:
        failed = [
            check["name"]
            for check in checks
            if not check["passed"]
        ]

        raise ContractViolation(
            "Timing contract rejected configuration: "
            + ", ".join(failed)
        )

    print("\nTiming contract accepted.")


if __name__ == "__main__":
    try:
        main()
    except ContractViolation as exc:
        print(f"\nCONTRACT ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
