# Home Assistant — Siemens S7 PLC

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration that reads tags from Siemens S7 PLCs
directly via [python-snap7](https://python-snap7.readthedocs.io/) and exposes
them as Home Assistant entities.

Reading (`sensor`, `binary_sensor`) and writing (`switch`, `number`, `button`)
are both supported.

> ⚠️ **Writing affects real equipment.** Only point write entities at addresses
> you know are safe. Writing to a live machine control can physically
> start/stop equipment.

## Status

Read and write support is implemented and **verified against a real
Siemens S7-1200** PLC:

| Capability | Platforms | Status |
|------------|-----------|--------|
| Read | `sensor`, `binary_sensor` | ✅ verified on hardware — DB, input, output and memory |
| Write bool | `switch`, `button` | ✅ verified on DB, memory (M) and output (Q); read-modify-write preserves neighbouring bits |
| Write numeric | `number`, `button` | ✅ verified on DB and memory (`real` big-endian confirmed, e.g. `42.5` → `0x422A0000`) |
| Config flow | — | ✅ connection-only setup with live connection test |
| Tag management | — | ✅ add/remove tags in the UI (options flow); no YAML needed |
| Automatic reconnect | — | ✅ implemented |

- **46 unit tests** pass (parser, writer, read planner, YAML loader).
- Standalone scripts ([`tools/live_read.py`](tools/live_read.py),
  [`tools/live_write.py`](tools/live_write.py)) exercise the **same** code path
  as the Home Assistant entities, against a live PLC.

Not yet covered: options flow (edit connection without re-adding), optimized-DB
support, and `suggested_display_precision` for rounding floats in the UI.

## Features

- One central PLC client per config entry (no per-entity Snap7 connections).
- One central polling layer via `DataUpdateCoordinator`.
- Reads from **data blocks and direct I/O** (inputs, outputs, merkers) are
  **grouped per area** into the minimal set of contiguous byte ranges, so
  multiple tags in the same area cost a single PLC call.
- Tags are defined in a YAML file: `sensor`, `binary_sensor` (read) and
  `switch`, `number`, `button` (write).
- Big-endian (Siemens) value parsing/serialization for `bool`, `byte`, `int`,
  `uint`, `dint`, `real`. Bool writes use a safe read-modify-write of the byte.
- Automatic reconnect: when the PLC is unreachable, entities become
  `unavailable` and the next poll retries the connection.

## Supported PLC types

The rack/slot is derived automatically from the PLC type:

| PLC type   | Rack | Slot |
|------------|------|------|
| `s7_1200`  | 0    | 1    |
| `s7_1500`  | 0    | 1    |
| `s7_300`   | 0    | 2    |

> For S7-1200 / S7-1500, enable PUT/GET communication and use a
> **non-optimized** DB with fixed byte offsets.

## Requirements

`python-snap7` is a wrapper around the native **snap7** library (`libsnap7`).
The Python package is installed automatically from `manifest.json`, but the
native library must be present in the runtime:

- **Home Assistant OS / Container**: recent `python-snap7` wheels bundle the
  native library, so no extra step is normally needed.
- **Core / venv on Debian/Ubuntu**: install it via your package manager or
  build it from the [snap7 project](https://snap7.sourceforge.net/).

If setup fails with a "library not found" error, the native library is missing.

## Installation via HACS (recommended)

This repository is a valid HACS custom repository.

1. In Home Assistant: **HACS → ⋮ (top right) → Custom repositories**.
2. Add the repository URL, category **Integration**, and click **Add**.
3. Search for **Siemens S7 PLC** in HACS and **Download** it.
4. **Restart Home Assistant**.
5. **Settings → Devices & Services → Add Integration → Siemens S7 PLC**.

HACS installs releases by tag, so cut a GitHub release (e.g. `0.1.0`) whose
tag matches the `version` in `manifest.json`.

## Installation (manual)

1. Copy `custom_components/s7_plc` to `/config/custom_components/s7_plc`.
2. (Optional) Enable debug logging in `configuration.yaml`:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.s7_plc: debug
   ```
3. Restart Home Assistant.
4. **Settings → Devices & Services → Add Integration → Siemens S7 PLC**.
5. Fill in the connection details. The connection is tested immediately.
6. Add tags one by one via the integration's **Configure** button
   (see [Adding tags via the UI](#adding-tags-via-the-ui)).

### Config flow fields

| Field           | Example              | Notes                              |
|-----------------|----------------------|------------------------------------|
| Name            | `Main PLC`           | Device name in Home Assistant      |
| Host            | `192.168.1.10`       | PLC IP address                     |
| PLC type        | `s7_1500`            | Determines rack/slot               |
| Scan interval   | `2`                  | Seconds between polls (min 1)      |

## Adding tags via the UI

After the connection is created, open the integration and click **Configure**:

- **Add a tag** → pick the entity type (`sensor`, `binary_sensor`, `switch`,
  `number`, `button`), then fill in the address (DB / byte / bit) and options.
- **Remove tags** → select existing tags to delete.

Each change reloads the connection so new entities appear immediately. No YAML
file is required. The address fields map directly to the data types below.

## YAML tag definition (optional / legacy)

Tags are normally added through the UI (above). A YAML file is **no longer
required**, but is still supported for power users: if an entry was created
with a `yaml_path`, those tags are loaded in addition to any UI tags. This is
also the format used by the standalone test scripts under `tools/`.

```yaml
plc:                       # optional — informational only
  name: "Main PLC"
  host: "192.168.1.10"
  plc_type: "s7_1500"
  scan_interval: 2

entities:
  - key: machine_running
    name: "Machine Running"
    platform: binary_sensor
    db: 1
    byte: 0
    bit: 0
    data_type: bool
    device_class: running

  - key: actual_speed
    name: "Actual Speed"
    platform: sensor
    db: 1
    byte: 2
    data_type: real
    unit: "m/min"
    state_class: measurement
```

The connection parameters that the integration actually uses come from the
config flow. The `plc` block in the YAML is optional and only kept for
documentation / standalone validation.

### Memory areas

Each tag has an `area` (default `db`). The byte offset is relative to that area.

| `area`   | S7 area | Example address         | `db` used? |
|----------|---------|-------------------------|------------|
| `db`     | DB      | `DB10.DBX0.0`, `DB10.DBD2` | yes (required) |
| `input`  | I / E   | `I0.0` (byte 0, bit 0)  | no |
| `output` | Q / A   | `Q0.0` (byte 0, bit 0)  | no |
| `memory` | M       | `M10.0`, `MD100`        | no |

Reads are grouped per `(area, db)`, so inputs, outputs, merkers and each DB are
each read in their own grouped PLC call. Writing to **outputs** physically
actuates the PLC outputs — use with care.

### Supported data types

| `data_type` | Size  | Description                  |
|-------------|-------|------------------------------|
| `bool`      | 1 bit | `byte` + `bit` (0–7)         |
| `byte`      | 1 B   | unsigned 8-bit               |
| `int`       | 2 B   | signed 16-bit                |
| `uint`      | 2 B   | unsigned 16-bit              |
| `dint`      | 4 B   | signed 32-bit                |
| `real`      | 4 B   | 32-bit IEEE-754 float        |

Optional per-entity numeric post-processing: `scale` (multiply) and `offset`
(add), applied in that order on read and inverted on write. `unit`,
`device_class`, `state_class` and `icon` are passed through to Home Assistant.

### Write entities

| Platform | Data type        | Behaviour                                            |
|----------|------------------|------------------------------------------------------|
| `switch` | `bool`           | Toggles a single bit (read-modify-write of the byte).|
| `number` | numeric          | Writes the value; supports `min`, `max`, `step`, `mode` (`auto`/`box`/`slider`). |
| `button` | `bool` / numeric | Writes `press_value` on press (defaults to `True` for `bool`). Stateless — not polled. |

```yaml
  - key: enable_command
    name: "Enable Command"
    platform: switch
    db: 10
    byte: 12
    bit: 0
    data_type: bool

  - key: speed_setpoint
    name: "Speed Setpoint"
    platform: number
    db: 10
    byte: 14
    data_type: real
    unit: "m/min"
    min: 0
    max: 100
    step: 0.5
    mode: box

  - key: reset_command
    name: "Reset Command"
    platform: button
    db: 10
    byte: 18
    bit: 0
    data_type: bool
    press_value: true
```

### Testing writes from the command line

A standalone script exercises the same write path the HA entities use, with an
explicit (never defaulted) target address and a read-back check:

```bash
# bool bit -> True   (e.g. a Test_Write_Bool tag at DB10.DBX10.0)
python tools/live_write.py --host 192.168.84.12 --type bool --db 10 --byte 10 --bit 0 --value true
# real value         (e.g. a Test_Write_Real tag at DB10.DBD12)
python tools/live_write.py --host 192.168.84.12 --type real --db 10 --byte 12 --value 42.5
```

The script reads the target before and after the write and confirms the value,
so it is safe to run repeatedly against a dedicated test DB.

## MVP test DB

| Address     | Type   | Tag               |
|-------------|--------|-------------------|
| `DB1.DBX0.0`| bool   | `machine_running` |
| `DB1.DBX0.1`| bool   | `fault_active`    |
| `DB1.DBD2`  | real   | `actual_speed`    |
| `DB1.DBD6`  | dint   | `actual_count`    |

## Running the unit tests

The pure-logic tests (parser, writer, read planner, YAML loader) do **not**
require Home Assistant:

```bash
pip install pytest pyyaml
pytest
```

For the live scripts you also need `python-snap7` (and its native library):

```bash
pip install python-snap7
python tools/live_read.py examples/plc_tags.example.yaml
```

## Architecture

```
config entry ──▶ async_setup_entry
                   │
                   ├─ yaml_loader  → EntityDefinition[]   (validate YAML)
                   ├─ read_planner → ReadRequest[]        (group reads per DB)
                   └─ S7PlcCoordinator (DataUpdateCoordinator)
                        │  polls every scan_interval
                        ├─ S7PlcClient (single python-snap7 client)
                        │     connect / db_read / db_write / disconnect
                        ├─ parser  → values keyed by entity key (read)
                        ├─ writer  → bytes for db_write (write)
                        ├─ data cache ◀── sensor / binary_sensor / switch / number
                        └─ async_write_* ◀── switch / number / button
```

Read entities never call the PLC directly — they only read `coordinator.data`.
Write entities call `coordinator.async_write_*`, which serializes the value,
writes it in the executor and then requests a refresh. Bool writes use a
read-modify-write of the target byte so neighbouring bits are preserved.
Buttons are stateless and are excluded from the read plan.

## Roadmap

- Reconfigure flow for editing connection / scan interval without re-adding.
- Editing an existing tag (currently remove + re-add).
- `suggested_display_precision` to round floats in the UI.
- Optimized-DB support.
- HACS submission.
