import tempfile
import unittest
from pathlib import Path

from lair.compiler import compile_lair_file
from lair.generator_elaboration import (
    ToyGeneratorConfig,
)
from lair.resolver import ConstraintViolation


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/v1_0_pair.lair"


class CompilerDriverTests(unittest.TestCase):
    def test_canonical_program_compiles_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            rtl = root / "kernels.sv"
            calyx = root / "pair.futil"

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
                result.timing_environment.to_dict(),
                {
                    "L_A": 2,
                    "L_B": 5,
                },
            )

            self.assertEqual(
                result.resolved.timing_values["T"],
                5,
            )

    def test_calyx_references_generated_rtl_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            rtl = root / "kernels.sv"
            calyx = root / "pair.futil"

            compile_lair_file(
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

            text = calyx.read_text()

            self.assertIn(
                'extern "kernels.sv"',
                text,
            )

    def test_rejected_program_emits_rtl_but_no_calyx(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            rtl = root / "kernels.sv"
            calyx = root / "pair.futil"

            with self.assertRaises(
                ConstraintViolation
            ):
                compile_lair_file(
                    SOURCE,
                    ToyGeneratorConfig(
                        {
                            "A": 4,
                            "B": 7,
                        }
                    ),
                    rtl_output=rtl,
                    calyx_output=calyx,
                )

            self.assertTrue(
                rtl.exists()
            )

            self.assertFalse(
                calyx.exists()
            )

    def test_rejection_removes_stale_calyx_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            rtl = root / "kernels.sv"
            calyx = root / "pair.futil"

            calyx.write_text(
                "STALE SUCCESSFUL HARDWARE\n"
            )

            with self.assertRaises(
                ConstraintViolation
            ):
                compile_lair_file(
                    SOURCE,
                    ToyGeneratorConfig(
                        {
                            "A": 8,
                            "B": 3,
                        }
                    ),
                    rtl_output=rtl,
                    calyx_output=calyx,
                )

            self.assertFalse(
                calyx.exists()
            )


if __name__ == "__main__":
    unittest.main()
