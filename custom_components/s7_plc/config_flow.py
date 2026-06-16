"""Config flow for the S7 PLC integration.

The initial flow only configures the PLC connection. Individual tags
(entities) are added afterwards through the options flow ("Configure"), so no
YAML file is required. Each tag is stored in ``entry.options["entities"]`` as a
dict with the same shape as a YAML entity and validated with the same code.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.util import slugify

from .const import (
    AREA_DB,
    AREAS,
    CONF_ENTITIES,
    CONF_PLC_TYPE,
    CONF_SCAN_INTERVAL,
    DATA_TYPE_BOOL,
    DATA_TYPES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    NUMERIC_DATA_TYPES,
    PLATFORM_BINARY_SENSOR,
    PLATFORM_BUTTON,
    PLATFORM_NUMBER,
    PLATFORM_SENSOR,
    PLATFORM_SWITCH,
    PLC_TYPE_TO_RACK_SLOT,
    PLC_TYPES,
    SUPPORTED_PLATFORMS,
)
from .models import PlcConfig
from .plc_client import PlcConnectionError, S7PlcClient
from .yaml_loader import YamlConfigError, build_entity

_LOGGER = logging.getLogger(__name__)

# "none" sentinel so optional dropdowns show readable text instead of a blank
# first entry; stripped out again when the tag dict is built.
NONE_OPTION = "none"
NUMBER_MODES = ["auto", "box", "slider"]
SENSOR_DEVICE_CLASSES = [NONE_OPTION] + sorted(c.value for c in SensorDeviceClass)
BINARY_DEVICE_CLASSES = [NONE_OPTION] + sorted(c.value for c in BinarySensorDeviceClass)
SENSOR_STATE_CLASSES = [NONE_OPTION] + [c.value for c in SensorStateClass]


def _connection_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the connection (user step) schema."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "Main PLC")): str,
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(
                CONF_PLC_TYPE, default=defaults.get(CONF_PLC_TYPE, PLC_TYPES[0])
            ): vol.In(PLC_TYPES),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
        }
    )


def _test_connection(data: dict[str, Any]) -> None:
    """Try to connect to the PLC. Raises PlcConnectionError on failure."""
    rack, slot = PLC_TYPE_TO_RACK_SLOT[data[CONF_PLC_TYPE]]
    config = PlcConfig(
        name=data[CONF_NAME],
        host=data[CONF_HOST],
        plc_type=data[CONF_PLC_TYPE],
        rack=rack,
        slot=slot,
        scan_interval=data[CONF_SCAN_INTERVAL],
    )
    client = S7PlcClient(config)
    try:
        client.connect()
    finally:
        client.disconnect()


class S7PlcConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the connection config flow for S7 PLC."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the PLC connection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()
            try:
                await self.hass.async_add_executor_job(_test_connection, user_input)
            except PlcConnectionError as err:
                _LOGGER.warning("PLC connection test failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_connection_schema(user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow for managing tags."""
        return S7PlcOptionsFlow()


