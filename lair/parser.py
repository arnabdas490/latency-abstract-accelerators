from __future__ import annotations

import re
from pathlib import Path

from lair.ast import (
    GeneratorDecl,
    Invoke,
    StaticPar,
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


def parse_lair(text: str) -> SymbolicProgram:
    """
    Parse the minimal V1.0 textual latency-abstract language.

    Grammar intentionally stays small:

        generator A = toy_generator(kernel_a) latency -> L_A
        let T = max(L_A, L_B)
        require name: T <= 6

        component pair(x) {
            static par {
                invoke A(x)
                invoke B(x)
            }
        }
    """

    lines = _clean_lines(text)

    generators = []
    bindings = []
    constraints = []
    invokes = []

    state = "top"
    component_seen = False

    for line in lines:
        if state == "top":
            generator_match = re.fullmatch(
                rf"generator\s+({IDENT})\s*=\s*"
                rf"({IDENT})\s*\(\s*({IDENT})\s*\)\s*"
                rf"latency\s*->\s*({IDENT})",
                line,
            )

            if generator_match:
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

                continue

            binding_match = re.fullmatch(
                rf"let\s+({IDENT})\s*=\s*(.+)",
                line,
            )

            if binding_match:
                target, expr_text = (
                    binding_match.groups()
                )

                bindings.append(
                    TimingBinding(
                        target=TimingVar(target),
                        expr=parse_timing_expr(
                            expr_text
                        ),
                    )
                )

                continue

            constraint_match = re.fullmatch(
                rf"require\s+({IDENT})\s*:\s*(.+)",
                line,
            )

            if constraint_match:
                name, constraint_text = (
                    constraint_match.groups()
                )

                left, op, right = _split_constraint(
                    constraint_text
                )

                constraints.append(
                    TimingConstraint(
                        name=name,
                        left=parse_timing_expr(left),
                        op=op,
                        right=parse_timing_expr(right),
                    )
                )

                continue

            component_match = re.fullmatch(
                rf"component\s+({IDENT})"
                rf"\s*\(\s*({IDENT})\s*\)\s*\{{",
                line,
            )

            if component_match:
                if component_seen:
                    raise ParseError(
                        "V1.0 supports one component only."
                    )

                component_seen = True
                state = "component"
                continue

            raise ParseError(
                f"Unexpected top-level statement: {line}"
            )

        if state == "component":
            if re.fullmatch(
                r"static\s+par\s*\{",
                line,
            ):
                state = "static_par"
                continue

            raise ParseError(
                "Expected 'static par {' inside component; "
                f"got: {line}"
            )

        if state == "static_par":
            invoke_match = re.fullmatch(
                rf"invoke\s+({IDENT})"
                rf"\s*\(\s*([^)]*)\s*\)",
                line,
            )

            if invoke_match:
                component, args_text = (
                    invoke_match.groups()
                )

                args = tuple(
                    arg.strip()
                    for arg in args_text.split(",")
                    if arg.strip()
                )

                invokes.append(
                    Invoke(
                        component=component,
                        args=args,
                    )
                )

                continue

            if line == "}":
                state = "after_static_par"
                continue

            raise ParseError(
                f"Unexpected static-par statement: {line}"
            )

        if state == "after_static_par":
            if line == "}":
                state = "done"
                continue

            raise ParseError(
                "Expected component closing brace; "
                f"got: {line}"
            )

        if state == "done":
            raise ParseError(
                f"Unexpected content after component: {line}"
            )

    if not component_seen:
        raise ParseError(
            "Program contains no component."
        )

    if state != "done":
        raise ParseError(
            "Program ended before component was fully closed."
        )

    if not invokes:
        raise ParseError(
            "Static parallel body contains no invokes."
        )

    return SymbolicProgram(
        generators=tuple(generators),
        bindings=tuple(bindings),
        constraints=tuple(constraints),
        body=StaticPar(
            invokes=tuple(invokes),
        ),
    )


def parse_lair_file(path: Path) -> SymbolicProgram:
    return parse_lair(
        path.read_text()
    )
