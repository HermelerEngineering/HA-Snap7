"""Central polling layer for the S7 PLC integration.

A single :class:`S7PlcCoordinator` per config entry owns the one PLC client,
issues grouped DB reads, parses values out of the raw buffers and exposes the
parsed values to entities. Entities never talk to the PLC directly; they read
from ``coordinator.data``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, READABLE_PLATFORMS
from .models import EntityDefinition, PlcConfig, ReadRequest
from .parser import ParseError, parse_value
from .plc_client import PlcConnectionError, S7PlcClient
from .read_planner import plan_reads
from .writer import serialize

_LOGGER = logging.getLogger(__name__)


class S7PlcCoordinator(DataUpdateCoordinator[dict[str, object]]):
    """Polls the PLC and caches parsed entity values keyed by entity key."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: PlcConfig,
        entities: list[EntityDefinition],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {config.name}",
            update_interval=timedelta(seconds=config.scan_interval),
        )
        self._config = config
        self._entities = entities
        self._client = S7PlcClient(config)
        # snap7's client is not thread-safe and shares one TCP connection, so
        # every PLC operation (poll reads and writes) must be serialized.
        # Without this, a write overlapping a poll corrupts the S7 protocol
        # stream ("Invalid TPKT version" / "Receive timeout").
        self._lock = asyncio.Lock()
        # Only readable entities (everything except stateless buttons) take part
        # in the polling read plan.
        self._readable = [e for e in entities if e.platform in READABLE_PLATFORMS]
        self._read_plan: list[ReadRequest] = plan_reads(self._readable)
        _LOGGER.debug(
            "Planned %d DB read(s) for %d readable entities: %s",
            len(self._read_plan),
            len(self._readable),
            self._read_plan,
        )

    @property
    def config(self) -> PlcConfig:
        """Return the PLC connection config."""
        return self._config

    @property
    def entity_definitions(self) -> list[EntityDefinition]:
        """Return the entity definitions managed by this coordinator."""
        return self._entities

    async def async_shutdown(self) -> None:
        """Disconnect the PLC client on unload."""
        await super().async_shutdown()
        async with self._lock:
            await self.hass.async_add_executor_job(self._client.disconnect)

    async def _async_update_data(self) -> dict[str, object]:
        """Fetch all planned DB ranges and parse every entity value.

        Runs in the executor because python-snap7 is blocking. A failure here
        marks the coordinator (and therefore all entities) unavailable; the
        next poll will attempt to reconnect.
        """
        async with self._lock:
            try:
                return await self.hass.async_add_executor_job(self._poll)
            except PlcConnectionError as err:
                # Drop the connection so the next cycle performs a clean reconnect.
                await self.hass.async_add_executor_job(self._client.disconnect)
                raise UpdateFailed(str(err)) from err

    def _poll(self) -> dict[str, object]:
        """Blocking poll: connect if needed, read DBs, parse values."""
        if not self._client.is_connected:
            self._client.connect()

        buffers: dict[ReadRequest, bytes] = {}
        for request in self._read_plan:
            buffers[request] = bytes(
                self._client.read(
                    request.area, request.db, request.start, request.size
                )
            )

        return self._parse_all(buffers)

    def _parse_all(self, buffers: dict[ReadRequest, bytes]) -> dict[str, object]:
        """Parse every readable entity value out of the read buffers."""
        values: dict[str, object] = {}
        for entity in self._readable:
            request = self._request_for(entity)
            buffer = buffers[request]
            rel_byte = entity.byte - request.start
            try:
                value = parse_value(buffer, entity.data_type, rel_byte, entity.bit)
            except ParseError as err:
                _LOGGER.warning("Failed to parse entity '%s': %s", entity.key, err)
                values[entity.key] = None
                continue
            values[entity.key] = self._apply_scale(entity, value)
        return values

    @staticmethod
    def _apply_scale(entity: EntityDefinition, value: object) -> object:
        """Apply optional scale/offset to numeric values (read direction)."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return value
        if entity.scale is not None:
            value = value * entity.scale
        if entity.offset is not None:
            value = value + entity.offset
        return value

    @staticmethod
    def _unapply_scale(entity: EntityDefinition, value: float) -> float:
        """Invert scale/offset to turn a display value into a raw PLC value."""
        if entity.offset is not None:
            value = value - entity.offset
        if entity.scale:
            value = value / entity.scale
        return value

    async def async_write_bool(self, entity: EntityDefinition, value: bool) -> None:
        """Write a single bit to the PLC and refresh state."""
        async with self._lock:
            try:
                await self.hass.async_add_executor_job(
                    self._client.write_bit,
                    entity.area,
                    entity.db,
                    entity.byte,
                    entity.bit,
                    value,
                )
            except PlcConnectionError:
                await self.hass.async_add_executor_job(self._client.disconnect)
                raise
        _LOGGER.debug("Wrote bool %s to %s", value, entity.key)
        await self.async_request_refresh()

    async def async_write_number(self, entity: EntityDefinition, value: float) -> None:
        """Serialize and write a numeric value to the PLC and refresh state."""
        raw = self._unapply_scale(entity, value)
        data = serialize(entity.data_type, raw)
        async with self._lock:
            try:
                await self.hass.async_add_executor_job(
                    self._client.write, entity.area, entity.db, entity.byte, data
                )
            except PlcConnectionError:
                await self.hass.async_add_executor_job(self._client.disconnect)
                raise
        _LOGGER.debug("Wrote number %s (raw %s) to %s", value, raw, entity.key)
        await self.async_request_refresh()

    async def async_write_entity(self, entity: EntityDefinition, value: object) -> None:
        """Write ``value`` to ``entity`` choosing bit vs byte write by type."""
        if entity.is_bool:
            await self.async_write_bool(entity, bool(value))
        else:
            await self.async_write_number(entity, float(value))

    def _request_for(self, entity: EntityDefinition) -> ReadRequest:
        """Return the ReadRequest whose range covers ``entity``."""
        for request in self._read_plan:
            if (
                request.area == entity.area
                and request.db == entity.db
                and request.start <= entity.byte < request.end
            ):
                return request
        # plan_reads guarantees coverage; this is a safety net.
        raise UpdateFailed(f"No read range covers entity '{entity.key}'")
