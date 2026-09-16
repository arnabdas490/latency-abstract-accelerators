from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComponentTimingInterface:
    """
    Public timing summary exported by a resolved user component.

    Deliberately contains no implementation structure. A parent timing
    resolver may consume this interface without receiving the child's
    control body or generator dependencies.
    """

    component: str
    latency: int

    def __post_init__(self) -> None:
        if not self.component:
            raise ValueError(
                "Component timing interface name "
                "must be non-empty."
            )

        if self.latency < 0:
            raise ValueError(
                "Component timing interface latency "
                "must be non-negative."
            )

    def to_dict(self) -> dict:
        return {
            "component": self.component,
            "latency": self.latency,
        }
