from __future__ import annotations

import re
from pathlib import Path

from lair.ast import (
    ComponentDecl,
    GeneratorDecl,
    Invoke,
    StaticPar,
    StaticSeq,
    SymbolicProgram,
    TimingBinding,
    TimingConst,
    TimingConstraint,
    TimingExpr,
    TimingMax,
    TimingVar,
)


class ParseError(ValueError):
    """Raised when LAIR source cannot be parsed."""


IDENT = r"[A-Za-z_][A-Za-z0-9_]*"


def _clean_lines(text: str) -> list[str]:
    lines = []

    for raw in text.splitlines():
        # V1.0 supports shell/Python-style comments.
        line = raw.split("#", 1)[0].strip()

        if line:
            lines.append(line)

    return lines


def _split_top_level_comma(text: str) -> tuple[str, str]:
    depth = 0

    for i, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1

            if depth < 0:
                raise ParseError(
                    f"Unbalanced parentheses in expression: {text}"
                )

        elif char == "," and depth == 0:
            return (
                text[:i].strip(),
                text[i + 1:].strip(),
            )

    raise ParseError(
        f"Expected top-level comma in expression: {text}"
    )


def parse_timing_expr(text: str) -> TimingExpr:
    text = text.strip()

    if re.fullmatch(r"\d+", text):
        return TimingConst(int(text))

    if re.fullmatch(IDENT, text):
        return TimingVar(text)

    max_match = re.fullmatch(
        r"max\s*\((.*)\)",
        text,
    )

    if max_match:
        inside = max_match.group(1)

        left_text, right_text = _split_top_level_comma(
            inside
        )

        return TimingMax(
            parse_timing_expr(left_text),
            parse_timing_expr(right_text),
        )

    raise ParseError(
        f"Unsupported timing expression: {text}"
    )


def _split_constraint(
    text: str,
) -> tuple[str, str, str]:
    depth = 0
    i = 0

    while i < len(text):
        char = text[i]

        if char == "(":
            depth += 1

        elif char == ")":
            depth -= 1

            if depth < 0:
                raise ParseError(
                    f"Unbalanced parentheses: {text}"
                )

        elif depth == 0:
            for op in ("<=", ">=", "=="):
                if text.startswith(op, i):
                    left = text[:i].strip()
                    right = text[i + len(op):].strip()

                    if not left or not right:
                        raise ParseError(
                            f"Malformed constraint: {text}"
                        )

                    return left, op, right

        i += 1

    raise ParseError(
        f"No supported comparison operator in constraint: {text}"
    )


def _parse_invoke(line: str) -> Invoke | None:
    match = re.fullmatch(
        rf"invoke\s+({IDENT})"
        rf"\s*\(\s*([^)]*)\s*\)",
        line,
    )

    if match is None:
        return None

    component, args_text = match.groups()

    args = tuple(
        arg.strip()
        for arg in args_text.split(",")
        if arg.strip()
    )

    return Invoke(
        component=component,
        args=args,
    )


