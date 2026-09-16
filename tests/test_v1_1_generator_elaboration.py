import unittest

from lair.generator_elaboration import (
    ElaborationResult,
    GeneratorResult,
    RTLArtifact,
)


def shared_rtl(module: str) -> RTLArtifact:
    return RTLArtifact(
        path="baselines/v0_8_fixed_li_kernels.sv",
        module=module,
        sha256="abc123",
    )


class RTLArtifactTests(unittest.TestCase):
    def test_artifact_records_file_and_module_separately(self):
        artifact = shared_rtl("kernel_a_li")

        self.assertEqual(
            artifact.path,
            "baselines/v0_8_fixed_li_kernels.sv",
        )

        self.assertEqual(
            artifact.module,
            "kernel_a_li",
        )


class GeneratorResultTests(unittest.TestCase):
    def test_logical_result_contains_resolved_latency(self):
        result = GeneratorResult(
            instance="A",
            generator="toy_generator",
            kernel="kernel_a",
            latency_var="L_A",
            latency=2,
            rtl=shared_rtl("kernel_a_li"),
        )

        self.assertEqual(result.latency, 2)
        self.assertEqual(result.latency_var, "L_A")
        self.assertEqual(
            result.rtl.module,
            "kernel_a_li",
        )

    def test_zero_latency_is_rejected(self):
        with self.assertRaises(ValueError):
            GeneratorResult(
                instance="A",
                generator="toy_generator",
                kernel="kernel_a",
                latency_var="L_A",
                latency=0,
                rtl=shared_rtl("kernel_a_li"),
            )


class ElaborationResultTests(unittest.TestCase):
    def test_shared_physical_rtl_can_back_multiple_generators(self):
        a = GeneratorResult(
            instance="A",
            generator="toy_generator",
            kernel="kernel_a",
            latency_var="L_A",
            latency=2,
            rtl=shared_rtl("kernel_a_li"),
        )

        b = GeneratorResult(
            instance="B",
            generator="toy_generator",
            kernel="kernel_b",
            latency_var="L_B",
            latency=5,
            rtl=shared_rtl("kernel_b_li"),
        )

        result = ElaborationResult(
            generators=(a, b),
        )

        self.assertEqual(
            result.by_instance()["A"].rtl.path,
            result.by_instance()["B"].rtl.path,
        )

        self.assertNotEqual(
            result.by_instance()["A"].rtl.module,
            result.by_instance()["B"].rtl.module,
        )

    def test_duplicate_instances_are_rejected(self):
        a1 = GeneratorResult(
            instance="A",
            generator="toy_generator",
            kernel="kernel_a",
            latency_var="L_A",
            latency=2,
            rtl=shared_rtl("kernel_a_li"),
        )

        a2 = GeneratorResult(
            instance="A",
            generator="toy_generator",
            kernel="kernel_b",
            latency_var="L_B",
            latency=5,
            rtl=shared_rtl("kernel_b_li"),
        )

        with self.assertRaises(ValueError):
            ElaborationResult(
                generators=(a1, a2),
            )

    def test_duplicate_latency_variables_are_rejected(self):
        a = GeneratorResult(
            instance="A",
            generator="toy_generator",
            kernel="kernel_a",
            latency_var="L",
            latency=2,
            rtl=shared_rtl("kernel_a_li"),
        )

        b = GeneratorResult(
            instance="B",
            generator="toy_generator",
            kernel="kernel_b",
            latency_var="L",
            latency=5,
            rtl=shared_rtl("kernel_b_li"),
        )

        with self.assertRaises(ValueError):
            ElaborationResult(
                generators=(a, b),
            )


class ToyGeneratorExecutionTests(unittest.TestCase):
    def test_canonical_pair_emits_real_shared_rtl(self):
        import tempfile
        from pathlib import Path

        from lair.examples import make_v1_0_pair_program
        from lair.generator_elaboration import (
            ToyGeneratorConfig,
            elaborate_toy_generators,
        )

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "kernels.sv"

            result = elaborate_toy_generators(
                make_v1_0_pair_program(),
                ToyGeneratorConfig(
                    {
                        "A": 2,
                        "B": 5,
                    }
                ),
                output,
            )

            self.assertTrue(output.exists())

            text = output.read_text()

            self.assertIn(
                "module kernel_a_li",
                text,
            )
            self.assertIn(
                "module kernel_b_li",
                text,
            )
            self.assertIn(
                "localparam integer LATENCY = 2;",
                text,
            )
            self.assertIn(
                "localparam integer LATENCY = 5;",
                text,
            )

            by_instance = result.by_instance()

            self.assertEqual(
                by_instance["A"].latency,
                2,
            )
            self.assertEqual(
                by_instance["B"].latency,
                5,
            )

            self.assertEqual(
                by_instance["A"].rtl.sha256,
                by_instance["B"].rtl.sha256,
            )

    def test_reversed_configuration_is_not_order_dependent(self):
        import tempfile
        from pathlib import Path

        from lair.examples import make_v1_0_pair_program
        from lair.generator_elaboration import (
            ToyGeneratorConfig,
            elaborate_toy_generators,
        )

        with tempfile.TemporaryDirectory() as tmp:
            result = elaborate_toy_generators(
                make_v1_0_pair_program(),
                ToyGeneratorConfig(
                    {
                        "A": 5,
                        "B": 2,
                    }
                ),
                Path(tmp) / "kernels.sv",
            )

            by_instance = result.by_instance()

            self.assertEqual(
                by_instance["A"].latency,
                5,
            )
            self.assertEqual(
                by_instance["B"].latency,
                2,
            )

    def test_missing_configuration_emits_no_rtl(self):
        import tempfile
        from pathlib import Path

        from lair.examples import make_v1_0_pair_program
        from lair.generator_elaboration import (
            GeneratorElaborationError,
            ToyGeneratorConfig,
            elaborate_toy_generators,
        )

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "kernels.sv"

            with self.assertRaises(
                GeneratorElaborationError
            ):
                elaborate_toy_generators(
                    make_v1_0_pair_program(),
                    ToyGeneratorConfig(
                        {
                            "A": 2,
                        }
                    ),
                    output,
                )

            self.assertFalse(
                output.exists()
            )

    def test_generated_artifact_sha_matches_file(self):
        import hashlib
        import tempfile
        from pathlib import Path

        from lair.examples import make_v1_0_pair_program
        from lair.generator_elaboration import (
            ToyGeneratorConfig,
            elaborate_toy_generators,
        )

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "kernels.sv"

            result = elaborate_toy_generators(
                make_v1_0_pair_program(),
                ToyGeneratorConfig(
                    {
                        "A": 3,
                        "B": 3,
                    }
                ),
                output,
            )

            actual = hashlib.sha256(
                output.read_bytes()
            ).hexdigest()

            for generated in result.generators:
                self.assertEqual(
                    generated.rtl.sha256,
                    actual,
                )



if __name__ == "__main__":
    unittest.main()
