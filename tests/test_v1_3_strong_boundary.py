import unittest

from lair.component_timing import (
    ComponentTimingInterface,
)
from lair.resolver import (
    resolve_component_decl,
)
from tests.test_v1_3_component_graph import (
    pair,
    pipeline,
    tail,
)


def resolve_children(
    *,
    a_latency: int,
    b_latency: int,
) -> dict[
    str,
    ComponentTimingInterface,
]:
    """
    Resolve actual child implementations and retain only their exported
    timing interfaces.

    The returned object contains no child bodies.
    """

    resolved_pair = resolve_component_decl(
        pair(),
        generator_latencies={
            "A": a_latency,
            "B": b_latency,
        },
        component_interfaces={},
    )

    resolved_tail = resolve_component_decl(
        tail(),
        generator_latencies={
            "A": a_latency,
        },
        component_interfaces={},
    )

    interfaces = {
        "pair": (
            resolved_pair
            .timing_interface()
        ),
        "tail": (
            resolved_tail
            .timing_interface()
        ),
    }

    # From this point onward, callers receive only the public contracts.
    return interfaces


def resolve_parent(
    interfaces: dict[
        str,
        ComponentTimingInterface,
    ],
):
    return resolve_component_decl(
        pipeline(),
        generator_latencies={},
        component_interfaces=interfaces,
    )


class StrongBoundaryTests(
    unittest.TestCase
):
    def test_c1_real_children_cross_interface_boundary(self):
        interfaces = resolve_children(
            a_latency=2,
            b_latency=5,
        )

        self.assertEqual(
            interfaces,
            {
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

        resolved_parent = resolve_parent(
            interfaces
        )

        self.assertEqual(
            resolved_parent.latency,
            7,
        )

        self.assertEqual(
            resolved_parent.timing_values,
            {
                "T_total": 7,
            },
        )

    def test_c2_same_pair_interface_changes_parent_through_tail(self):
        c1_interfaces = resolve_children(
            a_latency=2,
            b_latency=5,
        )

        c2_interfaces = resolve_children(
            a_latency=5,
            b_latency=2,
        )

        # Same leaf-latency multiset and same pair interface.
        self.assertEqual(
            c1_interfaces["pair"].latency,
            5,
        )

        self.assertEqual(
            c2_interfaces["pair"].latency,
            5,
        )

        # But tail changes because A is reused behind its own boundary.
        self.assertEqual(
            c1_interfaces["tail"].latency,
            2,
        )

        self.assertEqual(
            c2_interfaces["tail"].latency,
            5,
        )

        c1_parent = resolve_parent(
            c1_interfaces
        )

        c2_parent = resolve_parent(
            c2_interfaces
        )

        self.assertEqual(
            c1_parent.latency,
            7,
        )

        self.assertEqual(
            c2_parent.latency,
            10,
        )

    def test_parent_stage_receives_no_generator_facts_or_child_bodies(self):
        interfaces = resolve_children(
            a_latency=2,
            b_latency=5,
        )

        for interface in interfaces.values():
            self.assertFalse(
                hasattr(
                    interface,
                    "body",
                )
            )

        resolved_parent = resolve_component_decl(
            pipeline(),
            generator_latencies={},
            component_interfaces=interfaces,
        )

        self.assertEqual(
            set(
                resolved_parent.timing_values
            ),
            {
                "T_total",
            },
        )

        self.assertEqual(
            resolved_parent.latency,
            7,
        )


if __name__ == "__main__":
    unittest.main()
