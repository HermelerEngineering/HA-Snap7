"""Binary sensor platform for the S7 PLC integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PLATFORM_BINARY_SENSOR
from .coordinator import S7PlcCoordinator
from .entity import S7PlcEntity
from .models import EntityDefinition


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from a config entry."""
    coordinator: S7PlcCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        S7PlcBinarySensor(coordinator, entry.entry_id, definition)
        for definition in coordinator.entity_definitions
        if definition.platform == PLATFORM_BINARY_SENSOR
    ]
    async_add_entities(entities)


class S7PlcBinarySensor(S7PlcEntity, BinarySensorEntity):
    """A binary sensor backed by a PLC bool value."""

    def __init__(
        self,
        coordinator: S7PlcCoordinator,
        entry_id: str,
        definition: EntityDefinition,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry_id, definition)
        self._attr_device_class = _parse_device_class(definition.device_class)

    @property
    def is_on(self) -> bool | None:
        """Return True if the bit is set."""
        value = self._value
        if value is None:
            return None
        return bool(value)


def _parse_device_class(value: str | None) -> BinarySensorDeviceClass | None:
    """Map a YAML device_class string to a BinarySensorDeviceClass."""
    if value is None:
        return None
    try:
        return BinarySensorDeviceClass(value)
    except ValueError:
        return None
