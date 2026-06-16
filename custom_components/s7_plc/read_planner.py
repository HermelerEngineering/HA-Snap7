"""Plan grouped DB reads from entity definitions.

To avoid one PLC call per entity, all entities are grouped by data block and
collapsed into the minimal set of contiguous byte ranges that cover every
entity. Adjacent or overlapping ranges within a DB are merged.
"""

from __future__ import annotations

from collections import defaultdict

from .const import DATA_TYPE_SIZE
from .models import EntityDefinition, ReadRequest

# Spans within a DB separated by at most this many unused bytes are merged
# into a single read. One PLC round-trip is far cheaper than transferring a
# handful of extra bytes, so tolerating small gaps reduces total PLC calls.
DEFAULT_MAX_GAP = 16


def _entity_span(entity: EntityDefinition) -> tuple[int, int]:
    """Return the (start, end_exclusive) byte span an entity occupies."""
    size = DATA_TYPE_SIZE[entity.data_type]
    return entity.byte, entity.byte + size


def plan_reads(
    entities: list[EntityDefinition], max_gap: int = DEFAULT_MAX_GAP
) -> list[ReadRequest]:
    """Return a compact set of ReadRequests covering all entities.

    Ranges are grouped per DB and merged when they overlap, are adjacent, or
    are separated by at most ``max_gap`` unused bytes, so a DB read covers as
    many entities as possible in a single PLC call.
    """
    # Group spans per (area, db): reads from different areas — or different
    # data blocks — can never be merged into a single PLC call.
    spans_by_key: dict[tuple[str, int], list[tuple[int, int]]] = defaultdict(list)
    for entity in entities:
        start, end = _entity_span(entity)
        spans_by_key[(entity.area, entity.db)].append((start, end))

    requests: list[ReadRequest] = []
    for area, db in sorted(spans_by_key):
        spans = sorted(spans_by_key[(area, db)])
        cur_start, cur_end = spans[0]
        for start, end in spans[1:]:
            if start <= cur_end + max_gap:
                # Overlapping, adjacent, or within the gap tolerance -> extend.
                cur_end = max(cur_end, end)
            else:
                requests.append(
                    ReadRequest(db=db, start=cur_start, size=cur_end - cur_start, area=area)
                )
                cur_start, cur_end = start, end
        requests.append(
            ReadRequest(db=db, start=cur_start, size=cur_end - cur_start, area=area)
        )

    return requests
