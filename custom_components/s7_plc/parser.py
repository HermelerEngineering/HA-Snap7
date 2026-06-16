"""Parse PLC values from raw byte buffers.

Siemens S7 uses big-endian byte order. ``real`` is a 32-bit IEEE-754 float.
All functions take a buffer whose index 0 corresponds to the start byte that
the buffer was read from. The caller is responsible for translating absolute
DB offsets into buffer-relative offsets.
"""

from __future__ import annotations

import struct

from .const import (
    DATA_TYPE_BOOL,
    DATA_TYPE_BYTE,
    DATA_TYPE_DINT,
    DATA_TYPE_INT,
    DATA_TYPE_REAL,
    DATA_TYPE_UINT,
)


class ParseError(Exception):
    """Raised when a value cannot be parsed from a buffer."""


def get_bool(buffer: bytes, byte_index: int, bit_index: int) -> bool:
    """Return a single bit as a boolean."""
    if not 0 <= bit_index <= 7:
        raise ParseError(f"bit index {bit_index} out of range (0-7)")
    _check_bounds(buffer, byte_index, 1)
    return bool((buffer[byte_index] >> bit_index) & 0x01)


def get_byte(buffer: bytes, byte_index: int) -> int:
    """Return an unsigned 8-bit value."""
    _check_bounds(buffer, byte_index, 1)
    return buffer[byte_index]


def get_int(buffer: bytes, byte_index: int) -> int:
    """Return a signed 16-bit big-endian integer."""
    _check_bounds(buffer, byte_index, 2)
    return struct.unpack_from(">h", buffer, byte_index)[0]


def get_uint(buffer: bytes, byte_index: int) -> int:
    """Return an unsigned 16-bit big-endian integer."""
    _check_bounds(buffer, byte_index, 2)
    return struct.unpack_from(">H", buffer, byte_index)[0]


def get_dint(buffer: bytes, byte_index: int) -> int:
    """Return a signed 32-bit big-endian integer."""
    _check_bounds(buffer, byte_index, 4)
    return struct.unpack_from(">i", buffer, byte_index)[0]


def get_real(buffer: bytes, byte_index: int) -> float:
    """Return a 32-bit big-endian IEEE-754 float."""
    _check_bounds(buffer, byte_index, 4)
    return struct.unpack_from(">f", buffer, byte_index)[0]


def parse_value(
    buffer: bytes,
    data_type: str,
    byte_index: int,
    bit_index: int = 0,
) -> bool | int | float:
    """Parse a value of ``data_type`` from ``buffer`` at ``byte_index``."""
    if data_type == DATA_TYPE_BOOL:
        return get_bool(buffer, byte_index, bit_index)
    if data_type == DATA_TYPE_BYTE:
        return get_byte(buffer, byte_index)
    if data_type == DATA_TYPE_INT:
        return get_int(buffer, byte_index)
    if data_type == DATA_TYPE_UINT:
        return get_uint(buffer, byte_index)
    if data_type == DATA_TYPE_DINT:
        return get_dint(buffer, byte_index)
    if data_type == DATA_TYPE_REAL:
        return get_real(buffer, byte_index)
    raise ParseError(f"unsupported data type: {data_type}")


def _check_bounds(buffer: bytes, byte_index: int, size: int) -> None:
    """Validate that ``size`` bytes are available at ``byte_index``."""
    if byte_index < 0:
        raise ParseError(f"negative byte index {byte_index}")
    if byte_index + size > len(buffer):
        raise ParseError(
            f"read of {size} byte(s) at offset {byte_index} exceeds "
            f"buffer length {len(buffer)}"
        )
