import hashlib
import json
import unittest

from lair.environment import TimingEnvironment
from lair.examples import make_v1_0_pair_program
from lair.resolver import (
    ConstraintViolation,
    ResolutionError,
    UnboundTimingVariable,
    resolve_program,
)


def symbolic_hash(program) -> str:
    text = json.dumps(
        program.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        text.encode()
    ).hexdigest()


class EnvironmentTests(unittest.TestCase):
    def test_environment_preserves_generator_timings(self):
        env = TimingEnvironment(
            {
                "L_A": 5,
                "L_B": 2,
            }
        )

        self.assertEqual(
            env.to_dict(),
            {
                "L_A": 5,
                "L_B": 2,
            },
        )

    def test_negative_environment_value_is_rejected(self):
        with self.assertRaises(ValueError):
            TimingEnvironment(
                {
                    "L_A": -1,
                }
            )


class ResolverTests(unittest.TestCase):
    def test_c2_resolves_symbolic_timing(self):
        program = make_v1_0_pair_program()

        resolved = resolve_program(
            program,
            TimingEnvironment(
                {
                    "L_A": 5,
                    "L_B": 2,
                }
            ),
        )

        self.assertEqual(
            resolved.timing_values["L_A"],
            5,
        )
        self.assertEqual(
            resolved.timing_values["L_B"],
            2,
        )
        self.assertEqual(
            resolved.timing_values["T"],
            5,
        )

        self.assertEqual(
            resolved.body.latency,
            5,
        )

        self.assertEqual(
            [
                invoke.latency
                for invoke in resolved.body.invokes
            ],
            [5, 2],
        )

        self.assertTrue(
            all(
                check.passed
                for check in resolved.constraint_checks
            )
        )

    def test_c1_resolves_to_five_cycle_parallel_region(self):
        resolved = resolve_program(
            make_v1_0_pair_program(),
            TimingEnvironment(
                {
                    "L_A": 2,
                    "L_B": 5,
                }
            ),
        )

        self.assertEqual(
            resolved.timing_values["T"],
            5,
        )
        self.assertEqual(
            resolved.body.latency,
            5,
        )

    def test_c3_resolves_to_three_cycle_parallel_region(self):
        resolved = resolve_program(
            make_v1_0_pair_program(),
            TimingEnvironment(
                {
                    "L_A": 3,
                    "L_B": 3,
                }
            ),
        )

        self.assertEqual(
            resolved.timing_values["T"],
            3,
        )
        self.assertEqual(
            resolved.body.latency,
            3,
        )

    def test_c4_is_rejected_by_symbolic_constraint(self):
        program = make_v1_0_pair_program()

        with self.assertRaises(
            ConstraintViolation
        ) as ctx:
            resolve_program(
                program,
                TimingEnvironment(
                    {
                        "L_A": 4,
                        "L_B": 7,
                    }
                ),
            )

        failures = ctx.exception.failures

        self.assertEqual(
            len(failures),
            1,
        )
        self.assertEqual(
            failures[0].name,
            "parallel_deadline",
        )
        self.assertEqual(
            failures[0].left_value,
            7,
        )
        self.assertEqual(
            failures[0].op,
            "<=",
        )
        self.assertEqual(
            failures[0].right_value,
            6,
        )
        self.assertFalse(
            failures[0].passed,
        )

    def test_c5_is_rejected_by_symbolic_constraint(self):
        with self.assertRaises(
            ConstraintViolation
        ) as ctx:
            resolve_program(
                make_v1_0_pair_program(),
                TimingEnvironment(
                    {
                        "L_A": 8,
                        "L_B": 3,
                    }
                ),
            )

        self.assertEqual(
            ctx.exception.failures[0].name,
            "parallel_deadline",
        )
        self.assertEqual(
            ctx.exception.failures[0].left_value,
            8,
        )

    def test_missing_generator_latency_is_rejected(self):
        with self.assertRaises(
            UnboundTimingVariable
        ) as ctx:
            resolve_program(
                make_v1_0_pair_program(),
                TimingEnvironment(
                    {
                        "L_A": 2,
                    }
                ),
            )

        self.assertEqual(
            ctx.exception.name,
            "L_B",
        )

    def test_environment_cannot_override_derived_binding(self):
        with self.assertRaises(
            ResolutionError
        ):
            resolve_program(
                make_v1_0_pair_program(),
                TimingEnvironment(
                    {
                        "L_A": 2,
                        "L_B": 5,
                        "T": 999,
                    }
                ),
            )

    def test_resolution_does_not_mutate_symbolic_ir(self):
        program = make_v1_0_pair_program()

        before = symbolic_hash(program)

        resolve_program(
            program,
            TimingEnvironment(
                {
                    "L_A": 5,
                    "L_B": 2,
                }
            ),
        )

        after = symbolic_hash(program)

        self.assertEqual(
            before,
            after,
        )


if __name__ == "__main__":
    unittest.main()
