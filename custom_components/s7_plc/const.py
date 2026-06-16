"""Constants for the S7 PLC integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "s7_plc"

PLATFORMS: Final = ["binary_sensor", "sensor", "switch", "number", "button"]

# Configuration keys (config entry / config flow)
CONF_NAME: Final = "name"
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_PLC_TYPE: Final = "plc_type"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_YAML_PATH: Final = "yaml_path"
# Options key holding the list of UI-defined tag dicts.
CONF_ENTITIES: Final = "entities"

# Defaults
DEFAULT_PORT: Final = 102
DEFAULT_SCAN_INTERVAL: Final = 2
MIN_SCAN_INTERVAL: Final = 1

# Supported PLC types
PLC_TYPE_S7_1200: Final = "s7_1200"
PLC_TYPE_S7_1500: Final = "s7_1500"
PLC_TYPE_S7_300: Final = "s7_300"

PLC_TYPES: Final = [PLC_TYPE_S7_1200, PLC_TYPE_S7_1500, PLC_TYPE_S7_300]

# Rack/slot is derived from the PLC type (Rack, Slot).
PLC_TYPE_TO_RACK_SLOT: Final = {
    PLC_TYPE_S7_1200: (0, 1),
    PLC_TYPE_S7_1500: (0, 1),
    PLC_TYPE_S7_300: (0, 2),
}

# Memory areas. "db" addresses a data block (needs a DB number); the others
# address the process image / flags directly (no DB number).
AREA_DB: Final = "db"          # Data block        -> snap7 Area.DB
AREA_INPUT: Final = "input"    # Inputs   (I / E)  -> snap7 Area.PE
AREA_OUTPUT: Final = "output"  # Outputs  (Q / A)  -> snap7 Area.PA
AREA_MEMORY: Final = "memory"  # Merkers  (M)      -> snap7 Area.MK

AREAS: Final = [AREA_DB, AREA_INPUT, AREA_OUTPUT, AREA_MEMORY]

# Supported data types (read-only v1)
DATA_TYPE_BOOL: Final = "bool"
DATA_TYPE_BYTE: Final = "byte"
DATA_TYPE_INT: Final = "int"
DATA_TYPE_UINT: Final = "uint"
DATA_TYPE_DINT: Final = "dint"
DATA_TYPE_REAL: Final = "real"

DATA_TYPES: Final = [
    DATA_TYPE_BOOL,
    DATA_TYPE_BYTE,
    DATA_TYPE_INT,
    DATA_TYPE_UINT,
    DATA_TYPE_DINT,
    DATA_TYPE_REAL,
]

# Number of bytes each (non-bool) data type occupies in the PLC buffer.
DATA_TYPE_SIZE: Final = {
    DATA_TYPE_BOOL: 1,
    DATA_TYPE_BYTE: 1,
    DATA_TYPE_INT: 2,
    DATA_TYPE_UINT: 2,
    DATA_TYPE_DINT: 4,
    DATA_TYPE_REAL: 4,
}

# Supported entity platforms.
PLATFORM_BINARY_SENSOR: Final = "binary_sensor"
PLATFORM_SENSOR: Final = "sensor"
PLATFORM_SWITCH: Final = "switch"
PLATFORM_NUMBER: Final = "number"
PLATFORM_BUTTON: Final = "button"

SUPPORTED_PLATFORMS: Final = [
    PLATFORM_BINARY_SENSOR,
    PLATFORM_SENSOR,
    PLATFORM_SWITCH,
    PLATFORM_NUMBER,
    PLATFORM_BUTTON,
]

# Platforms whose current value is read back from the PLC each poll.
# Buttons are stateless write-only and therefore excluded from the read plan.
READABLE_PLATFORMS: Final = [
    PLATFORM_BINARY_SENSOR,
    PLATFORM_SENSOR,
    PLATFORM_SWITCH,
    PLATFORM_NUMBER,
]

# Platforms that can write a value back to the PLC.
WRITABLE_PLATFORMS: Final = [PLATFORM_SWITCH, PLATFORM_NUMBER, PLATFORM_BUTTON]

# Numeric data types (everything except bool).
NUMERIC_DATA_TYPES: Final = [
    DATA_TYPE_BYTE,
    DATA_TYPE_INT,
    DATA_TYPE_UINT,
    DATA_TYPE_DINT,
    DATA_TYPE_REAL,
]

# Inclusive value ranges for the integer data types, used to validate writes.
INT_RANGES: Final = {
    DATA_TYPE_BYTE: (0, 255),
    DATA_TYPE_INT: (-32768, 32767),
    DATA_TYPE_UINT: (0, 65535),
    DATA_TYPE_DINT: (-2147483648, 2147483647),
}
