import hashlib
import json
import unittest

from lair.ast import (
    GeneratorDecl,
    Invoke,
    StaticPar,
    StaticSeq,
    SymbolicProgram,
    TimingBinding,
    TimingConst,
    TimingVar,
)
from lair.examples import make_v1_0_pair_program


V1_0_CANONICAL_HASH = (
    "0f592c4575286d5b0db6653058d9c11"
    "b0c5417ecd08dc91e53a5ca4d405a6459"
)


def canonical_hash(program: SymbolicProgram) -> str:
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
            latency_var=TimingVar("L_A"),
        ),
        GeneratorDecl(
            instance="B",
            generator="toy_generator",
            kernel="kernel_b",
            latency_var=TimingVar("L_B"),
        ),
    )


def hierarchical_body():
    return StaticSeq(
        steps=(
            StaticPar(
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
                timing_var=TimingVar(
                    "T_pair"
                ),
            ),
            Invoke(
                component="A",
                args=("x",),
            ),
        ),
        timing_var=TimingVar(
            "T_total"
        ),
    )


class StructuralControlASTTests(unittest.TestCase):
    def test_v1_0_symbolic_hash_is_preserved(self):
        self.assertEqual(
            canonical_hash(
                make_v1_0_pair_program()
            ),
            V1_0_CANONICAL_HASH,
        )

    def test_parallel_region_can_expose_inferred_timing(self):
        body = hierarchical_body()

        pair = body.steps[0]

        self.assertIsInstance(
            pair,
            StaticPar,
        )

        self.assertEqual(
            pair.to_dict()["timing_var"]["name"],
            "T_pair",
        )

    def test_static_sequence_preserves_nested_structure(self):
        body = hierarchical_body()

        data = body.to_dict()

        self.assertEqual(
            data["kind"],
            "static_seq",
        )

        self.assertEqual(
            data["timing_var"]["name"],
            "T_total",
        )

        self.assertEqual(
            data["steps"][0]["kind"],
            "static_par",
        )

        self.assertEqual(
            data["steps"][1]["kind"],
            "invoke",
        )

    def test_nested_undeclared_invoke_is_rejected(self):
        bad_body = StaticSeq(
            steps=(
                StaticPar(
                    invokes=(
                        Invoke(
                            component="A",
                            args=("x",),
                        ),
                    ),
                ),
                Invoke(
                    component="C",
                    args=("x",),
                ),
            ),
        )

        with self.assertRaises(ValueError):
            SymbolicProgram(
                generators=generators(),
                bindings=(),
                constraints=(),
                body=bad_body,
            )

    def test_control_timing_variable_collision_is_rejected(self):
        with self.assertRaises(ValueError):
            SymbolicProgram(
                generators=generators(),
                bindings=(
                    TimingBinding(
                        target=TimingVar(
                            "T_total"
                        ),
                        expr=TimingConst(4),
                    ),
                ),
                constraints=(),
                body=hierarchical_body(),
            )


if __name__ == "__main__":
    unittest.main()
