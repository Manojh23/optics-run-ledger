# Optics Run Ledger

A local data platform for a simulated optics fabrication lab. Trace a device serial back to its material lot, substrate, print run, and design and recipe revisions. If a material lot is flagged, see which devices it touches, which have failed metrology, and which have no measurement yet. All data and tolerance values in the demo are synthetic.

## Try it

Requires Docker with Compose and Python 3.12 for the instrument SDK demo.

```sh
docker compose up --build -d
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m demo.seed
```

Open the [operator UI](http://localhost:8000), trace `LENS-102`, then select **Review this material lot** and review `LOT-R42`. The sample has two passing, one failing and one unmeasured device. The built-in [REST API docs](http://localhost:8000/docs) and the [Grafana dashboard](http://localhost:3000/d/optics-quality) are also available locally. Grafana uses the container's default local login (`admin` / `admin`, change when prompted). The Compose app binds to loopback and is meant to demonstrate the workflow with fictional data. It does not implement production user sign-in or deploy to AWS.

The React workspace has separate forms for substrates and print runs. The run form registers its devices in the same transaction. The Python SDK registers fabrication via REST and reads a CSV file produced by a mock metrology tool. Re-running the demo prints the original import ID with `replayed: true`.

## Design choices

| Concern | Implementation |
| --- | --- |
| Device provenance | Foreign keys connect material, substrates, runs, devices and readings; immutable run metadata records design and recipe revisions. |
| Repeat instrument exports | A unique instrument/export key and a SHA-256 hash of normalized readings make retries safe. Reusing a key with different content returns HTTP 409. Bad device references roll back the entire batch. |
| Late measurements | The latest result uses measurement time rather than upload time; tied measurement times use the last inserted ID. The device endpoint keeps the latest 100 readings with instrument and export evidence. |
| Lot impact review | A PostgreSQL view joins the latest result to fabrication lineage. Both React and Grafana show unmeasured devices as a separate status. The API reads totals and device rows from one transaction snapshot. |
| Schema rollout | The first Alembic migration creates fabrication lineage. The second adds imports, raw readings and the quality view without rewriting fabrication records. Downgrading the second migration deletes measurement history; use it on disposable data only. |

Main entry points: `ledger/api.py`, `ledger/sdk.py`, `migrations/versions/`, and `web/src/main.tsx`. Grafana uses its own read-only PostgreSQL login.

## Development checks

Use a fresh PostgreSQL database. With `DATABASE_URL` pointing to it:

```sh
alembic upgrade 0001_lineage
alembic upgrade head
python -m unittest discover -s tests -v
(cd web && npm ci && npm run build)
```

The integration tests truncate the configured database before each test. GitHub Actions is configured to run them against a disposable PostgreSQL service. Tests cover serial-to-substrate traceability, missing metrology, conflicting and concurrent replays, transaction rollback, and late measurements. No external instruments or infrastructure are used.
