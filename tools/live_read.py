"""Standalone live PLC read test (no Home Assistant required).

Reuses the integration's plc_client, read_planner and parser to connect to a
real PLC, perform the grouped DB reads and print the parsed entity values.

Usage:
    python tools/live_read.py [path/to/tags.yaml] [--loop SECONDS]

Defaults to examples/plc_tags.example.yaml.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

# Make the custom_components package importable when run from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.s7_plc.const import PLC_TYPE_TO_RACK_SLOT
from custom_components.s7_plc.models import PlcConfig
from custom_components.s7_plc.parser import parse_value
from custom_components.s7_plc.plc_client import PlcConnectionError, S7PlcClient
from custom_components.s7_plc.read_planner import plan_reads
from custom_components.s7_plc.yaml_loader import load_definition


def build_config(defn) -> PlcConfig:
    """Build a PlcConfig from the YAML 'plc' block."""
    if defn.plc is None:
        raise SystemExit("YAML is missing a 'plc' block (needed for standalone test).")
    return defn.plc


def read_once(client: S7PlcClient, entities, plan) -> dict[str, object]:
    """Perform one grouped read cycle and return parsed values."""
    buffers = {req: bytes(client.db_read(req.db, req.start, req.size)) for req in plan}
    values: dict[str, object] = {}
    for ent in entities:
        req = next(
            r for r in plan if r.db == ent.db and r.start <= ent.byte < r.end
        )
        rel = ent.byte - req.start
        values[ent.key] = parse_value(buffers[req], ent.data_type, rel, ent.bit)
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Live S7 PLC read test")
    parser.add_argument("yaml", nargs="?", default="examples/plc_tags.example.yaml")
    parser.add_argument("--loop", type=float, default=0, help="repeat every N seconds")
    args = parser.parse_args()

    defn = load_definition(os.getcwd(), args.yaml)
    config = build_config(defn)
    plan = plan_reads(defn.entities)

    rack, slot = PLC_TYPE_TO_RACK_SLOT[config.plc_type]
    print(f"PLC {config.name} @ {config.host}:{config.port}  "
          f"type={config.plc_type} rack={rack} slot={slot}")
    print("Read plan:")
    for req in plan:
        print(f"  DB{req.db}  bytes {req.start}..{req.end - 1}  ({req.size} bytes)")
    print()

    client = S7PlcClient(config)
    try:
        client.connect()
    except PlcConnectionError as err:
        print(f"CONNECT FAILED: {err}")
        return 1
    print(f"Connected: {client.is_connected}\n")

    try:
        while True:
            try:
                values = read_once(client, defn.entities, plan)
            except PlcConnectionError as err:
                print(f"READ FAILED: {err}")
                return 2
            for ent in defn.entities:
                val = values[ent.key]
                unit = f" {ent.unit}" if ent.unit else ""
                print(f"  {ent.key:<18} = {val}{unit}  "
                      f"[DB{ent.db}.{ent.byte}{('.' + str(ent.bit)) if ent.data_type == 'bool' else ''} "
                      f"{ent.data_type}]")
            if args.loop <= 0:
                break
            print("-" * 50)
            time.sleep(args.loop)
    finally:
        client.disconnect()
        print("\nDisconnected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
