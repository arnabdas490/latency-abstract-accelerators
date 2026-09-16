import hashlib
import json
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
from lair.examples import (
    make_v1_0_pair_program,
)


V1_0_CANONICAL_HASH = (
    "0f592c4575286d5b0db6653058d9c11"
    "b0c5417ecd08dc91e53a5ca4d405a6459"
)


def canonical_hash(
    program: SymbolicProgram,
) -> str:
    text = json.dumps(
        program.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        text.encode()
    ).hexdigest()


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


def pair_component():
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


def tail_component():
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


def pipeline_component():
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


class ComponentASTTests(
    unittest.TestCase
):
    def test_component_decl_serializes_exported_latency(self):
        data = (
            pair_component()
            .to_dict()
        )

        self.assertEqual(
            data["kind"],
            "component_decl",
        )

        self.assertEqual(
            data["name"],
            "pair",
        )

        self.assertEqual(
            data["latency_var"]["name"],
            "T_pair",
        )

        self.assertEqual(
            data["body"]["kind"],
            "static_par",
        )

    def test_component_body_preserves_nested_invocations(self):
        data = (
            pipeline_component()
            .to_dict()
        )

        self.assertEqual(
            data["body"]["kind"],
            "static_seq",
        )

        self.assertEqual(
            [
                step["component"]
                for step
                in data["body"]["steps"]
            ],
            [
                "pair",
                "tail",
            ],
        )

    def test_v1_3_program_serializes_components_and_entry(self):
        program = SymbolicProgram(
            generators=generators(),
            bindings=(),
            constraints=(),
            components=(
                pair_component(),
                tail_component(),
                pipeline_component(),
            ),
            entry="pipeline",
        )

        data = program.to_dict()

        self.assertNotIn(
            "body",
            data,
        )

        self.assertEqual(
            [
                component["name"]
                for component
                in data["components"]
            ],
            [
                "pair",
                "tail",
                "pipeline",
            ],
        )

        self.assertEqual(
            data["entry"],
            "pipeline",
        )

    def test_legacy_program_omits_v1_3_fields(self):
        data = (
            make_v1_0_pair_program()
            .to_dict()
        )

        self.assertIn(
            "body",
            data,
        )

        self.assertNotIn(
            "components",
            data,
        )

        self.assertNotIn(
            "entry",
            data,
        )

    def test_v1_0_canonical_hash_remains_unchanged(self):
        self.assertEqual(
            canonical_hash(
                make_v1_0_pair_program()
            ),
            V1_0_CANONICAL_HASH,
        )


if __name__ == "__main__":
    unittest.main()
