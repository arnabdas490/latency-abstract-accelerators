from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class TimingEnvironment:
    """
    Concrete timing facts obtained from generator elaboration.

    Example:
        {
            "L_A": 5,
            "L_B": 2,
        }

    Derived timing variables such as T do not belong here; they are
    computed by the resolver from symbolic bindings.
    """

    values: Mapping[str, int]

    def __post_init__(self) -> None:
        copied = dict(self.values)

        for name, value in copied.items():
            if not name:
                raise ValueError(
                    "Timing-environment variable names must be non-empty."
                )

            if not isinstance(value, int):
                raise TypeError(
                    f"Timing value for {name} must be an integer."
                )

            if value < 0:
                raise ValueError(
                    f"Timing value for {name} cannot be negative."
                )

        object.__setattr__(
            self,
            "values",
            MappingProxyType(copied),
        )

    def require(self, name: str) -> int:
        try:
            return self.values[name]
        except KeyError as exc:
            raise KeyError(
                f"Unbound timing variable: {name}"
            ) from exc

    def to_dict(self) -> dict[str, int]:
        return dict(self.values)