def _parse_control(
    lines: list[str],
    start: int,
) -> tuple[
    StaticPar | StaticSeq,
    int,
]:
    """
    Parse one static-control region.

    Returns:
        (control_node, index_after_closing_brace)
    """

    if start >= len(lines):
        raise ParseError(
            "Expected static control region."
        )

    header = lines[start]

    match = re.fullmatch(
        rf"static\s+(par|seq)"
        rf"(?:\s*->\s*({IDENT}))?"
        rf"\s*\{{",
        header,
    )

    if match is None:
        raise ParseError(
            "Expected 'static par {' or "
            "'static seq {' control region; "
            f"got: {header}"
        )

    kind, timing_name = match.groups()

    timing_var = (
        None
        if timing_name is None
        else TimingVar(timing_name)
    )

    i = start + 1

    if kind == "par":
        invokes = []

        while i < len(lines):
            line = lines[i]

            if line == "}":
                if not invokes:
                    raise ParseError(
                        "Static parallel region "
                        "contains no invokes."
                    )

                return (
                    StaticPar(
                        invokes=tuple(invokes),
                        timing_var=timing_var,
                    ),
                    i + 1,
                )

            invoke = _parse_invoke(
                line
            )

            if invoke is None:
                raise ParseError(
                    "Static parallel regions "
                    "currently contain invokes only; "
                    f"got: {line}"
                )

            invokes.append(
                invoke
            )

            i += 1

        raise ParseError(
            "Program ended before static "
            "parallel region was closed."
        )

    steps = []

    while i < len(lines):
        line = lines[i]

        if line == "}":
            if not steps:
                raise ParseError(
                    "Static sequential region "
                    "contains no steps."
                )

            return (
                StaticSeq(
                    steps=tuple(steps),
                    timing_var=timing_var,
                ),
                i + 1,
            )

        invoke = _parse_invoke(
            line
        )

        if invoke is not None:
            steps.append(
                invoke
            )

            i += 1
            continue

        if re.fullmatch(
            rf"static\s+(par|seq)"
            rf"(?:\s*->\s*({IDENT}))?"
            rf"\s*\{{",
            line,
        ):
            child, i = _parse_control(
                lines,
                i,
            )

            steps.append(
                child
            )

            continue

        raise ParseError(
            "Unexpected static-seq statement: "
            f"{line}"
        )

    raise ParseError(
        "Program ended before static "
        "sequential region was closed."
    )


