import unittest

from lair.ast import (
    ComponentDecl,
    GeneratorDecl,
    Invoke,
    StaticPar,
    StaticSeq,
    SymbolicProgram,
    TimingBinding,
    TimingConst,
    TimingVar,
)


def generator(
    instance,
    latency,
):
    return GeneratorDecl(
        instance=instance,
        generator="toy_generator",
        kernel=(
            "kernel_a"
            if instance == "A"
            else "kernel_b"
        ),
        latency_var=TimingVar(
            latency
        ),
    )


def component(
    name,
    latency,
    target,
    *,
    body_timing=None,
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
            timing_var=(
                None
                if body_timing is None
                else TimingVar(
                    body_timing
                )
            ),
        ),
    )


def program(
    *,
    generators=None,
    components=None,
    bindings=(),
    entry="pair",
):
    if generators is None:
        generators = (
            generator(
                "A",
                "L_A",
            ),
            generator(
                "B",
                "L_B",
            ),
        )

    if components is None:
        components = (
            component(
                "pair",
                "T_pair",
                "A",
            ),
        )

    return SymbolicProgram(
        generators=generators,
        bindings=bindings,
        constraints=(),
        components=components,
        entry=entry,
    )


class ComponentValidationTests(
    unittest.TestCase
):
    def test_duplicate_component_names_are_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            program(
                components=(
                    component(
                        "pair",
                        "T_pair",
                        "A",
                    ),
                    component(
                        "pair",
                        "T_other",
                        "B",
                    ),
                )
            )

    def test_generator_component_name_collision_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            program(
                components=(
                    component(
                        "A",
                        "T_pair",
                        "B",
                    ),
                ),
                entry="A",
            )

    def test_duplicate_component_timing_exports_are_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            program(
                components=(
                    component(
                        "pair",
                        "T_shared",
                        "A",
                    ),
                    component(
                        "tail",
                        "T_shared",
                        "A",
                    ),
                )
            )

    def test_component_export_generator_latency_collision_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            program(
                components=(
                    component(
                        "pair",
                        "L_A",
                        "A",
                    ),
                )
            )

    def test_component_export_binding_collision_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            program(
                bindings=(
                    TimingBinding(
                        target=TimingVar(
                            "T_pair"
                        ),
                        expr=TimingConst(
                            4
                        ),
                    ),
                )
            )

    def test_unknown_invoke_target_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            program(
                components=(
                    component(
                        "pair",
                        "T_pair",
                        "missing",
                    ),
                )
            )

    def test_unknown_entry_component_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            program(
                entry="missing"
            )

    def test_control_region_timing_cannot_collide_with_component_export(self):
        with self.assertRaises(
            ValueError
        ):
            program(
                components=(
                    component(
                        "pair",
                        "T_pair",
                        "A",
                        body_timing=(
                            "T_pair"
                        ),
                    ),
                )
            )


if __name__ == "__main__":
    unittest.main()
