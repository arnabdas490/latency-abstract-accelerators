import unittest
from dataclasses import fields

from lair.component_timing import (
    ComponentTimingInterface,
)


class ComponentTimingInterfaceTests(
    unittest.TestCase
):
    def test_interface_contains_only_component_and_latency(self):
        interface = ComponentTimingInterface(
            component="pair",
            latency=5,
        )

        self.assertEqual(
            tuple(
                field.name
                for field in fields(interface)
            ),
            (
                "component",
                "latency",
            ),
        )

        self.assertFalse(
            hasattr(
                interface,
                "body",
            )
        )

    def test_interface_serializes_without_implementation_details(self):
        interface = ComponentTimingInterface(
            component="pair",
            latency=5,
        )

        self.assertEqual(
            interface.to_dict(),
            {
                "component": "pair",
                "latency": 5,
            },
        )

    def test_empty_component_name_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            ComponentTimingInterface(
                component="",
                latency=5,
            )

    def test_negative_latency_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            ComponentTimingInterface(
                component="pair",
                latency=-1,
            )


if __name__ == "__main__":
    unittest.main()
