import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from fastapi.testclient import TestClient
from sqlalchemy import text

from ledger.api import app
from ledger.db import engine


class LedgerTests(unittest.TestCase):
    def setUp(self):
        # Use a dedicated test database. Never point this suite at an existing ledger.
        with engine.begin() as c:
            c.execute(text("TRUNCATE measurements, imports, devices, print_runs, substrates RESTART IDENTITY"))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.assertEqual(self.client.post("/api/substrates", json={
            "code": "SUB-A", "material_lot": "LOT-A", "material": "Demo resin",
        }).status_code, 201)
        self.assertEqual(self.client.post("/api/runs", json={
            "code":"RUN-A", "substrate_code":"SUB-A", "design_revision":"D3", "recipe_revision":"P2",
            "printer":"PR-1", "printed_at":"2026-11-16T11:00:00Z",
            "devices":[{"serial":"D-1","position":"X1"},{"serial":"D-2","position":"X2"},
                       {"serial":"D-3","position":"X3"}],
        }).status_code, 201)

    def sample(self):
        return {"instrument":"TOOL-A", "external_id":"EXPORT-1", "readings":[
            {"serial":"D-1","measured_at":"2026-11-16T13:00:00Z","value_nm":18,"spec_max_nm":15},
            {"serial":"D-2","measured_at":"2026-11-16T13:00:00Z","value_nm":12,"spec_max_nm":15},
        ]}

    def upload(self, batch):
        return self.client.post("/api/measurements/import", json=batch)

    def test_trace_and_lot_counts_include_missing_evidence(self):
        self.assertEqual(self.upload(self.sample()).status_code, 200)
        trace = self.client.get("/api/devices/D-1").json()
        self.assertEqual([trace["device"][key] for key in ("substrate_code","run_code","design_revision","status")],
                         ["SUB-A","RUN-A","D3","fail"])
        self.assertEqual(trace["history"][0]["external_id"], "EXPORT-1")
        impact = self.client.get("/api/lots/LOT-A/impact", params={"status":"unmeasured"}).json()
        self.assertEqual(impact["totals"], {"fail":1, "pass":1, "unmeasured":1})
        self.assertEqual([r["serial"] for r in impact["devices"]], ["D-3"])

    def test_reordered_retry_matches_and_changed_payload_conflicts(self):
        batch = self.sample()
        first = self.upload(batch).json()
        batch["readings"].reverse()
        batch["readings"][0]["measured_at"] = "2026-11-16T08:00:00-05:00"
        replay = self.upload(batch).json()
        self.assertTrue(replay["replayed"])
        self.assertEqual(first["id"], replay["id"])
        batch["readings"][0]["value_nm"] = 22
        self.assertEqual(self.upload(batch).status_code, 409)
        self.assertEqual(len(self.client.get("/api/devices/D-2").json()["history"]), 1)

    def test_invalid_serial_rolls_back_every_reading_and_receipt(self):
        batch = self.sample()
        batch["readings"][1]["serial"] = "UNKNOWN"
        self.assertEqual(self.upload(batch).status_code, 422)
        self.assertEqual(self.client.get("/api/devices/D-1").json()["history"], [])
        valid = self.upload(self.sample()).json()
        self.assertFalse(valid["replayed"])

    def test_late_upload_does_not_replace_newer_quality_result(self):
        batch = self.sample()
        self.assertEqual(self.upload(batch).status_code, 200)
        late = deepcopy(batch)
        late["external_id"] = "LATE"
        late["readings"] = [late["readings"][0] | {"value_nm":3,"measured_at":"2026-11-16T12:00:00Z"}]
        self.assertEqual(self.upload(late).status_code, 200)
        self.assertEqual(self.client.get("/api/devices/D-1").json()["device"]["status"], "fail")

    def test_concurrent_retries_commit_once(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(self.upload, [self.sample(), self.sample()]))
        self.assertEqual([r.status_code for r in replies], [200,200])
        a,b = [r.json() for r in replies]
        self.assertEqual(a["id"], b["id"])
        self.assertEqual({a["replayed"], b["replayed"]}, {False, True})


if __name__ == "__main__":
    unittest.main()
