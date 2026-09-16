import tempfile
import unittest
from pathlib import Path

from lair.compiler import (
    compile_lair_to_resolved,
)
from lair.generator_elaboration import (
    ToyGeneratorConfig,
)
from lair.resolver import (
    ConstraintViolation,
    ResolvedComponentProgram,
    ResolvedStaticSeq,
)


ROOT = Path(__file__).resolve().parents[1]

SOURCE = (
    ROOT
    / "examples/v1_3_components.lair"
)


class V13CompilerIntegrationTests(
    unittest.TestCase
):
    def test_c1_resolves_end_to_end_before_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            rtl = (
                Path(tmp)
                / "kernels.sv"
            )

            result = (
                compile_lair_to_resolved(
                    SOURCE,
                    ToyGeneratorConfig(
                        {
                            "A": 2,
                            "B": 5,
                        }
                    ),
                    rtl_output=rtl,
                )
            )

            self.assertTrue(
                rtl.exists()
            )

            self.assertIsInstance(
                result.resolved,
                ResolvedComponentProgram,
            )

            self.assertEqual(
                result.timing_environment.to_dict(),
                {
                    "L_A": 2,
                    "L_B": 5,
                },
            )

            self.assertEqual(
                result.resolved.timing_values,
                {
                    "L_A": 2,
                    "L_B": 5,
                    "T_pair": 5,
                    "T_tail": 2,
                    "T_total": 7,
                },
            )

    def test_c1_components_resolve_dependency_first(self):
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

            self.assertEqual(
                tuple(
                    component.name
                    for component
                    in result.resolved.components
                ),
                (
                    "pair",
                    "tail",
                    "pipeline",
                ),
            )

            self.assertEqual(
                tuple(
                    component.latency
                    for component
                    in result.resolved.components
                ),
                (
                    5,
                    2,
                    7,
                ),
            )

    def test_c1_pipeline_retains_abstraction_firewall(self):
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

            pipeline = next(
                component
                for component
                in result.resolved.components
                if component.name
                == "pipeline"
            )

            self.assertIsInstance(
                pipeline.body,
                ResolvedStaticSeq,
            )

            self.assertEqual(
                pipeline.timing_values,
                {
                    "T_total": 7,
                },
            )

            self.assertEqual(
                tuple(
                    step.component
                    for step
                    in pipeline.body.steps
                ),
                (
                    "pair",
                    "tail",
                ),
            )

            self.assertEqual(
                tuple(
                    step.latency
                    for step
                    in pipeline.body.steps
                ),
                (
                    5,
                    2,
                ),
            )

    def test_c2_reversal_is_rejected_after_real_elaboration(self):
        with tempfile.TemporaryDirectory() as tmp:
            rtl = (
                Path(tmp)
                / "kernels.sv"
            )

            with self.assertRaises(
                ConstraintViolation
            ) as ctx:
                compile_lair_to_resolved(
                    SOURCE,
                    ToyGeneratorConfig(
                        {
                            "A": 5,
                            "B": 2,
                        }
                    ),
                    rtl_output=rtl,
                )

            # Generator elaboration happened before global constraint
            # rejection.
            self.assertTrue(
                rtl.exists()
            )

            failure = (
                ctx.exception.failures[0]
            )

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


if __name__ == "__main__":
    unittest.main()
