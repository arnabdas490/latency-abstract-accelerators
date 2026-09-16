import hashlib
import json
import unittest
from pathlib import Path

from lair.ast import (
    Invoke,
    StaticPar,
    StaticSeq,
)
from lair.environment import (
    TimingEnvironment,
)
from lair.parser import (
    ParseError,
    parse_lair,
    parse_lair_file,
)
from lair.resolver import (
    ConstraintViolation,
    resolve_program,
)


ROOT = Path(__file__).resolve().parents[1]

V1_SOURCE = (
    ROOT / "examples/v1_0_pair.lair"
)

V1_2_SOURCE = (
    ROOT / "examples/v1_2_hierarchical.lair"
)

V1_0_HASH = (
    "0f592c4575286d5b0db6653058d9c11"
    "b0c5417ecd08dc91e53a5ca4d405a6459"
)


def canonical_hash(program) -> str:
    text = json.dumps(
        program.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        text.encode()
    ).hexdigest()


class StructuralParserTests(unittest.TestCase):
    def test_v1_0_parse_result_remains_unchanged(self):
        program = parse_lair_file(
            V1_SOURCE
        )

        self.assertEqual(
            canonical_hash(program),
            V1_0_HASH,
        )

    def test_hierarchical_source_has_no_manual_timing_bindings(self):
        program = parse_lair_file(
            V1_2_SOURCE
        )

        self.assertEqual(
            program.bindings,
            (),
        )

    def test_hierarchical_control_shape_is_parsed(self):
        program = parse_lair_file(
            V1_2_SOURCE
        )

        self.assertIsInstance(
            program.body,
            StaticSeq,
        )

        self.assertEqual(
            program.body.timing_var.name,
            "T_total",
        )

        self.assertEqual(
            len(program.body.steps),
            2,
        )

        pair = program.body.steps[0]
        final_a = program.body.steps[1]

        self.assertIsInstance(
            pair,
            StaticPar,
        )

        self.assertEqual(
            pair.timing_var.name,
            "T_pair",
        )

        self.assertIsInstance(
            final_a,
            Invoke,
        )

        self.assertEqual(
            final_a.component,
            "A",
        )

    def test_parsed_c1_infers_seven_cycles(self):
        program = parse_lair_file(
            V1_2_SOURCE
        )

        resolved = resolve_program(
            program,
            TimingEnvironment(
                {
                    "L_A": 2,
                    "L_B": 5,
                }
            ),
        )

        self.assertEqual(
            resolved.timing_values[
                "T_pair"
            ],
            5,
        )

        self.assertEqual(
            resolved.timing_values[
                "T_total"
            ],
            7,
        )

    def test_parsed_c2_reversal_rejects(self):
        program = parse_lair_file(
            V1_2_SOURCE
        )

        with self.assertRaises(
            ConstraintViolation
        ) as ctx:
            resolve_program(
                program,
                TimingEnvironment(
                    {
                        "L_A": 5,
                        "L_B": 2,
                    }
                ),
            )

        self.assertEqual(
            ctx.exception.failures[0].name,
            "total_deadline",
        )

        self.assertEqual(
            ctx.exception.failures[0].left_value,
            10,
        )

    def test_unclosed_nested_region_is_rejected(self):
        source = """
generator A = toy_generator(kernel_a) latency -> L_A

component pipeline(x) {
    static seq -> T_total {
        static par -> T_pair {
            invoke A(x)
    }
}
"""

        with self.assertRaises(
            ParseError
        ):
            parse_lair(
                source
            )


if __name__ == "__main__":
    unittest.main()
