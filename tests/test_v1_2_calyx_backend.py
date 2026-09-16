import tempfile
import unittest
from pathlib import Path

from lair.calyx_backend import (
    CalyxLoweringError,
    lower_resolved_program_to_calyx,
    lower_v1_pair_to_calyx,
)
from lair.compiler import compile_lair_file
from lair.environment import TimingEnvironment
from lair.examples import make_v1_0_pair_program
from lair.generator_elaboration import (
    ToyGeneratorConfig,
)
from lair.parser import parse_lair_file
from lair.resolver import (
    ResolvedStaticSeq,
    resolve_program,
)


ROOT = Path(__file__).resolve().parents[1]

SOURCE = (
    ROOT
    / "examples/v1_2_hierarchical.lair"
)


class StructuralCalyxBackendTests(
    unittest.TestCase
):
    def test_v1_0_compatibility_alias_matches_generic_backend(self):
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
            lower_v1_pair_to_calyx(
                resolved
            ),
            lower_resolved_program_to_calyx(
                resolved
            ),
        )

    def test_hierarchical_control_lowers_recursively(self):
        resolved = resolve_program(
            parse_lair_file(
                SOURCE
            ),
            TimingEnvironment(
                {
                    "L_A": 2,
                    "L_B": 5,
                }
            ),
        )

        text = (
            lower_resolved_program_to_calyx(
                resolved
            )
        )

        self.assertEqual(
            text.count(
                "static invoke "
                "a(x=x.out)();"
            ),
            2,
        )

        self.assertEqual(
            text.count(
                "static invoke "
                "b(x=x.out)();"
            ),
            1,
        )

        # One static seq comes from the established runtime-loop
        # wrapper and one from the V1.2 resolved body.
        self.assertGreaterEqual(
            text.count(
                "static seq {"
            ),
            2,
        )

        self.assertIn(
            "static par {",
            text,
        )

    def test_inconsistent_hierarchical_latency_is_rejected(self):
        resolved = resolve_program(
            parse_lair_file(
                SOURCE
            ),
            TimingEnvironment(
                {
                    "L_A": 2,
                    "L_B": 5,
                }
            ),
        )

        self.assertIsInstance(
            resolved.body,
            ResolvedStaticSeq,
        )

        broken_body = ResolvedStaticSeq(
            steps=resolved.body.steps,
            latency=999,
        )

        broken = type(resolved)(
            timing_values=resolved.timing_values,
            generators=resolved.generators,
            bindings=resolved.bindings,
            constraint_checks=(
                resolved.constraint_checks
            ),
            body=broken_body,
        )

        with self.assertRaises(
            CalyxLoweringError
        ):
            lower_resolved_program_to_calyx(
                broken
            )

    def test_compiler_emits_hierarchical_calyx_for_c1(self):
        with tempfile.TemporaryDirectory(
            prefix="v1_2_backend_"
        ) as td:
            td = Path(td)

            rtl = td / "kernels.sv"
            calyx = td / "program.futil"

            result = compile_lair_file(
                SOURCE,
                ToyGeneratorConfig(
                    {
                        "A": 2,
                        "B": 5,
                    }
                ),
                rtl_output=rtl,
                calyx_output=calyx,
            )

            self.assertEqual(
                result.resolved
                .timing_values["T_pair"],
                5,
            )

            self.assertEqual(
                result.resolved
                .timing_values["T_total"],
                7,
            )

            self.assertTrue(
                rtl.exists()
            )

            self.assertTrue(
                calyx.exists()
            )

            text = calyx.read_text()

            self.assertEqual(
                text.count(
                    "static invoke "
                    "a(x=x.out)();"
                ),
                2,
            )


if __name__ == "__main__":
    unittest.main()
