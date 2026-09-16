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


def topological_component_order(
    program: SymbolicProgram,
) -> tuple[str, ...]:
    """
    Return user components in dependency-first order.

    For an edge:

        parent -> child

    the child appears before the parent.

    Recursive/self-recursive component dependencies are rejected.

    Generator invocations are absent from the graph and therefore do
    not participate in cycle detection.
    """

    graph = component_dependencies(
        program
    )

    if not graph:
        return ()

    # 0 = unseen
    # 1 = active DFS stack
    # 2 = fully resolved
    state: dict[str, int] = {
        name: 0
        for name in graph
    }

    order: list[str] = []
    stack: list[str] = []

    def visit(
        component: str,
    ) -> None:
        current = state[component]

        if current == 2:
            return

        if current == 1:
            # Recover a useful cycle path.
            try:
                start = stack.index(
                    component
                )
            except ValueError:
                start = 0

            cycle = (
                stack[start:]
                + [component]
            )

            raise ValueError(
                "Recursive component dependency "
                "is not supported in V1.3: "
                + " -> ".join(cycle)
            )

        state[component] = 1
        stack.append(component)

        for dependency in graph[component]:
            visit(
                dependency
            )

        stack.pop()
        state[component] = 2

        order.append(
            component
        )

    # Preserve declaration order whenever multiple valid
    # topological orders exist.
    for component in program.components:
        visit(
            component.name
        )

    return tuple(order)
