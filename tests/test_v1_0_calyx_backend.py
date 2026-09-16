from pathlib import Path
import unittest

from lair.calyx_backend import (
    CalyxLoweringError,
    lower_v1_pair_to_calyx,
)
from lair.environment import TimingEnvironment
from lair.examples import make_v1_0_pair_program
from lair.resolver import (
    ConstraintViolation,
    ResolvedStaticPar,
    resolve_program,
)


ROOT = Path(__file__).resolve().parents[1]


class CalyxBackendTests(unittest.TestCase):
    def test_backend_rejects_symbolic_program(self):
        symbolic = make_v1_0_pair_program()

        with self.assertRaises(TypeError):
            lower_v1_pair_to_calyx(symbolic)  # type: ignore[arg-type]

    def test_c1_lowers_resolved_intervals(self):
        resolved = resolve_program(
            make_v1_0_pair_program(),
            TimingEnvironment(
                {
                    "L_A": 2,
                    "L_B": 5,
                }
            ),
        )

        text = lower_v1_pair_to_calyx(resolved)

        self.assertIn(
            "@interval(2) @go go: 1",
            text,
        )
        self.assertIn(
            "@interval(5) @go go: 1",
            text,
        )

    def test_c2_lowers_reversed_intervals(self):
        resolved = resolve_program(
            make_v1_0_pair_program(),
            TimingEnvironment(
                {
                    "L_A": 5,
                    "L_B": 2,
                }
            ),
        )

        text = lower_v1_pair_to_calyx(resolved)

        first = text.index(
            "@interval(5) @go go: 1"
        )
        second = text.index(
            "@interval(2) @go go: 1"
        )

        self.assertLess(first, second)

    def test_c1_matches_known_good_v0_8_lowering(self):
        resolved = resolve_program(
            make_v1_0_pair_program(),
            TimingEnvironment(
                {
                    "L_A": 2,
                    "L_B": 5,
                }
            ),
        )

        generated = lower_v1_pair_to_calyx(resolved)

        reference = (
            ROOT
            / "examples/generated/v0_8_fixed_la.futil"
        ).read_text()

        self.assertEqual(
            generated,
            reference,
        )

    def test_backend_source_does_not_reference_contract_files(self):
        source = (
            ROOT
            / "lair/calyx_backend.py"
        ).read_text()

        forbidden = (
            "kernel_a.json",
            "kernel_b.json",
            "contracts/",
            "resolve_v0_4_contract",
            "v0_4_resolution.json",
        )

        for token in forbidden:
            self.assertNotIn(
                token,
                source,
                msg=f"Backend illegally depends on {token}",
            )

    def test_invalid_c4_never_reaches_backend(self):
        symbolic = make_v1_0_pair_program()

        with self.assertRaises(
            ConstraintViolation
        ):
            resolve_program(
                symbolic,
                TimingEnvironment(
                    {
                        "L_A": 4,
                        "L_B": 7,
                    }
                ),
            )

    def test_inconsistent_resolved_body_is_rejected(self):
        resolved = resolve_program(
            make_v1_0_pair_program(),
            TimingEnvironment(
                {
                    "L_A": 2,
                    "L_B": 5,
                }
            ),
        )

        broken = type(resolved)(
            timing_values=resolved.timing_values,
            generators=resolved.generators,
            bindings=resolved.bindings,
            constraint_checks=resolved.constraint_checks,
            body=ResolvedStaticPar(
                invokes=resolved.body.invokes,
                latency=999,
            ),
        )

        with self.assertRaises(
            CalyxLoweringError
        ):
            lower_v1_pair_to_calyx(broken)


if __name__ == "__main__":
    unittest.main()
