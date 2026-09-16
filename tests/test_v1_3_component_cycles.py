import unittest

from lair.ast import (
    ComponentDecl,
    GeneratorDecl,
    Invoke,
    StaticSeq,
    SymbolicProgram,
    TimingVar,
)
from lair.component_graph import (
    topological_component_order,
)
from lair.examples import (
    make_v1_0_pair_program,
)
from tests.test_v1_3_component_graph import (
    canonical_program,
)


def generator_a():
    return GeneratorDecl(
        instance="A",
        generator="toy_generator",
        kernel="kernel_a",
        latency_var=TimingVar(
            "L_A"
        ),
    )


def component(
    name,
    latency,
    target,
):
    return ComponentDecl(
        name=name,
        args=("x",),
        latency_var=TimingVar(
            latency
        ),
        body=StaticSeq(
            steps=(
                Invoke(
                    component=target,
                    args=("x",),
                ),
            ),
        ),
    )


class ComponentCycleTests(
    unittest.TestCase
):
    def test_canonical_program_orders_children_before_parent(self):
        self.assertEqual(
            topological_component_order(
                canonical_program()
            ),
            (
                "pair",
                "tail",
                "pipeline",
            ),
        )

    def test_direct_self_recursion_is_rejected(self):
        recursive = component(
            "loop",
            "T_loop",
            "loop",
        )

        program = SymbolicProgram(
            generators=(
                generator_a(),
            ),
            bindings=(),
            constraints=(),
            components=(
                recursive,
            ),
            entry="loop",
        )

        with self.assertRaisesRegex(
            ValueError,
            r"loop -> loop",
        ):
            topological_component_order(
                program
            )

    def test_indirect_recursion_is_rejected(self):
        first = component(
            "first",
            "T_first",
            "second",
        )

        second = component(
            "second",
            "T_second",
            "first",
        )

        program = SymbolicProgram(
            generators=(
                generator_a(),
            ),
            bindings=(),
            constraints=(),
            components=(
                first,
                second,
            ),
            entry="first",
        )

        with self.assertRaisesRegex(
            ValueError,
            r"first -> second -> first",
        ):
            topological_component_order(
                program
            )

    def test_legacy_program_has_empty_component_order(self):
        self.assertEqual(
            topological_component_order(
                make_v1_0_pair_program()
            ),
            (),
        )


if __name__ == "__main__":
    unittest.main()
