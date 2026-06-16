"""Standalone live PLC WRITE test (no Home Assistant required).

SAFETY: this writes to a real PLC. There are no default addresses — you must
pass the exact target explicitly. Pick an address you KNOW is safe (a spare
test byte / DB), never a live machine control.

Reuses the integration's plc_client / writer so it exercises the same code
path the Home Assistant switch / number / button entities use.

Examples:
    # Set DB10.DBX12.0 (a bool bit) to True
    python tools/live_write.py --host 192.168.84.12 --type bool --db 10 --byte 12 --bit 0 --value true

    # Write a real to DB10.DBD14
    python tools/live_write.py --host 192.168.84.12 --type real --db 10 --byte 14 --value 42.5
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.s7_plc.const import PLC_TYPE_TO_RACK_SLOT
from custom_components.s7_plc.models import PlcConfig
from custom_components.s7_plc.parser import parse_value
from custom_components.s7_plc.plc_client import PlcConnectionError, S7PlcClient


def _parse_value_arg(data_type: str, raw: str) -> object:
    if data_type == "bool":
        return raw.strip().lower() in ("1", "true", "on", "yes")
    if data_type == "real":
        return float(raw)
    return int(raw)


def main() -> int:
    p = argparse.ArgumentParser(description="Live S7 PLC write test")
    p.add_argument("--host", required=True)
    p.add_argument("--plc-type", default="s7_1200", choices=list(PLC_TYPE_TO_RACK_SLOT))
    p.add_argument("--port", type=int, default=102)
    p.add_argument(
        "--type", required=True, dest="data_type",
        choices=["bool", "byte", "int", "uint", "dint", "real"],
    )
    p.add_argument(
        "--area", default="db", choices=["db", "input", "output", "memory"]
    )
    p.add_argument("--db", type=int, default=0)
    p.add_argument("--byte", type=int, required=True)
    p.add_argument("--bit", type=int, default=0)
    p.add_argument("--value", required=True)
    args = p.parse_args()

    value = _parse_value_arg(args.data_type, args.value)
    rack, slot = PLC_TYPE_TO_RACK_SLOT[args.plc_type]
    size = 1 if args.data_type in ("bool", "byte") else (2 if args.data_type in ("int", "uint") else 4)

    config = PlcConfig(
        name="write-test", host=args.host, plc_type=args.plc_type,
        rack=rack, slot=slot, scan_interval=1, port=args.port,
    )
    if args.area == "db":
        addr = f"DB{args.db}.{args.byte}"
    else:
        addr = f"{args.area}:{args.byte}"
    if args.data_type == "bool":
        addr += f".{args.bit}"
    print(f"Target {addr} ({args.data_type}) on {args.host}:{args.port}")
    print(f"About to write: {value!r}\n")

    client = S7PlcClient(config)
    try:
        client.connect()
    except PlcConnectionError as err:
        print(f"CONNECT FAILED: {err}")
        return 1

    try:
        before = bytes(client.read(args.area, args.db, args.byte, size))
        print(f"  before: {parse_value(before, args.data_type, 0, args.bit)}  raw={before.hex()}")

        if args.data_type == "bool":
            client.write_bit(args.area, args.db, args.byte, args.bit, bool(value))
        else:
            from custom_components.s7_plc.writer import serialize
            client.write(args.area, args.db, args.byte, serialize(args.data_type, value))

        after = bytes(client.read(args.area, args.db, args.byte, size))
        print(f"  after:  {parse_value(after, args.data_type, 0, args.bit)}  raw={after.hex()}")

        ok = parse_value(after, args.data_type, 0, args.bit) == value or (
            args.data_type == "real"
            and abs(parse_value(after, args.data_type, 0, args.bit) - float(value)) < 1e-3
        )
        print("\nRESULT:", "OK — value confirmed" if ok else "MISMATCH — check write protection / address")
        return 0 if ok else 3
    except PlcConnectionError as err:
        print(f"WRITE FAILED: {err}")
        return 2
    finally:
        client.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
