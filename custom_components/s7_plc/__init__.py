"""The S7 PLC integration.

The Home Assistant entry points live behind a soft import guard so that the
pure-logic modules (parser, read_planner, yaml_loader) can be unit tested in
an environment where Home Assistant is not installed. In a real Home Assistant
runtime the imports always succeed and the entry points are defined as usual.
"""

from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.const import CONF_HOST, CONF_NAME
    from homeassistant.core import HomeAssistant
    from homeassistant.exceptions import ConfigEntryNotReady

    _HA_AVAILABLE = True
except ImportError:  # pragma: no cover - unit-test environment without HA
    _HA_AVAILABLE = False


if _HA_AVAILABLE:
    from .const import (
        CONF_ENTITIES,
        CONF_PLC_TYPE,
        CONF_PORT,
        CONF_SCAN_INTERVAL,
        CONF_YAML_PATH,
        DEFAULT_PORT,
        DEFAULT_SCAN_INTERVAL,
        DOMAIN,
        PLATFORMS,
        PLC_TYPE_TO_RACK_SLOT,
    )
    from .coordinator import S7PlcCoordinator
    from .models import EntityDefinition, PlcConfig
    from .yaml_loader import YamlConfigError, build_entity, load_entities

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Set up S7 PLC from a config entry."""
        data = entry.data
        plc_type = data[CONF_PLC_TYPE]
        rack, slot = PLC_TYPE_TO_RACK_SLOT[plc_type]

        config = PlcConfig(
            name=data.get(CONF_NAME, "PLC"),
            host=data[CONF_HOST],
            plc_type=plc_type,
            rack=rack,
            slot=slot,
            scan_interval=data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            port=data.get(CONF_PORT, DEFAULT_PORT),
        )

        entities: list[EntityDefinition] = []

        # Tags added through the UI options flow.
        try:
            for item in entry.options.get(CONF_ENTITIES, []):
                entities.append(build_entity(dict(item)))
        except YamlConfigError as err:
            _LOGGER.error("Invalid tag in options for %s: %s", config.name, err)
            raise ConfigEntryNotReady(f"Invalid tag definition: {err}") from err

        # Backward compatibility: a YAML path may still be present in entry.data.
        yaml_path = data.get(CONF_YAML_PATH)
        if yaml_path:
            try:
                entities.extend(
                    await hass.async_add_executor_job(
                        load_entities, hass.config.config_dir, yaml_path
                    )
                )
            except YamlConfigError as err:
                _LOGGER.error("Invalid YAML for %s: %s", config.name, err)
                raise ConfigEntryNotReady(f"Invalid YAML configuration: {err}") from err

        coordinator = S7PlcCoordinator(hass, config, entities)

        # Raises ConfigEntryNotReady on connection failure so HA retries setup.
        await coordinator.async_config_entry_first_refresh()

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(_async_update_listener))
        return True

    async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Unload a config entry."""
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        if unload_ok:
            coordinator: S7PlcCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
            await coordinator.async_shutdown()
        return unload_ok

    async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Reload the entry when its options change."""
        await hass.config_entries.async_reload(entry.entry_id)
