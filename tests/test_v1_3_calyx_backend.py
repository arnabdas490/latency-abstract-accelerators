import tempfile
import unittest
from pathlib import Path

from lair.calyx_backend import (
    CalyxLoweringError,
    lower_resolved_component_program_to_calyx,
)
from lair.compiler import (
    compile_lair_file,
    compile_lair_to_resolved,
)
from lair.generator_elaboration import (
    ToyGeneratorConfig,
)
from lair.resolver import (
    ResolvedComponent,
    ResolvedComponentProgram,
)


ROOT = Path(__file__).resolve().parents[1]

SOURCE = (
    ROOT
    / "examples/v1_3_components.lair"
)


class V13CalyxBackendTests(
    unittest.TestCase
):
    def test_c1_component_program_lowers_to_toy_calyx(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = (
                compile_lair_to_resolved(
                    SOURCE,
                    ToyGeneratorConfig(
                        {
                            "A": 2,
                            "B": 5,
                        }
                    ),
                    rtl_output=(
                        root / "kernels.sv"
                    ),
                )
            )

            text = (
                lower_resolved_component_program_to_calyx(
                    result.resolved,
                    extern_rtl="kernels.sv",
                )
            )

            self.assertIn(
                'extern "kernels.sv"',
                text,
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

            self.assertIn(
                "static par {",
                text,
            )

    def test_c1_backend_expands_component_invokes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = (
                compile_lair_to_resolved(
                    SOURCE,
                    ToyGeneratorConfig(
                        {
                            "A": 2,
                            "B": 5,
                        }
                    ),
                    rtl_output=(
                        Path(tmp)
                        / "kernels.sv"
                    ),
                )
            )

            text = (
                lower_resolved_component_program_to_calyx(
                    result.resolved
                )
            )

            # pair/tail are compiler-IR component names, not physical
            # primitive cells in the current toy backend.
            self.assertNotIn(
                "invoke pair",
                text,
            )

            self.assertNotIn(
                "invoke tail",
                text,
            )

    def test_compiler_emits_v1_3_calyx_for_c1(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            rtl = (
                root / "kernels.sv"
            )

            calyx = (
                root / "program.futil"
            )

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

            self.assertTrue(
                rtl.exists()
            )

            self.assertTrue(
                calyx.exists()
            )

            self.assertEqual(
                result.resolved
                .timing_values[
                    "T_total"
                ],
                7,
            )

            text = calyx.read_text()

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

    def test_backend_rejects_broken_component_export_latency(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = (
                compile_lair_to_resolved(
                    SOURCE,
                    ToyGeneratorConfig(
                        {
                            "A": 2,
                            "B": 5,
                        }
                    ),
                    rtl_output=(
                        Path(tmp)
                        / "kernels.sv"
                    ),
                )
            )

            resolved = result.resolved

            pair = resolved.components[0]

            broken_pair = ResolvedComponent(
                name=pair.name,
                args=pair.args,
                latency=999,
                body=pair.body,
                timing_values=(
                    pair.timing_values
                ),
            )

            broken = ResolvedComponentProgram(
                timing_values=(
                    resolved.timing_values
                ),
                generators=(
                    resolved.generators
                ),
                bindings=(
                    resolved.bindings
                ),
                constraint_checks=(
                    resolved.constraint_checks
                ),
                components=(
                    broken_pair,
                    *resolved.components[1:],
                ),
                entry=resolved.entry,
            )

            with self.assertRaises(
                CalyxLoweringError
            ):
                lower_resolved_component_program_to_calyx(
                    broken
                )


if __name__ == "__main__":
    unittest.main()
