"""Unit tests for YAML parsing and validation."""

import pytest

from custom_components.s7_plc.yaml_loader import YamlConfigError, parse_definition


def _valid_raw():
    return {
        "plc": {
            "name": "Main PLC",
            "host": "192.168.1.10",
            "plc_type": "s7_1500",
            "scan_interval": 2,
        },
        "entities": [
            {
                "key": "machine_running",
                "name": "Machine Running",
                "platform": "binary_sensor",
                "db": 1,
                "byte": 0,
                "bit": 0,
                "data_type": "bool",
                "device_class": "running",
            },
            {
                "key": "actual_speed",
                "name": "Actual Speed",
                "platform": "sensor",
                "db": 1,
                "byte": 2,
                "data_type": "real",
                "unit": "m/min",
                "state_class": "measurement",
            },
        ],
    }


def test_valid_definition():
    definition = parse_definition(_valid_raw())
    assert definition.plc is not None
    assert definition.plc.host == "192.168.1.10"
    # Rack/slot derived from plc_type s7_1500 -> (0, 1)
    assert definition.plc.rack == 0
    assert definition.plc.slot == 1
    assert len(definition.entities) == 2
    assert definition.entities[0].key == "machine_running"


def test_plc_block_is_optional():
    raw = _valid_raw()
    del raw["plc"]
    definition = parse_definition(raw)
    assert definition.plc is None
    assert len(definition.entities) == 2


def test_s7_300_rack_slot():
    raw = _valid_raw()
    raw["plc"]["plc_type"] = "s7_300"
    definition = parse_definition(raw)
    assert (definition.plc.rack, definition.plc.slot) == (0, 2)


def test_invalid_plc_type():
    raw = _valid_raw()
    raw["plc"]["plc_type"] = "s7_400"
    with pytest.raises(YamlConfigError):
        parse_definition(raw)


def test_invalid_platform():
    raw = _valid_raw()
    raw["entities"][0]["platform"] = "light"
    with pytest.raises(YamlConfigError):
        parse_definition(raw)


def test_invalid_data_type():
    raw = _valid_raw()
    raw["entities"][0]["data_type"] = "word"
    with pytest.raises(YamlConfigError):
        parse_definition(raw)


def test_duplicate_keys_rejected():
    raw = _valid_raw()
    raw["entities"][1]["key"] = "machine_running"
    with pytest.raises(YamlConfigError):
        parse_definition(raw)


def test_missing_entities_rejected():
    raw = _valid_raw()
    raw["entities"] = []
    with pytest.raises(YamlConfigError):
        parse_definition(raw)


def test_bad_bit_rejected():
    raw = _valid_raw()
    raw["entities"][0]["bit"] = 9
    with pytest.raises(YamlConfigError):
        parse_definition(raw)


def test_negative_byte_rejected():
    raw = _valid_raw()
    raw["entities"][0]["byte"] = -1
    with pytest.raises(YamlConfigError):
        parse_definition(raw)


def test_switch_requires_bool():
    raw = _valid_raw()
    raw["entities"].append(
        {
            "key": "enable",
            "name": "Enable",
            "platform": "switch",
            "db": 10,
            "byte": 12,
            "data_type": "int",  # invalid for a switch
        }
    )
    with pytest.raises(YamlConfigError):
        parse_definition(raw)


def test_valid_switch_and_number():
    raw = _valid_raw()
    raw["entities"].extend(
        [
            {
                "key": "enable",
                "name": "Enable",
                "platform": "switch",
                "db": 10,
                "byte": 12,
                "bit": 0,
                "data_type": "bool",
            },
            {
                "key": "setpoint",
                "name": "Setpoint",
                "platform": "number",
                "db": 10,
                "byte": 14,
                "data_type": "real",
                "min": 0,
                "max": 100,
                "step": 0.5,
                "mode": "box",
                "unit": "m/min",
            },
        ]
    )
    definition = parse_definition(raw)
    number = next(e for e in definition.entities if e.key == "setpoint")
    assert number.min_value == 0
    assert number.max_value == 100
    assert number.step == 0.5
    assert number.mode == "box"


def test_number_rejects_bool():
    raw = _valid_raw()
    raw["entities"].append(
        {
            "key": "bad",
            "name": "Bad",
            "platform": "number",
            "db": 10,
            "byte": 20,
            "data_type": "bool",
        }
    )
    with pytest.raises(YamlConfigError):
        parse_definition(raw)


def test_button_defaults_press_value_true_for_bool():
    raw = _valid_raw()
    raw["entities"].append(
        {
            "key": "reset",
            "name": "Reset",
            "platform": "button",
            "db": 10,
            "byte": 22,
            "bit": 0,
            "data_type": "bool",
        }
    )
    definition = parse_definition(raw)
    button = next(e for e in definition.entities if e.key == "reset")
    assert button.press_value is True


def test_input_area_does_not_require_db():
    raw = _valid_raw()
    raw["entities"].append(
        {
            "key": "estop",
            "name": "E-Stop",
            "platform": "binary_sensor",
            "area": "input",
            "byte": 0,
            "bit": 0,
            "data_type": "bool",
        }
    )
    definition = parse_definition(raw)
    estop = next(e for e in definition.entities if e.key == "estop")
    assert estop.area == "input"
    assert estop.db == 0


def test_memory_area_real():
    raw = _valid_raw()
    raw["entities"].append(
        {
            "key": "flag_temp",
            "name": "Flag Temp",
            "platform": "sensor",
            "area": "memory",
            "byte": 100,
            "data_type": "real",
        }
    )
    definition = parse_definition(raw)
    flag = next(e for e in definition.entities if e.key == "flag_temp")
    assert flag.area == "memory"


def test_db_area_requires_db_number():
    raw = _valid_raw()
    raw["entities"].append(
        {
            "key": "bad",
            "name": "Bad",
            "platform": "sensor",
            "area": "db",  # db number missing -> defaults to 0 -> invalid
            "byte": 0,
            "data_type": "int",
        }
    )
    with pytest.raises(YamlConfigError):
        parse_definition(raw)


def test_invalid_area():
    raw = _valid_raw()
    raw["entities"][0]["area"] = "register"
    with pytest.raises(YamlConfigError):
        parse_definition(raw)


def test_numeric_button_requires_press_value():
    raw = _valid_raw()
    raw["entities"].append(
        {
            "key": "preset",
            "name": "Preset",
            "platform": "button",
            "db": 10,
            "byte": 24,
            "data_type": "dint",
        }
    )
    with pytest.raises(YamlConfigError):
        parse_definition(raw)
