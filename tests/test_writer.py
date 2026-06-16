"""Unit tests for the value writer (inverse of the parser)."""

import pytest

from custom_components.s7_plc.parser import parse_value
from custom_components.s7_plc.writer import WriteError, serialize, set_bit


@pytest.mark.parametrize(
    ("data_type", "value"),
    [
        ("byte", 0),
        ("byte", 255),
        ("int", -1234),
        ("int", 32767),
        ("uint", 50000),
        ("dint", -2_000_000_000),
        ("real", 12.5),
    ],
)
def test_roundtrip(data_type, value):
    buf = serialize(data_type, value)
    parsed = parse_value(bytes(buf), data_type, 0)
    if data_type == "real":
        assert parsed == pytest.approx(value)
    else:
        assert parsed == value


def test_real_roundtrip_known_bytes():
    assert bytes(serialize("real", 1.0)) == bytes([0x3F, 0x80, 0x00, 0x00])


def test_float_coerced_to_int_rounds():
    assert bytes(serialize("int", 10.6)) == bytes([0x00, 0x0B])


def test_out_of_range_byte_raises():
    with pytest.raises(WriteError):
        serialize("byte", 256)


def test_out_of_range_int_raises():
    with pytest.raises(WriteError):
        serialize("int", 40000)


def test_bool_not_serializable_as_number():
    with pytest.raises(WriteError):
        serialize("int", True)


def test_unsupported_type_raises():
    with pytest.raises(WriteError):
        serialize("bool", 1)


def test_set_bit():
    assert set_bit(0b0000_0000, 0, True) == 0b0000_0001
    assert set_bit(0b0000_0001, 0, False) == 0b0000_0000
    assert set_bit(0b0000_0000, 3, True) == 0b0000_1000
    # Setting an already-set bit is idempotent and leaves others intact.
    assert set_bit(0b1010_1010, 1, True) == 0b1010_1010
    assert set_bit(0b1010_1010, 1, False) == 0b1010_1000


def test_set_bit_out_of_range():
    with pytest.raises(WriteError):
        set_bit(0, 8, True)
