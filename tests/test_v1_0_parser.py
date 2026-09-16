import hashlib
import json
import unittest
from pathlib import Path

from lair.calyx_backend import (
    lower_v1_pair_to_calyx,
)
from lair.environment import TimingEnvironment
from lair.examples import (
    make_v1_0_pair_program,
)
from lair.parser import (
    ParseError,
    parse_lair,
    parse_lair_file,
)
from lair.resolver import resolve_program


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/v1_0_pair.lair"


def canonical_hash(program) -> str:
    text = json.dumps(
        program.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        text.encode()
    ).hexdigest()


class ParserTests(unittest.TestCase):
    def test_source_matches_reference_symbolic_ir(self):
        parsed = parse_lair_file(SOURCE)
        reference = make_v1_0_pair_program()

        self.assertEqual(
            parsed.to_dict(),
            reference.to_dict(),
        )

    def test_source_contains_no_concrete_generator_latency(self):
        parsed = parse_lair_file(SOURCE)

        generators = parsed.to_dict()[
            "generators"
        ]

        self.assertNotIn(
            "latency",
            generators[0],
        )
        self.assertNotIn(
            "latency",
            generators[1],
        )

    def test_comments_and_whitespace_do_not_change_ir(self):
        source = SOURCE.read_text()

        modified = (
            "\n\n# extra comment\n"
            + source
            + "\n# trailing comment\n"
        )

        original = parse_lair(source)
        reparsed = parse_lair(modified)

        self.assertEqual(
            canonical_hash(original),
            canonical_hash(reparsed),
        )

    def test_nested_max_expression_parses(self):
        source = """
generator A = toy_generator(kernel_a) latency -> L_A
generator B = toy_generator(kernel_b) latency -> L_B
let T = max(max(L_A, 1), L_B)
require deadline: T <= 6
component pair(x) {
    static par {
        invoke A(x)
        invoke B(x)
    }
}
"""

        program = parse_lair(source)

        binding = program.to_dict()[
            "bindings"
        ][0]

        self.assertEqual(
            binding["expr"]["kind"],
            "timing_max",
        )
        self.assertEqual(
            binding["expr"]["left"]["kind"],
            "timing_max",
        )

    def test_unsupported_expression_is_rejected(self):
        source = """
generator A = toy_generator(kernel_a) latency -> L_A
let T = min(L_A, 4)
component pair(x) {
    static par {
        invoke A(x)
    }
}
"""

        with self.assertRaises(ParseError):
            parse_lair(source)

    def test_unknown_statement_is_rejected(self):
        source = """
banana A
"""

        with self.assertRaises(ParseError):
            parse_lair(source)

    def test_unclosed_component_is_rejected(self):
        source = """
generator A = toy_generator(kernel_a) latency -> L_A
component pair(x) {
    static par {
        invoke A(x)
    }
"""

        with self.assertRaises(ParseError):
            parse_lair(source)

    def test_parsed_source_runs_through_resolver(self):
        parsed = parse_lair_file(SOURCE)

        resolved = resolve_program(
            parsed,
            TimingEnvironment(
                {
                    "L_A": 5,
                    "L_B": 2,
                }
            ),
        )

        self.assertEqual(
            resolved.timing_values["T"],
            5,
        )

    def test_parsed_source_runs_through_backend(self):
        parsed = parse_lair_file(SOURCE)

        resolved = resolve_program(
            parsed,
            TimingEnvironment(
                {
                    "L_A": 2,
                    "L_B": 5,
                }
            ),
        )

        generated = lower_v1_pair_to_calyx(
            resolved
        )

        self.assertIn(
            "@interval(2) @go go: 1",
            generated,
        )

        self.assertIn(
            "@interval(5) @go go: 1",
            generated,
        )


if __name__ == "__main__":
    unittest.main()
