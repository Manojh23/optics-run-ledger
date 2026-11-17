"""Small HTTP client for printing, metrology, and analysis scripts."""
import csv
from pathlib import Path

import httpx

from .schemas import Batch, Run, Substrate


class LedgerClient:
    def __init__(self, base_url: str):
        self.client = httpx.Client(base_url=base_url, timeout=12, trust_env=False)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.client.close()

    def _request(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    def register_substrate(self, item: Substrate):
        return self._request("POST", "/api/substrates", json=item.model_dump(mode="json"))

    def register_run(self, item: Run):
        return self._request("POST", "/api/runs", json=item.model_dump(mode="json"))

    def import_csv(self, file: Path, instrument: str, external_id: str):
        required = {"serial", "measured_at", "value_nm", "spec_max_nm"}
        with file.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if set(reader.fieldnames or []) != required or len(reader.fieldnames or []) != len(required):
                raise ValueError("CSV must have serial, measured_at, value_nm, and spec_max_nm columns.")
            rows = []
            for row in reader:
                if len(rows) == 500:
                    raise ValueError("At most 500 readings per export.")
                rows.append(row)
        batch = Batch.model_validate(dict(instrument=instrument, external_id=external_id, readings=rows))
        return self._request("POST", "/api/measurements/import", json=batch.model_dump(mode="json"))

    def lineage(self, serial: str):
        return self._request("GET", f"/api/devices/{serial}")

    def impact(self, lot: str, status: str | None = None):
        return self._request("GET", f"/api/lots/{lot}/impact", **({"params": {"status": status}} if status else {}))
