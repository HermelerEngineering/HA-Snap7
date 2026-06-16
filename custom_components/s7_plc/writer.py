"""Serialize Python values into S7 byte buffers.

This is the inverse of :mod:`parser`. Siemens S7 uses big-endian byte order;
``real`` is a 32-bit IEEE-754 float. ``bool`` is handled separately because a
single bit cannot be written without a read-modify-write of its byte (see
:meth:`plc_client.S7PlcClient.write_bool`).
"""

from __future__ import annotations

import struct

from .const import (
    DATA_TYPE_BYTE,
    DATA_TYPE_DINT,
    DATA_TYPE_INT,
    DATA_TYPE_REAL,
    DATA_TYPE_UINT,
    INT_RANGES,
)


class WriteError(Exception):
    """Raised when a value cannot be serialized for the PLC."""


def set_bit(byte_value: int, bit_index: int, value: bool) -> int:
    """Return ``byte_value`` with ``bit_index`` set or cleared per ``value``."""
    if not 0 <= bit_index <= 7:
        raise WriteError(f"bit index {bit_index} out of range (0-7)")
    if not 0 <= byte_value <= 255:
        raise WriteError(f"byte value {byte_value} out of range (0-255)")
    mask = 1 << bit_index
    if value:
        return byte_value | mask
    return byte_value & ~mask


def serialize(data_type: str, value: object) -> bytearray:
    """Serialize ``value`` of ``data_type`` into a big-endian byte buffer.

    Integer types coerce floats by rounding; ``real`` accepts any number.
    Raises :class:`WriteError` on an unsupported type or out-of-range value.
    """
    if data_type == DATA_TYPE_REAL:
        return bytearray(struct.pack(">f", float(value)))

    if data_type in INT_RANGES:
        int_value = _coerce_int(value)
        low, high = INT_RANGES[data_type]
        if not low <= int_value <= high:
            raise WriteError(
                f"value {int_value} out of range for {data_type} ({low}..{high})"
            )
        fmt = {
            DATA_TYPE_BYTE: ">B",
            DATA_TYPE_INT: ">h",
            DATA_TYPE_UINT: ">H",
            DATA_TYPE_DINT: ">i",
        }[data_type]
        return bytearray(struct.pack(fmt, int_value))

    raise WriteError(f"unsupported writable data type: {data_type}")


def _coerce_int(value: object) -> int:
    """Coerce a number to an int, rounding floats to the nearest integer."""
    if isinstance(value, bool):
        raise WriteError("expected a number, got a bool")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    raise WriteError(f"expected a number, got {type(value).__name__}")
