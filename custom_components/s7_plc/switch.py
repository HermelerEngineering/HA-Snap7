"""Switch platform for the S7 PLC integration (writes a bool bit)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PLATFORM_SWITCH
from .coordinator import S7PlcCoordinator
from .entity import S7PlcEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches from a config entry."""
    coordinator: S7PlcCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        S7PlcSwitch(coordinator, entry.entry_id, definition)
        for definition in coordinator.entity_definitions
        if definition.platform == PLATFORM_SWITCH
    )


class S7PlcSwitch(S7PlcEntity, SwitchEntity):
    """A switch backed by a PLC bool value."""

    @property
    def is_on(self) -> bool | None:
        """Return the current bit state from the coordinator cache."""
        value = self._value
        if value is None:
            return None
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the bit to True."""
        await self.coordinator.async_write_bool(self._definition, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set the bit to False."""
        await self.coordinator.async_write_bool(self._definition, False)
