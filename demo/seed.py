import argparse
from pathlib import Path

import httpx

from ledger.schemas import Run, Substrate
from ledger.sdk import LedgerClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    with LedgerClient(args.url) as lab:
        for code, devices in [("SUB-1", [101, 102]), ("SUB-2", [103, 104])]:
            substrate = Substrate(code=code, material_lot="LOT-R42", material="Synthetic resin")
            run = Run(code=f"RUN-{code[-1]}", substrate_code=code, design_revision="LENS-R7",
                      recipe_revision="PRINT-R3", printer="DEMO-PRINTER", printed_at="2026-11-16T11:30:00Z",
                      devices=[{"serial": f"LENS-{n}", "position": f"X{i}"} for i, n in enumerate(devices, 1)])
            for method, item in [(lab.register_substrate, substrate), (lab.register_run, run)]:
                try:
                    method(item)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code != 409:
                        raise
        fixture = Path(__file__).with_name("readings.csv")
        print("Import:", lab.import_csv(fixture, "DEMO-PROFILER", "EXPORT-01"))
        print("Replay:", lab.import_csv(fixture, "DEMO-PROFILER", "EXPORT-01"))
        print("Trace:", lab.lineage("LENS-102")["device"])
        print("Lot totals:", lab.impact("LOT-R42")["totals"])


if __name__ == "__main__":
    main()
