"""Unit tests for the grouped read planner."""

from custom_components.s7_plc.models import EntityDefinition
from custom_components.s7_plc.read_planner import plan_reads


def _entity(key, db, byte, data_type, bit=0, area="db"):
    return EntityDefinition(
        key=key,
        name=key,
        platform="sensor",
        area=area,
        db=db,
        byte=byte,
        bit=bit,
        data_type=data_type,
    )


def test_groups_single_db_into_one_range():
    # MVP DB layout: bools at byte 0, real at 2 (4 bytes), dint at 6 (4 bytes).
    entities = [
        _entity("running", 1, 0, "bool", 0),
        _entity("fault", 1, 0, "bool", 1),
        _entity("speed", 1, 2, "real"),
        _entity("count", 1, 6, "dint"),
    ]
    reads = plan_reads(entities)
    assert len(reads) == 1
    assert reads[0].db == 1
    assert reads[0].start == 0
    assert reads[0].size == 10  # bytes 0..9 inclusive


def test_separate_dbs_get_separate_reads():
    entities = [
        _entity("a", 1, 0, "int"),
        _entity("b", 2, 0, "int"),
    ]
    reads = plan_reads(entities)
    assert len(reads) == 2
    assert {r.db for r in reads} == {1, 2}


def test_non_adjacent_ranges_in_same_db_split():
    # A gap large enough not to merge.
    entities = [
        _entity("a", 1, 0, "byte"),
        _entity("b", 1, 100, "byte"),
    ]
    reads = plan_reads(entities)
    assert len(reads) == 2
    sizes = sorted(r.size for r in reads)
    assert sizes == [1, 1]


def test_adjacent_ranges_merge():
    entities = [
        _entity("a", 1, 0, "int"),  # bytes 0-1
        _entity("b", 1, 2, "int"),  # bytes 2-3, adjacent
    ]
    reads = plan_reads(entities)
    assert len(reads) == 1
    assert reads[0].start == 0
    assert reads[0].size == 4


def test_different_areas_never_merge():
    # Same byte offsets but different memory areas must stay separate reads.
    entities = [
        _entity("a", 0, 0, "int", area="input"),
        _entity("b", 0, 0, "int", area="output"),
        _entity("c", 0, 0, "int", area="memory"),
        _entity("d", 1, 0, "int", area="db"),
    ]
    reads = plan_reads(entities)
    assert len(reads) == 4
    assert {r.area for r in reads} == {"input", "output", "memory", "db"}


def test_same_area_merges():
    entities = [
        _entity("a", 0, 0, "int", area="memory"),
        _entity("b", 0, 2, "int", area="memory"),
    ]
    reads = plan_reads(entities)
    assert len(reads) == 1
    assert reads[0].area == "memory"
    assert reads[0].size == 4


def test_overlapping_ranges_merge():
    entities = [
        _entity("a", 1, 0, "dint"),  # bytes 0-3
        _entity("b", 1, 2, "int"),   # bytes 2-3, overlaps
    ]
    reads = plan_reads(entities)
    assert len(reads) == 1
    assert reads[0].size == 4
