"""Load and validate PLC entity definitions from a YAML file.

The YAML path configured in the config entry is resolved relative to the
Home Assistant ``/config`` directory. Validation errors raise
``YamlConfigError`` with a clear, user-facing message so that setup fails
loudly instead of producing broken entities.
"""

from __future__ import annotations

import logging
import os

import yaml

from .const import (
    AREA_DB,
    AREAS,
    DATA_TYPE_BOOL,
    DATA_TYPES,
    NUMERIC_DATA_TYPES,
    PLATFORM_BUTTON,
    PLATFORM_NUMBER,
    PLATFORM_SWITCH,
    PLC_TYPE_TO_RACK_SLOT,
    PLC_TYPES,
    SUPPORTED_PLATFORMS,
)
from .models import EntityDefinition, PlcConfig, PlcDefinition

_LOGGER = logging.getLogger(__name__)


class YamlConfigError(Exception):
    """Raised when the YAML configuration is missing or invalid."""


def build_entity(data: dict) -> EntityDefinition:
    """Validate and build a single EntityDefinition from a plain dict.

    Used by the UI options flow, where each tag is stored as a dict with the
    same shape as a YAML entity. Raises :class:`YamlConfigError` on invalid
    input, exactly like the YAML path.
    """
    return _parse_entity(data, 0)


def load_entities(config_dir: str, yaml_path: str) -> list[EntityDefinition]:
    """Load and validate just the entity definitions from a YAML file.

    The connection parameters come from the config entry, so only the
    ``entities`` section of the YAML is required here.
    """
    full_path = _resolve_path(config_dir, yaml_path)
    raw = _read_yaml(full_path)
    if not isinstance(raw, dict):
        raise YamlConfigError("Top-level YAML must be a mapping with an 'entities' list.")
    return _parse_entities(raw.get("entities"))


def load_definition(config_dir: str, yaml_path: str) -> PlcDefinition:
    """Load, parse and validate the full PLC definition file.

    ``config_dir`` is the Home Assistant config directory; ``yaml_path`` is
    relative to it. The ``plc`` section is optional here.
    """
    full_path = _resolve_path(config_dir, yaml_path)
    raw = _read_yaml(full_path)
    return parse_definition(raw)


def parse_definition(raw: object) -> PlcDefinition:
    """Validate a raw parsed YAML structure into a PlcDefinition.

    The ``plc`` section is optional; when absent, ``PlcDefinition.plc`` is None.
    """
    if not isinstance(raw, dict):
        raise YamlConfigError("Top-level YAML must be a mapping with 'plc' and 'entities'.")

    plc = _parse_plc(raw["plc"]) if "plc" in raw else None
    entities = _parse_entities(raw.get("entities"))
    return PlcDefinition(plc=plc, entities=entities)


def _resolve_path(config_dir: str, yaml_path: str) -> str:
    """Resolve and validate the YAML file path inside the config dir."""
    if not yaml_path:
        raise YamlConfigError("No YAML path configured.")
    full_path = os.path.join(config_dir, yaml_path)
    if not os.path.isfile(full_path):
        raise YamlConfigError(f"YAML file not found: {full_path}")
    return full_path


