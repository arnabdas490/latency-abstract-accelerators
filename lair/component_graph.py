from __future__ import annotations

from lair.ast import (
    SymbolicProgram,
    _iter_control_invokes,
)


def component_dependencies(
    program: SymbolicProgram,
) -> dict[str, tuple[str, ...]]:
    """
    Build the user-component dependency graph for a V1.3 program.

    Generator invocations are leaves and therefore do not appear as
    component dependency edges.

    Dependency order follows first appearance in the component body.
    Repeated invocations of the same child create only one graph edge.

    Cycle detection is intentionally not performed here; that is a
    separate V1.3 stage.
    """

    if not program.components:
        return {}

    component_names = {
        component.name
        for component in program.components
    }

    graph: dict[
        str,
        tuple[str, ...],
    ] = {}

    for component in program.components:
        dependencies: list[str] = []
        seen: set[str] = set()

        for invoke in _iter_control_invokes(
            component.body
        ):
            target = invoke.component

            if (
                target in component_names
                and target not in seen
            ):
                dependencies.append(
                    target
                )
                seen.add(
                    target
                )

        graph[component.name] = tuple(
            dependencies
        )

    return graph