def parse_lair(text: str) -> SymbolicProgram:
    """
    Parse textual latency-abstract accelerator IR.

    Legacy V1.0-V1.2 programs contain exactly one top-level component:

        component pipeline(x) {
            static seq -> T_total {
                ...
            }
        }

    V1.3 adds reusable component declarations with exported timing
    interfaces plus an explicit entry component:

        component pair(x) latency -> T_pair {
            static par {
                ...
            }
        }

        component pipeline(x) latency -> T_total {
            static seq {
                invoke pair(x)
            }
        }

        entry pipeline

    Legacy and V1.3 component forms may not be mixed.
    """

    lines = _clean_lines(
        text
    )

    generators = []
    bindings = []
    constraints = []

    legacy_body = None
    components = []
    entry = None

    component_section_started = False
    legacy_component_seen = False

    i = 0

    while i < len(lines):
        line = lines[i]

        generator_match = re.fullmatch(
            rf"generator\s+({IDENT})\s*=\s*"
            rf"({IDENT})\s*\(\s*({IDENT})\s*\)\s*"
            rf"latency\s*->\s*({IDENT})",
            line,
        )

        if generator_match:
            if component_section_started:
                raise ParseError(
                    "Generator declaration appears after component."
                )

            (
                instance,
                generator,
                kernel,
                latency_var,
            ) = generator_match.groups()

            generators.append(
                GeneratorDecl(
                    instance=instance,
                    generator=generator,
                    kernel=kernel,
                    latency_var=TimingVar(
                        latency_var
                    ),
                )
            )

            i += 1
            continue

        binding_match = re.fullmatch(
            rf"let\s+({IDENT})\s*=\s*(.+)",
            line,
        )

        if binding_match:
            if component_section_started:
                raise ParseError(
                    "Timing binding appears after component."
                )

            target, expr_text = (
                binding_match.groups()
            )

            bindings.append(
                TimingBinding(
                    target=TimingVar(
                        target
                    ),
                    expr=parse_timing_expr(
                        expr_text
                    ),
                )
            )

            i += 1
            continue

        constraint_match = re.fullmatch(
            rf"require\s+({IDENT})\s*:\s*(.+)",
            line,
        )

        if constraint_match:
            if component_section_started:
                raise ParseError(
                    "Constraint appears after component."
                )

            name, constraint_text = (
                constraint_match.groups()
            )

            left, op, right = (
                _split_constraint(
                    constraint_text
                )
            )

            constraints.append(
                TimingConstraint(
                    name=name,
                    left=parse_timing_expr(
                        left
                    ),
                    op=op,
                    right=parse_timing_expr(
                        right
                    ),
                )
            )

            i += 1
            continue

        # ---------------------------------------------------------------
        # V1.3 reusable component declaration.
        # ---------------------------------------------------------------
        component_match = re.fullmatch(
            rf"component\s+({IDENT})"
            rf"\s*\(\s*({IDENT})\s*\)"
            rf"\s+latency\s*->\s*({IDENT})"
            rf"\s*\{{",
            line,
        )

        if component_match:
            if legacy_component_seen:
                raise ParseError(
                    "Legacy and V1.3 component forms cannot be mixed."
                )

            if entry is not None:
                raise ParseError(
                    "Component declaration appears after entry."
                )

            component_section_started = True

            (
                component_name,
                argument,
                latency_name,
            ) = component_match.groups()

            body, i = _parse_control(
                lines,
                i + 1,
            )

            if (
                i >= len(lines)
                or lines[i] != "}"
            ):
                raise ParseError(
                    "Expected component closing brace."
                )

            components.append(
                ComponentDecl(
                    name=component_name,
                    args=(
                        argument,
                    ),
                    latency_var=TimingVar(
                        latency_name
                    ),
                    body=body,
                )
            )

            i += 1
            continue

        # ---------------------------------------------------------------
        # Historical V1.0-V1.2 single-component form.
        # ---------------------------------------------------------------
        legacy_match = re.fullmatch(
            rf"component\s+({IDENT})"
            rf"\s*\(\s*({IDENT})\s*\)\s*\{{",
            line,
        )

        if legacy_match:
            if components:
                raise ParseError(
                    "Legacy and V1.3 component forms cannot be mixed."
                )

            if legacy_component_seen:
                raise ParseError(
                    "Only one legacy top-level component "
                    "is supported."
                )

            if entry is not None:
                raise ParseError(
                    "Legacy component appears after entry."
                )

            component_section_started = True
            legacy_component_seen = True

            legacy_body, i = _parse_control(
                lines,
                i + 1,
            )

            if (
                i >= len(lines)
                or lines[i] != "}"
            ):
                raise ParseError(
                    "Expected component closing brace."
                )

            i += 1

            if i != len(lines):
                raise ParseError(
                    "Unexpected content after legacy component: "
                    f"{lines[i]}"
                )

            continue

        # ---------------------------------------------------------------
        # V1.3 entry declaration.
        # ---------------------------------------------------------------
        entry_match = re.fullmatch(
            rf"entry\s+({IDENT})",
            line,
        )

        if entry_match:
            if legacy_component_seen:
                raise ParseError(
                    "Legacy component programs cannot define entry."
                )

            if not components:
                raise ParseError(
                    "Entry declaration appears before any "
                    "V1.3 component."
                )

            if entry is not None:
                raise ParseError(
                    "Program defines more than one entry."
                )

            entry = entry_match.group(1)
            component_section_started = True

            i += 1

            if i != len(lines):
                raise ParseError(
                    "Unexpected content after entry: "
                    f"{lines[i]}"
                )

            continue

        raise ParseError(
            f"Unexpected top-level statement: {line}"
        )

    # -------------------------------------------------------------------
    # Construct exactly one of the two symbolic-program representations.
    # -------------------------------------------------------------------
    if legacy_component_seen:
        if legacy_body is None:
            raise ParseError(
                "Program contains no static control body."
            )

        return SymbolicProgram(
            generators=tuple(
                generators
            ),
            bindings=tuple(
                bindings
            ),
            constraints=tuple(
                constraints
            ),
            body=legacy_body,
        )

    if components:
        if entry is None:
            raise ParseError(
                "V1.3 component program contains no entry."
            )

        try:
            return SymbolicProgram(
                generators=tuple(
                    generators
                ),
                bindings=tuple(
                    bindings
                ),
                constraints=tuple(
                    constraints
                ),
                components=tuple(
                    components
                ),
                entry=entry,
            )
        except ValueError as exc:
            raise ParseError(
                str(exc)
            ) from exc

    raise ParseError(
        "Program contains no component."
    )

def parse_lair_file(path: Path) -> SymbolicProgram:
    return parse_lair(
        path.read_text()
    )
