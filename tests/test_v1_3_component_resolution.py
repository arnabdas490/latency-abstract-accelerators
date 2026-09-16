import unittest

from lair.component_timing import (
    ComponentTimingInterface,
)
from lair.resolver import (
    ResolvedComponent,
    ResolvedStaticPar,
    ResolvedStaticSeq,
    resolve_component_decl,
)
from tests.test_v1_3_component_graph import (
    pair,
    tail,
)


class ComponentResolutionTests(
    unittest.TestCase
):
    def test_c1_pair_resolves_from_generator_timings(self):
        resolved = resolve_component_decl(
            pair(),
            generator_latencies={
                "A": 2,
                "B": 5,
            },
            component_interfaces={},
        )

        self.assertIsInstance(
            resolved,
            ResolvedComponent,
        )

        self.assertIsInstance(
            resolved.body,
            ResolvedStaticPar,
        )

        self.assertEqual(
            resolved.latency,
            5,
        )

        self.assertEqual(
            resolved.timing_values[
                "T_pair"
            ],
            5,
        )

        self.assertEqual(
            resolved.timing_interface(),
            ComponentTimingInterface(
                component="pair",
                latency=5,
            ),
        )

    def test_c1_tail_resolves_from_generator_timing(self):
        resolved = resolve_component_decl(
            tail(),
            generator_latencies={
                "A": 2,
            },
            component_interfaces={},
        )

        self.assertIsInstance(
            resolved.body,
            ResolvedStaticSeq,
        )

        self.assertEqual(
            resolved.latency,
            2,
        )

        self.assertEqual(
            resolved.timing_interface(),
            ComponentTimingInterface(
                component="tail",
                latency=2,
            ),
        )

    def test_c2_pair_still_exports_five(self):
        resolved = resolve_component_decl(
            pair(),
            generator_latencies={
                "A": 5,
                "B": 2,
            },
            component_interfaces={},
        )

        self.assertEqual(
            resolved.latency,
            5,
        )

        self.assertEqual(
            resolved.timing_interface(),
            ComponentTimingInterface(
                component="pair",
                latency=5,
            ),
        )

    def test_child_resolution_does_not_require_global_environment(self):
        resolved = resolve_component_decl(
            pair(),
            generator_latencies={
                "A": 2,
                "B": 5,
            },
            component_interfaces={},
        )

        self.assertEqual(
            set(
                resolved.timing_values
            ),
            {
                "T_pair",
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


if __name__ == "__main__":
    unittest.main()