class S7PlcOptionsFlow(OptionsFlow):
    """Add and remove individual PLC tags on an existing connection."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._entities: list[dict[str, Any]] | None = None
        self._platform: str | None = None

    @property
    def entities(self) -> list[dict[str, Any]]:
        """Return the current list of tag dicts (lazily loaded)."""
        if self._entities is None:
            self._entities = [
                dict(item)
                for item in self.config_entry.options.get(CONF_ENTITIES, [])
            ]
        return self._entities

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the main options menu."""
        menu = ["add_entity"]
        if self.entities:
            menu.append("remove_entity")
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_add_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: pick the platform for the new tag."""
        if user_input is not None:
            self._platform = user_input["platform"]
            return await self.async_step_entity_details()
        return self.async_show_form(
            step_id="add_entity",
            data_schema=vol.Schema(
                {vol.Required("platform"): vol.In(SUPPORTED_PLATFORMS)}
            ),
        )

    async def async_step_entity_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: enter the tag details and validate."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = self._build_entity_data(user_input)
            try:
                build_entity(data)
            except (YamlConfigError, ValueError) as err:
                _LOGGER.warning("Invalid tag definition: %s", err)
                errors["base"] = "invalid_entity"
            else:
                self.entities.append(data)
                return self.async_create_entry(
                    title="", data={CONF_ENTITIES: self.entities}
                )
        return self.async_show_form(
            step_id="entity_details",
            data_schema=self._details_schema(),
            errors=errors,
            description_placeholders={"platform": self._platform or ""},
        )

    async def async_step_remove_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove one or more existing tags."""
        if user_input is not None:
            to_remove = set(user_input.get("remove", []))
            self._entities = [e for e in self.entities if e["key"] not in to_remove]
            return self.async_create_entry(
                title="", data={CONF_ENTITIES: self._entities}
            )
        choices = {
            e["key"]: f"{e['name']} ({e['platform']})" for e in self.entities
        }
        return self.async_show_form(
            step_id="remove_entity",
            data_schema=vol.Schema(
                {vol.Optional("remove", default=[]): cv.multi_select(choices)}
            ),
        )

    def _details_schema(self) -> vol.Schema:
        """Build the per-platform detail schema."""
        platform = self._platform
        fields: dict[Any, Any] = {
            vol.Required("name"): str,
            vol.Required("area", default=AREA_DB): vol.In(AREAS),
            vol.Optional("db", default=1): vol.All(vol.Coerce(int), vol.Range(min=0)),
            vol.Required("byte"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        }
        bit_field = vol.All(vol.Coerce(int), vol.Range(min=0, max=7))

        if platform in (PLATFORM_BINARY_SENSOR, PLATFORM_SWITCH):
            fields[vol.Required("bit", default=0)] = bit_field
        elif platform == PLATFORM_SENSOR:
            fields[vol.Required("data_type", default="real")] = vol.In(DATA_TYPES)
            fields[vol.Optional("bit", default=0)] = bit_field
        elif platform == PLATFORM_NUMBER:
            fields[vol.Required("data_type", default="real")] = vol.In(
                NUMERIC_DATA_TYPES
            )
        elif platform == PLATFORM_BUTTON:
            fields[vol.Required("data_type", default=DATA_TYPE_BOOL)] = vol.In(
                DATA_TYPES
            )
            fields[vol.Optional("bit", default=0)] = bit_field

        if platform in (PLATFORM_SENSOR, PLATFORM_NUMBER):
            fields[vol.Optional("unit", default="")] = str
        if platform == PLATFORM_SENSOR:
            fields[vol.Optional("device_class", default=NONE_OPTION)] = vol.In(
                SENSOR_DEVICE_CLASSES
            )
            fields[vol.Optional("state_class", default=NONE_OPTION)] = vol.In(
                SENSOR_STATE_CLASSES
            )
        if platform == PLATFORM_BINARY_SENSOR:
            fields[vol.Optional("device_class", default=NONE_OPTION)] = vol.In(
                BINARY_DEVICE_CLASSES
            )
        if platform == PLATFORM_NUMBER:
            fields[vol.Optional("min", default="")] = str
            fields[vol.Optional("max", default="")] = str
            fields[vol.Optional("step", default="")] = str
            fields[vol.Optional("mode", default="auto")] = vol.In(NUMBER_MODES)
        if platform == PLATFORM_BUTTON:
            fields[vol.Optional("press_value", default="")] = str

        return vol.Schema(fields)

    def _build_entity_data(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Turn raw form input into a YAML-shaped tag dict."""
        platform = self._platform
        area = user_input.get("area", AREA_DB)
        data: dict[str, Any] = {
            "platform": platform,
            "name": user_input["name"],
            "key": self._unique_key(user_input["name"]),
            "area": area,
            "db": user_input.get("db", 0) if area == AREA_DB else 0,
            "byte": user_input["byte"],
        }

        if platform in (PLATFORM_BINARY_SENSOR, PLATFORM_SWITCH):
            data["data_type"] = DATA_TYPE_BOOL
        else:
            data["data_type"] = user_input["data_type"]

        if "bit" in user_input:
            data["bit"] = user_input["bit"]

        for field in ("unit", "device_class", "state_class", "mode"):
            value = user_input.get(field)
            if value and value != NONE_OPTION:
                data[field] = value

        for field in ("min", "max", "step"):
            raw = user_input.get(field)
            if raw not in (None, ""):
                data[field] = float(raw)

        if platform == PLATFORM_BUTTON:
            data["press_value"] = self._parse_press_value(
                user_input.get("press_value", ""), data["data_type"]
            )

        return data

    @staticmethod
    def _parse_press_value(raw: str, data_type: str) -> Any:
        """Interpret the button press value from the form text field."""
        raw = (raw or "").strip()
        if data_type == DATA_TYPE_BOOL:
            if raw == "":
                return True
            return raw.lower() in ("1", "true", "on", "yes")
        if raw == "":
            # Let build_entity raise a clear "required" error.
            return None
        return float(raw)

    def _unique_key(self, name: str) -> str:
        """Generate a unique slug key for a new tag."""
        base = slugify(name) or "tag"
        existing = {e["key"] for e in self.entities}
        key = base
        index = 2
        while key in existing:
            key = f"{base}_{index}"
            index += 1
        return key
