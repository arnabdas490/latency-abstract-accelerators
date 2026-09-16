import unittest

from lair.component_timing import (
    ComponentTimingInterface,
)
from lair.resolver import (
    ResolutionError,
    ResolvedInvoke,
    ResolvedStaticSeq,
    resolve_component_decl,
)
from tests.test_v1_3_component_graph import (
    pipeline,
)


class ParentTimingFirewallTests(
    unittest.TestCase
):
    def test_c1_parent_resolves_from_interfaces_only(self):
        resolved = resolve_component_decl(
            pipeline(),
            generator_latencies={},
            component_interfaces={
                "pair": ComponentTimingInterface(
                    component="pair",
                    latency=5,
                ),
                "tail": ComponentTimingInterface(
                    component="tail",
                    latency=2,
                ),
            },
        )

        self.assertIsInstance(
            resolved.body,
            ResolvedStaticSeq,
        )

        self.assertEqual(
            resolved.latency,
            7,
        )

        self.assertEqual(
            resolved.timing_values,
            {
                "T_total": 7,
            },
        )

        self.assertEqual(
            tuple(
                step.latency
                for step in resolved.body.steps
            ),
            (
                5,
                2,
            ),
        )

        self.assertTrue(
            all(
                isinstance(
                    step,
                    ResolvedInvoke,
                )
                for step
                in resolved.body.steps
            )
        )

    def test_c2_parent_resolves_to_ten_from_interfaces_only(self):
        resolved = resolve_component_decl(
            pipeline(),
            generator_latencies={},
            component_interfaces={
                "pair": ComponentTimingInterface(
                    component="pair",
                    latency=5,
                ),
                "tail": ComponentTimingInterface(
                    component="tail",
                    latency=5,
                ),
            },
        )

        self.assertEqual(
            resolved.latency,
            10,
        )

        self.assertEqual(
            resolved.timing_values,
            {
                "T_total": 10,
            },
        )

    def test_parent_requires_no_generator_timing_facts(self):
        resolved = resolve_component_decl(
            pipeline(),
            generator_latencies={},
            component_interfaces={
                "pair": ComponentTimingInterface(
                    component="pair",
                    latency=5,
                ),
                "tail": ComponentTimingInterface(
                    component="tail",
                    latency=2,
                ),
            },
        )

        self.assertNotIn(
            "L_A",
            resolved.timing_values,
        )

        self.assertNotIn(
            "L_B",
            resolved.timing_values,
        )

        self.assertNotIn(
            "T_pair",
            resolved.timing_values,
        )

        self.assertNotIn(
            "T_tail",
            resolved.timing_values,
        )

        self.assertEqual(
            resolved.timing_values,
            {
                "T_total": 7,
            },
        )

    def test_parent_fails_when_child_interface_is_missing(self):
        with self.assertRaisesRegex(
            ResolutionError,
            r"No resolved latency for component: tail",
        ):
            resolve_component_decl(
                pipeline(),
                generator_latencies={},
                component_interfaces={
                    "pair": ComponentTimingInterface(
                        component="pair",
                        latency=5,
                    ),
                },
            )

    def test_pipeline_symbolic_body_contains_only_child_components(self):
        symbolic = pipeline()

        invoked = tuple(
            step.component
            for step in symbolic.body.steps
        )

        self.assertEqual(
            invoked,
            (
                "pair",
                "tail",
            ),
        )

        self.assertNotIn(
            "A",
            invoked,
        )

        self.assertNotIn(
            "B",
            invoked,
        )


if __name__ == "__main__":
    unittest.main()
