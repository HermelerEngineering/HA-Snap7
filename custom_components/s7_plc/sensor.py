"""Sensor platform for the S7 PLC integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PLATFORM_SENSOR
from .coordinator import S7PlcCoordinator
from .entity import S7PlcEntity
from .models import EntityDefinition


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: S7PlcCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        S7PlcSensor(coordinator, entry.entry_id, definition)
        for definition in coordinator.entity_definitions
        if definition.platform == PLATFORM_SENSOR
    ]
    async_add_entities(entities)


class S7PlcSensor(S7PlcEntity, SensorEntity):
    """A sensor backed by a numeric PLC value."""

    def __init__(
        self,
        coordinator: S7PlcCoordinator,
        entry_id: str,
        definition: EntityDefinition,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry_id, definition)
        self._attr_native_unit_of_measurement = definition.unit
        self._attr_device_class = _parse_device_class(definition.device_class)
        self._attr_state_class = _parse_state_class(definition.state_class)

    @property
    def native_value(self) -> int | float | None:
        """Return the latest numeric value."""
        value = self._value
        if isinstance(value, bool):
            # Defensive: a bool sneaking into a sensor becomes 0/1.
            return int(value)
        if isinstance(value, (int, float)):
            return value
        return None


def _parse_device_class(value: str | None) -> SensorDeviceClass | None:
    """Map a YAML device_class string to a SensorDeviceClass."""
    if value is None:
        return None
    try:
        return SensorDeviceClass(value)
    except ValueError:
        return None


def _parse_state_class(value: str | None) -> SensorStateClass | None:
    """Map a YAML state_class string to a SensorStateClass."""
    if value is None:
        return None
    try:
        return SensorStateClass(value)
    except ValueError:
        return None
