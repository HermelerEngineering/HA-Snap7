"""Unit tests for the value parser (no Home Assistant required)."""

import struct

import pytest

from custom_components.s7_plc.parser import ParseError, parse_value


def test_bool_bits():
    buf = bytes([0b0000_0101])
    assert parse_value(buf, "bool", 0, 0) is True
    assert parse_value(buf, "bool", 0, 1) is False
    assert parse_value(buf, "bool", 0, 2) is True
    assert parse_value(buf, "bool", 0, 7) is False


def test_byte():
    buf = bytes([0x00, 0xFF, 0x7F])
    assert parse_value(buf, "byte", 1) == 255
    assert parse_value(buf, "byte", 2) == 127


def test_int_signed():
    buf = struct.pack(">h", -1234)
    assert parse_value(buf, "int", 0) == -1234


def test_uint():
    buf = struct.pack(">H", 50000)
    assert parse_value(buf, "uint", 0) == 50000


def test_dint():
    buf = struct.pack(">i", -2_000_000_000)
    assert parse_value(buf, "dint", 0) == -2_000_000_000


def test_real():
    buf = struct.pack(">f", 12.5)
    assert parse_value(buf, "real", 0) == pytest.approx(12.5)


def test_real_at_offset():
    # bool byte 0, real at byte 2 (DB1.DBD2 in the MVP test DB)
    buf = bytes([0x00, 0x00]) + struct.pack(">f", 3.14)
    assert parse_value(buf, "real", 2) == pytest.approx(3.14, rel=1e-6)


def test_big_endian_real_known_bytes():
    # 1.0 in IEEE-754 big-endian is 3F 80 00 00
    buf = bytes([0x3F, 0x80, 0x00, 0x00])
    assert parse_value(buf, "real", 0) == pytest.approx(1.0)


def test_out_of_bounds_raises():
    with pytest.raises(ParseError):
        parse_value(bytes([0x00, 0x00]), "dint", 0)


def test_bad_bit_raises():
    with pytest.raises(ParseError):
        parse_value(bytes([0x00]), "bool", 0, 8)


def test_unknown_type_raises():
    with pytest.raises(ParseError):
        parse_value(bytes([0x00]), "word", 0)
