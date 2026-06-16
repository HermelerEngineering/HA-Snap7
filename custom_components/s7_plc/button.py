"""Button platform for the S7 PLC integration (writes a fixed value on press).

Buttons are stateless: they do not appear in the polling read plan and have no
value of their own. Pressing the button writes the configured ``press_value``
to the target address.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PLATFORM_BUTTON
from .coordinator import S7PlcCoordinator
from .entity import S7PlcEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons from a config entry."""
    coordinator: S7PlcCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        S7PlcButton(coordinator, entry.entry_id, definition)
        for definition in coordinator.entity_definitions
        if definition.platform == PLATFORM_BUTTON
    )


class S7PlcButton(S7PlcEntity, ButtonEntity):
    """A button that writes a fixed value to the PLC on press."""

    @property
    def available(self) -> bool:
        """A button is available whenever the coordinator's last update succeeded."""
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        """Write the configured press value to the PLC."""
        await self.coordinator.async_write_entity(
            self._definition, self._definition.press_value
        )
