"""Thin wrapper around python-snap7.

All Snap7 calls are funneled through a single client instance per config
entry. The python-snap7 client is not thread-safe and must never be shared
or called concurrently from multiple places, so the coordinator serializes
access by running reads in the executor one at a time.
"""

from __future__ import annotations

import logging

import snap7

# The base snap7 exception moved between major versions:
#   * python-snap7 3.x: snap7.error.S7Error
#   * python-snap7 1.x / 2.x: snap7.exceptions.Snap7Exception
try:  # python-snap7 >= 3.0
    from snap7.error import S7Error as Snap7Exception
except ImportError:  # pragma: no cover - older layouts
    try:
        from snap7.exceptions import Snap7Exception  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover
        Snap7Exception = Exception  # type: ignore[assignment,misc]

from .const import AREA_DB, AREA_INPUT, AREA_MEMORY, AREA_OUTPUT
from .models import PlcConfig

# Map our area keys to snap7's Area enum (process inputs / outputs / merkers).
try:  # python-snap7 >= 3.0
    from snap7.type import Area as _Snap7Area

    _AREA_MAP = {
        AREA_INPUT: _Snap7Area.PE,
        AREA_OUTPUT: _Snap7Area.PA,
        AREA_MEMORY: _Snap7Area.MK,
        AREA_DB: _Snap7Area.DB,
    }
except ImportError:  # pragma: no cover - older snap7 layouts
    try:
        from snap7.types import Areas as _Snap7Area  # type: ignore[no-redef]

        _AREA_MAP = {
            AREA_INPUT: _Snap7Area.PE,
            AREA_OUTPUT: _Snap7Area.PA,
            AREA_MEMORY: _Snap7Area.MK,
            AREA_DB: _Snap7Area.DB,
        }
    except ImportError:  # pragma: no cover
        _AREA_MAP = {}

_LOGGER = logging.getLogger(__name__)


class PlcConnectionError(Exception):
    """Raised when connecting to or reading from the PLC fails."""


class S7PlcClient:
    """Synchronous wrapper around a single python-snap7 client."""

    def __init__(self, config: PlcConfig) -> None:
        """Initialize the client (does not connect yet)."""
        self._config = config
        self._client = snap7.client.Client()

    @property
    def is_connected(self) -> bool:
        """Return True if the underlying client reports a live connection."""
        try:
            return bool(self._client.get_connected())
        except Snap7Exception:
            return False

    def connect(self) -> None:
        """Open the connection to the PLC.

        Raises PlcConnectionError on failure.
        """
        cfg = self._config
        _LOGGER.debug(
            "Connecting to PLC %s at %s:%s (rack=%s, slot=%s)",
            cfg.name,
            cfg.host,
            cfg.port,
            cfg.rack,
            cfg.slot,
        )
        try:
            self._client.connect(cfg.host, cfg.rack, cfg.slot, cfg.port)
        except Snap7Exception as err:
            raise PlcConnectionError(
                f"Failed to connect to PLC {cfg.host}: {err}"
            ) from err
        if not self.is_connected:
            raise PlcConnectionError(f"PLC {cfg.host} did not establish a connection")

    def disconnect(self) -> None:
        """Close the connection to the PLC, ignoring errors."""
        try:
            self._client.disconnect()
        except Snap7Exception as err:  # pragma: no cover - best effort cleanup
            _LOGGER.debug("Error while disconnecting from PLC: %s", err)

    def db_read(self, db_number: int, start: int, size: int) -> bytearray:
        """Read ``size`` bytes from data block ``db_number`` starting at ``start``.

        Raises PlcConnectionError on failure.
        """
        try:
            return self._client.db_read(db_number, start, size)
        except Snap7Exception as err:
            raise PlcConnectionError(
                f"Failed to read DB{db_number} [{start}:{start + size}]: {err}"
            ) from err

    def db_write(self, db_number: int, start: int, data: bytes | bytearray) -> None:
        """Write ``data`` to data block ``db_number`` starting at ``start``.

        Raises PlcConnectionError on failure.
        """
        try:
            self._client.db_write(db_number, start, bytearray(data))
        except Snap7Exception as err:
            raise PlcConnectionError(
                f"Failed to write DB{db_number} [{start}:{start + len(data)}]: {err}"
            ) from err

    def read(self, area: str, db_number: int, start: int, size: int) -> bytearray:
        """Read ``size`` bytes from ``area`` (db / input / output / memory).

        For non-DB areas the DB number is ignored. Raises PlcConnectionError
        on failure.
        """
        if area == AREA_DB:
            return self.db_read(db_number, start, size)
        try:
            return self._client.read_area(_AREA_MAP[area], 0, start, size)
        except Snap7Exception as err:
            raise PlcConnectionError(
                f"Failed to read {area} [{start}:{start + size}]: {err}"
            ) from err

    def write(self, area: str, db_number: int, start: int, data: bytes | bytearray) -> None:
        """Write ``data`` to ``area`` (db / input / output / memory).

        For non-DB areas the DB number is ignored. Raises PlcConnectionError
        on failure.
        """
        if area == AREA_DB:
            self.db_write(db_number, start, data)
            return
        try:
            self._client.write_area(_AREA_MAP[area], 0, start, bytearray(data))
        except Snap7Exception as err:
            raise PlcConnectionError(
                f"Failed to write {area} [{start}:{start + len(data)}]: {err}"
            ) from err

    def write_bit(
        self, area: str, db_number: int, byte: int, bit: int, value: bool
    ) -> None:
        """Set or clear a single bit via a read-modify-write of its byte.

        S7 writes happen at byte granularity, so the target byte is read, the
        requested bit is changed and the byte is written back. Works for any
        area. Raises PlcConnectionError on failure.
        """
        from .writer import set_bit

        current = self.read(area, db_number, byte, 1)
        current[0] = set_bit(current[0], bit, value)
        self.write(area, db_number, byte, current)

    def write_bool(self, db_number: int, byte: int, bit: int, value: bool) -> None:
        """DB-area convenience wrapper around :meth:`write_bit`."""
        self.write_bit(AREA_DB, db_number, byte, bit, value)
