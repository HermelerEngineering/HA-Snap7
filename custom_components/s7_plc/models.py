"""Typed data models for the S7 PLC integration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlcConfig:
    """Connection configuration for a single PLC."""

    name: str
    host: str
    plc_type: str
    rack: int
    slot: int
    scan_interval: int
    port: int = 102


@dataclass(frozen=True)
class EntityDefinition:
    """A single entity definition parsed from YAML.

    The ``byte`` offset is relative to the start of the data block ``db``.
    ``bit`` is only meaningful for ``bool`` data types.
    """

    key: str
    name: str
    platform: str
    db: int
    byte: int
    data_type: str
    bit: int = 0
    # Memory area: "db", "input", "output" or "memory". ``db`` is only
    # meaningful when ``area`` is "db".
    area: str = "db"
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    icon: str | None = None
    scale: float | None = None
    offset: float | None = None
    # Write-related (number platform).
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    mode: str | None = None
    # Write-related (button platform): value written on press.
    press_value: bool | int | float | None = None

    @property
    def is_bool(self) -> bool:
        """Return True if this entity targets a single bit."""
        return self.data_type == "bool"


@dataclass(frozen=True)
class ReadRequest:
    """A contiguous byte range to read from a single data block.

    The coordinator issues one PLC ``db_read`` per ReadRequest so that
    multiple entities sharing a DB are served by a single PLC call.
    """

    db: int
    start: int
    size: int
    area: str = "db"

    @property
    def end(self) -> int:
        """Return the exclusive end byte offset of this range."""
        return self.start + self.size


@dataclass
class PlcDefinition:
    """The full, validated definition loaded from a YAML file.

    ``plc`` is optional because connection parameters normally come from the
    config entry; the YAML may carry a ``plc`` block for documentation or
    standalone validation.
    """

    plc: PlcConfig | None = None
    entities: list[EntityDefinition] = field(default_factory=list)
