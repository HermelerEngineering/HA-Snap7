"""Number platform for the S7 PLC integration (writes a numeric value)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PLATFORM_NUMBER
from .coordinator import S7PlcCoordinator
from .entity import S7PlcEntity
from .models import EntityDefinition

_MODE_MAP = {
    "auto": NumberMode.AUTO,
    "box": NumberMode.BOX,
    "slider": NumberMode.SLIDER,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities from a config entry."""
    coordinator: S7PlcCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        S7PlcNumber(coordinator, entry.entry_id, definition)
        for definition in coordinator.entity_definitions
        if definition.platform == PLATFORM_NUMBER
    )


class S7PlcNumber(S7PlcEntity, NumberEntity):
    """A number backed by a numeric PLC value."""

    def __init__(
        self,
        coordinator: S7PlcCoordinator,
        entry_id: str,
        definition: EntityDefinition,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, entry_id, definition)
        self._attr_native_unit_of_measurement = definition.unit
        if definition.min_value is not None:
            self._attr_native_min_value = definition.min_value
        if definition.max_value is not None:
            self._attr_native_max_value = definition.max_value
        if definition.step is not None:
            self._attr_native_step = definition.step
        self._attr_mode = _MODE_MAP.get(definition.mode or "auto", NumberMode.AUTO)

    @property
    def native_value(self) -> float | None:
        """Return the current value from the coordinator cache."""
        value = self._value
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Write a new value to the PLC."""
        await self.coordinator.async_write_number(self._definition, value)
