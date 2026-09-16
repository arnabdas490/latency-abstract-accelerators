import unittest

from lair.ast import (
    GeneratorDecl,
    Invoke,
    StaticPar,
    StaticSeq,
    SymbolicProgram,
    TimingConst,
    TimingConstraint,
    TimingVar,
)
from lair.environment import TimingEnvironment
from lair.resolver import (
    ConstraintViolation,
    ResolutionError,
    ResolvedInvoke,
    ResolvedStaticPar,
    ResolvedStaticSeq,
    resolve_program,
)


def make_hierarchical_program() -> SymbolicProgram:
    return SymbolicProgram(
        generators=(
            GeneratorDecl(
                instance="A",
                generator="toy_generator",
                kernel="kernel_a",
                latency_var=TimingVar("L_A"),
            ),
            GeneratorDecl(
                instance="B",
                generator="toy_generator",
                kernel="kernel_b",
                latency_var=TimingVar("L_B"),
            ),
        ),
        # Deliberately NO handwritten timing equations.
        bindings=(),
        constraints=(
            TimingConstraint(
                name="total_deadline",
                left=TimingVar(
                    "T_total"
                ),
                op="<=",
                right=TimingConst(8),
            ),
        ),
        body=StaticSeq(
            steps=(
                StaticPar(
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
                    timing_var=TimingVar(
                        "T_pair"
                    ),
                ),
                Invoke(
                    component="A",
                    args=("x",),
                ),
            ),
            timing_var=TimingVar(
                "T_total"
            ),
        ),
    )


class StructuralTimingResolverTests(unittest.TestCase):
    def test_c1_infers_hierarchical_timing(self):
        program = make_hierarchical_program()

        resolved = resolve_program(
            program,
            TimingEnvironment(
                {
                    "L_A": 2,
                    "L_B": 5,
                }
            ),
        )

        self.assertEqual(
            program.bindings,
            (),
        )

        self.assertEqual(
            resolved.timing_values[
                "T_pair"
            ],
            5,
        )

        self.assertEqual(
            resolved.timing_values[
                "T_total"
            ],
            7,
        )

        self.assertIsInstance(
            resolved.body,
            ResolvedStaticSeq,
        )

        pair = resolved.body.steps[0]
        final_a = resolved.body.steps[1]

        self.assertIsInstance(
            pair,
            ResolvedStaticPar,
        )

        self.assertIsInstance(
            final_a,
            ResolvedInvoke,
        )

        self.assertEqual(
            pair.latency,
            5,
        )

        self.assertEqual(
            final_a.latency,
            2,
        )

        self.assertEqual(
            resolved.body.latency,
            7,
        )

    def test_c2_reversal_changes_parent_timing_and_rejects(self):
        program = make_hierarchical_program()

        with self.assertRaises(
            ConstraintViolation
        ) as ctx:
            resolve_program(
                program,
                TimingEnvironment(
                    {
                        "L_A": 5,
                        "L_B": 2,
                    }
                ),
            )

        failure = ctx.exception.failures[0]

        self.assertEqual(
            failure.name,
            "total_deadline",
        )

        self.assertEqual(
            failure.left_value,
            10,
        )

        self.assertEqual(
            failure.right_value,
            8,
        )

    def test_c3_equal_latencies_infer_six_cycles(self):
        resolved = resolve_program(
            make_hierarchical_program(),
            TimingEnvironment(
                {
                    "L_A": 3,
                    "L_B": 3,
                }
            ),
        )

        self.assertEqual(
            resolved.timing_values[
                "T_pair"
            ],
            3,
        )

        self.assertEqual(
            resolved.timing_values[
                "T_total"
            ],
            6,
        )

        self.assertEqual(
            resolved.body.latency,
            6,
        )

    def test_structural_timing_requires_no_explicit_binding(self):
        program = make_hierarchical_program()

        self.assertEqual(
            len(program.bindings),
            0,
        )

        resolved = resolve_program(
            program,
            TimingEnvironment(
                {
                    "L_A": 2,
                    "L_B": 5,
                }
            ),
        )

        self.assertIn(
            "T_pair",
            resolved.timing_values,
        )

        self.assertIn(
            "T_total",
            resolved.timing_values,
        )

    def test_environment_cannot_override_structural_timing(self):
        with self.assertRaises(
            ResolutionError
        ):
            resolve_program(
                make_hierarchical_program(),
                TimingEnvironment(
                    {
                        "L_A": 2,
                        "L_B": 5,
                        "T_pair": 999,
                    }
                ),
            )


if __name__ == "__main__":
    unittest.main()
