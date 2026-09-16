import unittest

from lair.ast import (
    ComponentDecl,
    GeneratorDecl,
    Invoke,
    StaticPar,
    StaticSeq,
    SymbolicProgram,
    TimingVar,
)
from lair.component_graph import (
    component_dependencies,
)
from lair.examples import (
    make_v1_0_pair_program,
)


def generators():
    return (
        GeneratorDecl(
            instance="A",
            generator="toy_generator",
            kernel="kernel_a",
            latency_var=TimingVar(
                "L_A"
            ),
        ),
        GeneratorDecl(
            instance="B",
            generator="toy_generator",
            kernel="kernel_b",
            latency_var=TimingVar(
                "L_B"
            ),
        ),
    )


def pair():
    return ComponentDecl(
        name="pair",
        args=("x",),
        latency_var=TimingVar(
            "T_pair"
        ),
        body=StaticPar(
            invokes=(
                Invoke(
                    component="A",
                    args=("x",),
                ),
                Invoke(
                    component="B",
                    args=("x",),
                ),
            ),
        ),
    )


def tail():
    return ComponentDecl(
        name="tail",
        args=("x",),
        latency_var=TimingVar(
            "T_tail"
        ),
        body=StaticSeq(
            steps=(
                Invoke(
                    component="A",
                    args=("x",),
                ),
            ),
        ),
    )


def pipeline():
    return ComponentDecl(
        name="pipeline",
        args=("x",),
        latency_var=TimingVar(
            "T_total"
        ),
        body=StaticSeq(
            steps=(
                Invoke(
                    component="pair",
                    args=("x",),
                ),
                Invoke(
                    component="tail",
                    args=("x",),
                ),
            ),
        ),
    )


def canonical_program():
    return SymbolicProgram(
        generators=generators(),
        bindings=(),
        constraints=(),
        components=(
            pair(),
            tail(),
            pipeline(),
        ),
        entry="pipeline",
    )


class ComponentDependencyGraphTests(
    unittest.TestCase
):
    def test_canonical_component_graph(self):
        self.assertEqual(
            component_dependencies(
                canonical_program()
            ),
            {
                "pair": (),
                "tail": (),
                "pipeline": (
                    "pair",
                    "tail",
                ),
            },
        )

    def test_generator_invocations_are_not_component_edges(self):
        graph = (
            component_dependencies(
                canonical_program()
            )
        )

        self.assertNotIn(
            "A",
            graph["pair"],
        )

        self.assertNotIn(
            "B",
            graph["pair"],
        )

        self.assertEqual(
            graph["tail"],
            (),
        )

    def test_repeated_component_invokes_produce_one_edge(self):
        repeated = ComponentDecl(
            name="pipeline",
            args=("x",),
            latency_var=TimingVar(
                "T_total"
            ),
            body=StaticSeq(
                steps=(
                    Invoke(
                        component="pair",
                        args=("x",),
                    ),
                    Invoke(
                        component="pair",
                        args=("x",),
                    ),
                ),
            ),
        )

        program = SymbolicProgram(
            generators=generators(),
            bindings=(),
            constraints=(),
            components=(
                pair(),
                repeated,
            ),
            entry="pipeline",
        )

        self.assertEqual(
            component_dependencies(
                program
            )["pipeline"],
            ("pair",),
        )

    def test_legacy_program_has_no_component_graph(self):
        self.assertEqual(
            component_dependencies(
                make_v1_0_pair_program()
            ),
            {},
        )


if __name__ == "__main__":
    unittest.main()
