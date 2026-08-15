import hashlib
import json
import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from ai import weights


class WeightConfig:
    """Snapshot inmutable y validado de los pesos de una estrategia."""

    def __init__(self, values: Mapping[str, int | float]) -> None:
        defaults = self._current_values()
        if set(values) != set(defaults):
            missing = sorted(set(defaults) - set(values))
            extra = sorted(set(values) - set(defaults))
            raise ValueError(f"Configuración incompleta: missing={missing}, extra={extra}")
        validated = {
            name: self._validate_value(name, value, defaults[name])
            for name, value in values.items()
        }
        self._values = MappingProxyType(dict(sorted(validated.items())))

    @classmethod
    def from_current_defaults(cls) -> "WeightConfig":
        return cls(cls._current_values())

    def with_changes(self, **changes: int | float) -> "WeightConfig":
        unknown = sorted(set(changes) - set(self._values))
        if unknown:
            raise ValueError(f"Pesos desconocidos: {', '.join(unknown)}")
        values = dict(self._values)
        values.update(changes)
        return WeightConfig(values)

    def as_dict(self) -> dict[str, int | float]:
        return dict(self._values)

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(dict(self._values), sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def differences_from(self, other: "WeightConfig") -> dict[str, dict[str, float]]:
        return {
            name: {"baseline": other._values[name], "candidate": value}
            for name, value in self._values.items()
            if value != other._values[name]
        }

    def __getattr__(self, name: str) -> Any:
        try:
            return self._values[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __eq__(self, other: object) -> bool:
        return isinstance(other, WeightConfig) and self._values == other._values

    @staticmethod
    def _current_values() -> dict[str, int | float]:
        return {
            name: value
            for name, value in vars(weights).items()
            if name.isupper() and isinstance(value, (int, float)) and not isinstance(value, bool)
        }

    @staticmethod
    def _validate_value(name: str, value: Any, default: int | float) -> int | float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} debe ser numérico.")
        if not math.isfinite(value) or abs(value) > 100_000_000:
            raise ValueError(f"{name} está fuera de un rango razonable.")
        if default > 0 and value < 0:
            raise ValueError(f"{name} no puede cambiar a signo negativo.")
        if default < 0 and value > 0:
            raise ValueError(f"{name} no puede cambiar a signo positivo.")
        return value
