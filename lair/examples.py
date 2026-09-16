from __future__ import annotations

from lair.ast import (
    GeneratorDecl,
    Invoke,
    StaticPar,
    SymbolicProgram,
    TimingBinding,
    TimingConst,
    TimingConstraint,
    TimingMax,
    TimingVar,
)


def make_v1_0_pair_program() -> SymbolicProgram:
    """
    Construct the canonical V1.0 latency-abstract pair program.

    L_A and L_B are intentionally unresolved here.
    """

    l_a = TimingVar("L_A")
    l_b = TimingVar("L_B")
    target = TimingVar("T")

    return SymbolicProgram(
        generators=(
            GeneratorDecl(
                instance="A",
                generator="toy_generator",
                kernel="kernel_a",
                latency_var=l_a,
            ),
            GeneratorDecl(
                instance="B",
                generator="toy_generator",
                kernel="kernel_b",
                latency_var=l_b,
            ),
        ),
        bindings=(
            TimingBinding(
                target=target,
                expr=TimingMax(l_a, l_b),
            ),
        ),
        constraints=(
            TimingConstraint(
                name="positive_latency_a",
                left=l_a,
                op=">=",
                right=TimingConst(1),
            ),
            TimingConstraint(
                name="positive_latency_b",
                left=l_b,
                op=">=",
                right=TimingConst(1),
            ),
            TimingConstraint(
                name="parallel_deadline",
                left=target,
                op="<=",
                right=TimingConst(6),
            ),
        ),
        body=StaticPar(
            invokes=(
                Invoke(
                    component="A",
                    args=("x",),
                ),
                Invoke(
                    component="B",
                    args=("x",),
                ),
            ),
        ),
    )