def _read_yaml(full_path: str) -> object:
    """Read and parse a YAML file from disk."""
    try:
        with open(full_path, encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except OSError as err:
        raise YamlConfigError(f"Could not read YAML file {full_path}: {err}") from err
    except yaml.YAMLError as err:
        raise YamlConfigError(f"Invalid YAML in {full_path}: {err}") from err


def _parse_plc(data: object) -> PlcConfig:
    """Validate and build the PlcConfig from the 'plc' section."""
    if not isinstance(data, dict):
        raise YamlConfigError("Missing or invalid 'plc' section.")

    name = data.get("name")
    host = data.get("host")
    plc_type = data.get("plc_type")
    scan_interval = data.get("scan_interval", 2)
    port = data.get("port", 102)

    if not isinstance(name, str) or not name:
        raise YamlConfigError("plc.name is required and must be a non-empty string.")
    if not isinstance(host, str) or not host:
        raise YamlConfigError("plc.host is required and must be a non-empty string.")
    if plc_type not in PLC_TYPES:
        raise YamlConfigError(
            f"plc.plc_type '{plc_type}' is invalid. Expected one of: {PLC_TYPES}."
        )
    if not isinstance(scan_interval, int) or scan_interval < 1:
        raise YamlConfigError("plc.scan_interval must be an integer >= 1.")
    if not isinstance(port, int) or port <= 0:
        raise YamlConfigError("plc.port must be a positive integer.")

    rack, slot = PLC_TYPE_TO_RACK_SLOT[plc_type]
    return PlcConfig(
        name=name,
        host=host,
        plc_type=plc_type,
        rack=rack,
        slot=slot,
        scan_interval=scan_interval,
        port=port,
    )


def _parse_entities(data: object) -> list[EntityDefinition]:
    """Validate and build the list of EntityDefinitions."""
    if not isinstance(data, list) or not data:
        raise YamlConfigError("'entities' must be a non-empty list.")

    entities: list[EntityDefinition] = []
    seen_keys: set[str] = set()
    for index, item in enumerate(data):
        entity = _parse_entity(item, index)
        if entity.key in seen_keys:
            raise YamlConfigError(f"Duplicate entity key '{entity.key}'.")
        seen_keys.add(entity.key)
        entities.append(entity)
    return entities


def _parse_entity(item: object, index: int) -> EntityDefinition:
    """Validate and build a single EntityDefinition."""
    where = f"entities[{index}]"
    if not isinstance(item, dict):
        raise YamlConfigError(f"{where} must be a mapping.")

    key = item.get("key")
    name = item.get("name")
    platform = item.get("platform")
    data_type = item.get("data_type")
    area = item.get("area", AREA_DB)
    db = item.get("db", 0)
    byte = item.get("byte")
    bit = item.get("bit", 0)

    if not isinstance(key, str) or not key:
        raise YamlConfigError(f"{where}.key is required and must be a non-empty string.")
    if not isinstance(name, str) or not name:
        raise YamlConfigError(f"{where}.name is required and must be a non-empty string.")
    if platform not in SUPPORTED_PLATFORMS:
        raise YamlConfigError(
            f"{where}.platform '{platform}' is invalid. Expected one of: {SUPPORTED_PLATFORMS}."
        )
    if data_type not in DATA_TYPES:
        raise YamlConfigError(
            f"{where}.data_type '{data_type}' is invalid. Expected one of: {DATA_TYPES}."
        )
    if area not in AREAS:
        raise YamlConfigError(
            f"{where}.area '{area}' is invalid. Expected one of: {AREAS}."
        )
    if not isinstance(db, int) or db < 0:
        raise YamlConfigError(f"{where}.db must be a non-negative integer.")
    if area == AREA_DB and db < 1:
        raise YamlConfigError(f"{where}.db is required (>= 1) for the 'db' area.")
    if area != AREA_DB:
        # DB number is meaningless outside the DB area; normalise it.
        db = 0
    if not isinstance(byte, int) or byte < 0:
        raise YamlConfigError(f"{where}.byte is required and must be a non-negative integer.")
    if not isinstance(bit, int) or not 0 <= bit <= 7:
        raise YamlConfigError(f"{where}.bit must be an integer between 0 and 7.")
    if data_type == DATA_TYPE_BOOL and "bit" not in item:
        _LOGGER.debug("%s is bool without explicit bit; defaulting to bit 0.", where)

    # Per-platform data-type constraints for writable entities.
    if platform == PLATFORM_SWITCH and data_type != DATA_TYPE_BOOL:
        raise YamlConfigError(f"{where}: switch requires data_type 'bool'.")
    if platform == PLATFORM_NUMBER and data_type not in NUMERIC_DATA_TYPES:
        raise YamlConfigError(
            f"{where}: number requires a numeric data_type ({NUMERIC_DATA_TYPES})."
        )

    scale = _optional_number(item.get("scale"), f"{where}.scale")
    offset = _optional_number(item.get("offset"), f"{where}.offset")
    min_value = _optional_number(item.get("min"), f"{where}.min")
    max_value = _optional_number(item.get("max"), f"{where}.max")
    step = _optional_number(item.get("step"), f"{where}.step")
    mode = item.get("mode")
    if mode is not None and mode not in ("auto", "box", "slider"):
        raise YamlConfigError(f"{where}.mode must be one of: auto, box, slider.")

    press_value = _parse_press_value(item, where, platform, data_type)

    return EntityDefinition(
        key=key,
        name=name,
        platform=platform,
        area=area,
        db=db,
        byte=byte,
        bit=bit,
        data_type=data_type,
        unit=item.get("unit"),
        device_class=item.get("device_class"),
        state_class=item.get("state_class"),
        icon=item.get("icon"),
        scale=scale,
        offset=offset,
        min_value=min_value,
        max_value=max_value,
        step=step,
        mode=mode,
        press_value=press_value,
    )


def _parse_press_value(
    item: dict, where: str, platform: str, data_type: str
) -> bool | int | float | None:
    """Validate the value a button writes on press."""
    if platform != PLATFORM_BUTTON:
        return None
    raw = item.get("press_value")
    if data_type == DATA_TYPE_BOOL:
        # Default a bool button to writing True (momentary set).
        if raw is None:
            return True
        if not isinstance(raw, bool):
            raise YamlConfigError(f"{where}.press_value must be a boolean for bool.")
        return raw
    if raw is None:
        raise YamlConfigError(f"{where}.press_value is required for a numeric button.")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise YamlConfigError(f"{where}.press_value must be a number.")
    return raw


def _optional_number(value: object, where: str) -> float | None:
    """Validate an optional numeric field."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise YamlConfigError(f"{where} must be a number.")
    return float(value)
