"""Shared base entity for the S7 PLC integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import S7PlcCoordinator
from .models import EntityDefinition


class S7PlcEntity(CoordinatorEntity[S7PlcCoordinator]):
    """Base entity reading its value from the coordinator cache."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: S7PlcCoordinator,
        entry_id: str,
        definition: EntityDefinition,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._definition = definition
        self._attr_unique_id = f"{entry_id}_{definition.key}"
        self._attr_name = definition.name
        if definition.icon:
            self._attr_icon = definition.icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=coordinator.config.name,
            manufacturer="Siemens",
            model=coordinator.config.plc_type,
        )

    @property
    def _value(self) -> object:
        """Return the latest parsed value for this entity, or None."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._definition.key)

    @property
    def available(self) -> bool:
        """Entity is available only when the coordinator has a fresh value."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.get(self._definition.key) is not None
        )
