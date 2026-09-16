import hashlib
import json
import unittest

from lair.ast import (
    GeneratorDecl,
    Invoke,
    StaticPar,
    SymbolicProgram,
    TimingBinding,
    TimingConst,
    TimingConstraint,
    TimingMax,
    TimingVar,
)
from lair.examples import make_v1_0_pair_program


def canonical_json(program: SymbolicProgram) -> str:
    return json.dumps(
        program.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )


class TimingExpressionTests(unittest.TestCase):
    def test_latency_variable_is_symbolic(self):
        var = TimingVar("L_A")

        self.assertEqual(
            var.to_dict(),
            {
                "kind": "timing_var",
                "name": "L_A",
            },
        )

    def test_max_expression_preserves_symbolic_operands(self):
        expr = TimingMax(
            TimingVar("L_A"),
            TimingVar("L_B"),
        )

        data = expr.to_dict()

        self.assertEqual(data["kind"], "timing_max")
        self.assertEqual(
            data["left"]["name"],
            "L_A",
        )
        self.assertEqual(
            data["right"]["name"],
            "L_B",
        )

    def test_negative_timing_constant_is_rejected(self):
        with self.assertRaises(ValueError):
            TimingConst(-1)


class ConstraintTests(unittest.TestCase):
    def test_constraint_is_structural_not_boolean(self):
        constraint = TimingConstraint(
            name="deadline",
            left=TimingVar("T"),
            op="<=",
            right=TimingConst(6),
        )

        self.assertEqual(
            constraint.to_dict()["op"],
            "<=",
        )
        self.assertEqual(
            constraint.to_dict()["left"]["name"],
            "T",
        )

    def test_invalid_constraint_operator_is_rejected(self):
        with self.assertRaises(ValueError):
            TimingConstraint(
                name="bad",
                left=TimingVar("A"),
                op="<",  # type: ignore[arg-type]
                right=TimingConst(1),
            )


class ProgramTests(unittest.TestCase):
    def test_v1_pair_contains_unresolved_generator_latencies(self):
        program = make_v1_0_pair_program()

        generators = program.to_dict()["generators"]

        self.assertEqual(
            generators[0]["latency_var"]["name"],
            "L_A",
        )
        self.assertEqual(
            generators[1]["latency_var"]["name"],
            "L_B",
        )

        # No concrete latency field exists in GeneratorDecl.
        self.assertNotIn(
            "latency",
            generators[0],
        )
        self.assertNotIn(
            "latency",
            generators[1],
        )

    def test_v1_pair_contains_symbolic_max_binding(self):
        program = make_v1_0_pair_program()

        binding = program.to_dict()["bindings"][0]

        self.assertEqual(
            binding["target"]["name"],
            "T",
        )
        self.assertEqual(
            binding["expr"]["kind"],
            "timing_max",
        )
        self.assertEqual(
            binding["expr"]["left"]["name"],
            "L_A",
        )
        self.assertEqual(
            binding["expr"]["right"]["name"],
            "L_B",
        )

    def test_v1_pair_contains_deadline_constraint(self):
        program = make_v1_0_pair_program()

        constraints = {
            item["name"]: item
            for item in program.to_dict()["constraints"]
        }

        deadline = constraints["parallel_deadline"]

        self.assertEqual(
            deadline["left"]["name"],
            "T",
        )
        self.assertEqual(
            deadline["op"],
            "<=",
        )
        self.assertEqual(
            deadline["right"]["value"],
            6,
        )

    def test_v1_pair_static_body_invokes_both_components(self):
        program = make_v1_0_pair_program()

        invokes = program.to_dict()["body"]["invokes"]

        self.assertEqual(
            [invoke["component"] for invoke in invokes],
            ["A", "B"],
        )

    def test_symbolic_ir_has_stable_canonical_hash(self):
        program_a = make_v1_0_pair_program()
        program_b = make_v1_0_pair_program()

        hash_a = hashlib.sha256(
            canonical_json(program_a).encode()
        ).hexdigest()

        hash_b = hashlib.sha256(
            canonical_json(program_b).encode()
        ).hexdigest()

        self.assertEqual(hash_a, hash_b)

    def test_duplicate_generator_instances_are_rejected(self):
        l_a = TimingVar("L_A")

        with self.assertRaises(ValueError):
            SymbolicProgram(
                generators=(
                    GeneratorDecl(
                        instance="A",
                        generator="toy",
                        kernel="one",
                        latency_var=l_a,
                    ),
                    GeneratorDecl(
                        instance="A",
                        generator="toy",
                        kernel="two",
                        latency_var=TimingVar("L_B"),
                    ),
                ),
                bindings=(),
                constraints=(),
                body=StaticPar(
                    invokes=(
                        Invoke("A", ("x",)),
                    ),
                ),
            )

    def test_undeclared_invocation_is_rejected(self):
        with self.assertRaises(ValueError):
            SymbolicProgram(
                generators=(
                    GeneratorDecl(
                        instance="A",
                        generator="toy",
                        kernel="one",
                        latency_var=TimingVar("L_A"),
                    ),
                ),
                bindings=(
                    TimingBinding(
                        target=TimingVar("T"),
                        expr=TimingVar("L_A"),
                    ),
                ),
                constraints=(),
                body=StaticPar(
                    invokes=(
                        Invoke("B", ("x",)),
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
