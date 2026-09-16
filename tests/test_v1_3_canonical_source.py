import hashlib
import json
import unittest
from pathlib import Path

from lair.ast import (
    Invoke,
)
from lair.parser import (
    parse_lair_file,
)


ROOT = Path(__file__).resolve().parents[1]

SOURCE = (
    ROOT
    / "examples/v1_3_components.lair"
)

IR_ARCHIVE = (
    ROOT
    / "results/v1_3_canonical_ir.json"
)

HASH_MANIFEST = (
    ROOT
    / "results/v1_3_canonical_hashes.json"
)


def canonical_ir_text(
    program,
) -> str:
    return json.dumps(
        program.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )


class CanonicalV13SourceTests(
    unittest.TestCase
):
    def test_canonical_source_has_no_manual_timing_bindings(self):
        program = parse_lair_file(
            SOURCE
        )

        self.assertEqual(
            program.bindings,
            (),
        )

        self.assertNotIn(
            "let ",
            SOURCE.read_text(),
        )

    def test_canonical_component_boundary_shape(self):
        program = parse_lair_file(
            SOURCE
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

        self.assertEqual(
            program.entry,
            "pipeline",
        )

        pipeline = next(
            component
            for component
            in program.components
            if component.name
            == "pipeline"
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

    def test_source_hash_matches_frozen_manifest(self):
        manifest = json.loads(
            HASH_MANIFEST.read_text()
        )

        current = hashlib.sha256(
            SOURCE.read_bytes()
        ).hexdigest()

        self.assertEqual(
            current,
            manifest[
                "source_sha256"
            ],
        )

    def test_symbolic_ir_matches_frozen_archive_and_hash(self):
        program = parse_lair_file(
            SOURCE
        )

        manifest = json.loads(
            HASH_MANIFEST.read_text()
        )

        archived = json.loads(
            IR_ARCHIVE.read_text()
        )

        self.assertEqual(
            program.to_dict(),
            archived,
        )

        current_hash = hashlib.sha256(
            canonical_ir_text(
                program
            ).encode()
        ).hexdigest()

        self.assertEqual(
            current_hash,
            manifest[
                "symbolic_ir_sha256"
            ],
        )


if __name__ == "__main__":
    unittest.main()
