import hashlib
import json
import unittest
from pathlib import Path

from lair.ast import (
    ComponentDecl,
    Invoke,
    StaticPar,
    StaticSeq,
)
from lair.parser import (
    ParseError,
    parse_lair,
    parse_lair_file,
)


ROOT = Path(__file__).resolve().parents[1]

V1_0_SOURCE = (
    ROOT / "examples/v1_0_pair.lair"
)

V1_2_SOURCE = (
    ROOT / "examples/v1_2_hierarchical.lair"
)

V1_0_HASH = (
    "0f592c4575286d5b0db6653058d9c11"
    "b0c5417ecd08dc91e53a5ca4d405a6459"
)


V1_3_SOURCE = """
generator A = toy_generator(kernel_a) latency -> L_A
generator B = toy_generator(kernel_b) latency -> L_B

require positive_latency_a: L_A >= 1
require positive_latency_b: L_B >= 1
require total_deadline: T_total <= 8

component pair(x) latency -> T_pair {
    static par {
        invoke A(x)
        invoke B(x)
    }
}

component tail(x) latency -> T_tail {
    static seq {
        invoke A(x)
    }
}

component pipeline(x) latency -> T_total {
    static seq {
        invoke pair(x)
        invoke tail(x)
    }
}

entry pipeline
"""


def canonical_hash(program) -> str:
    text = json.dumps(
        program.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        text.encode()
    ).hexdigest()


class V13ParserTests(
    unittest.TestCase
):
    def test_three_components_and_entry_are_parsed(self):
        program = parse_lair(
            V1_3_SOURCE
        )

        self.assertIsNone(
            program.body
        )

        self.assertEqual(
            tuple(
                component.name
                for component
                in program.components
            ),
            (
                "pair",
                "tail",
                "pipeline",
            ),
        )

        self.assertEqual(
            program.entry,
            "pipeline",
        )

        self.assertEqual(
            program.bindings,
            (),
        )

    def test_component_exports_are_preserved(self):
        program = parse_lair(
            V1_3_SOURCE
        )

        self.assertTrue(
            all(
                isinstance(
                    component,
                    ComponentDecl,
                )
                for component
                in program.components
            )
        )

        self.assertEqual(
            tuple(
                component.latency_var.name
                for component
                in program.components
            ),
            (
                "T_pair",
                "T_tail",
                "T_total",
            ),
        )

    def test_component_bodies_preserve_module_boundary(self):
        program = parse_lair(
            V1_3_SOURCE
        )

        pair, tail, pipeline = (
            program.components
        )

        self.assertIsInstance(
            pair.body,
            StaticPar,
        )

        self.assertIsInstance(
            tail.body,
            StaticSeq,
        )

        self.assertIsInstance(
            pipeline.body,
            StaticSeq,
        )

        self.assertEqual(
            tuple(
                invoke.component
                for invoke
                in pair.body.invokes
            ),
            (
                "A",
                "B",
            ),
        )

        self.assertEqual(
            tuple(
                step.component
                for step
                in pipeline.body.steps
                if isinstance(
                    step,
                    Invoke,
                )
            ),
            (
                "pair",
                "tail",
            ),
        )

    def test_missing_entry_is_rejected(self):
        source = (
            V1_3_SOURCE
            .replace(
                "entry pipeline",
                "",
            )
        )

        with self.assertRaisesRegex(
            ParseError,
            r"contains no entry",
        ):
            parse_lair(
                source
            )

    def test_legacy_and_v1_3_component_forms_cannot_mix(self):
        source = """
generator A = toy_generator(kernel_a) latency -> L_A

component old(x) {
    static seq {
        invoke A(x)
    }
}

component newer(x) latency -> T_new {
    static seq {
        invoke A(x)
    }
}

entry newer
"""

        with self.assertRaises(
            ParseError
        ):
            parse_lair(
                source
            )

    def test_v1_0_parse_hash_is_unchanged(self):
        program = parse_lair_file(
            V1_0_SOURCE
        )

        self.assertEqual(
            canonical_hash(
                program
            ),
            V1_0_HASH,
        )

    def test_v1_2_remains_legacy_single_body_program(self):
        program = parse_lair_file(
            V1_2_SOURCE
        )

        self.assertIsNotNone(
            program.body
        )

        self.assertEqual(
            program.components,
            (),
        )

        self.assertIsNone(
            program.entry
        )


if __name__ == "__main__":
    unittest.main()
