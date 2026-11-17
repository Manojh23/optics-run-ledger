import hashlib
import json
from datetime import timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .db import engine
from .schemas import Batch, Key, Run, Substrate

app = FastAPI(title="Optics Run Ledger", version="1.0.0")


@app.get("/api/health")
def health():
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    return {"status": "ok"}


def integrity(exc):
    if exc.orig.sqlstate == "23503":
        return HTTPException(422, "A referenced substrate or device does not exist.")
    if exc.orig.sqlstate == "23505":
        return HTTPException(409, "An identifier or print position is already registered.")
    raise exc


@app.post("/api/substrates", status_code=201)
def create_substrate(item: Substrate):
    try:
        with engine.begin() as c:
            c.execute(text("INSERT INTO substrates VALUES (:code, :material_lot, :material)"), item.model_dump())
    except IntegrityError as exc:
        raise integrity(exc) from None
    return item


@app.post("/api/runs", status_code=201)
def create_run(run: Run):
    try:
        with engine.begin() as c:
            c.execute(text("""INSERT INTO print_runs
                 (code,substrate_code,design_revision,recipe_revision,printer,printed_at)
                 VALUES (:code,:substrate_code,:design_revision,:recipe_revision,:printer,:printed_at)"""),
                      run.model_dump(exclude={"devices"}))
            c.execute(text("INSERT INTO devices VALUES (:serial,:run_code,:position)"),
                      [d.model_dump() | {"run_code": run.code} for d in run.devices])
    except IntegrityError as exc:
        raise integrity(exc) from None
    return {"code": run.code, "devices": len(run.devices)}


@app.post("/api/measurements/import")
def ingest(batch: Batch):
    readings = [r.model_dump(mode="json") | {"measured_at": r.measured_at.astimezone(timezone.utc).isoformat()}
                for r in batch.readings]
    readings.sort(key=lambda r: (r["serial"], r["measured_at"]))
    digest = hashlib.sha256(json.dumps(readings, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    params = {"instrument": batch.instrument, "external": batch.external_id, "digest": digest}
    try:
        with engine.begin() as c:
            id_ = c.execute(text("""INSERT INTO imports(instrument,external_id,sha256)
                VALUES (:instrument,:external,:digest)
                ON CONFLICT (instrument,external_id) DO NOTHING RETURNING id"""), params).scalar_one_or_none()
            if id_ is None:
                row = c.execute(text("""SELECT id,sha256 FROM imports
                    WHERE instrument=:instrument AND external_id=:external"""), params).one()
                if row.sha256 != digest:
                    raise HTTPException(409, "This instrument export ID already has different readings.")
                return {"id": row.id, "accepted": len(readings), "replayed": True, "sha256": digest}
            c.execute(text("""INSERT INTO measurements(import_id,serial,measured_at,value_nm,spec_max_nm)
                VALUES (:id,:serial,:measured_at,:value_nm,:spec_max_nm)"""),
                      [r.model_dump() | {"id": id_} for r in batch.readings])
    except IntegrityError as exc:
        raise integrity(exc) from None
    return {"id": id_, "accepted": len(readings), "replayed": False, "sha256": digest}


@app.get("/api/devices/{serial}")
def lineage(serial: Key):
    with engine.connect() as conn:
        with conn.execution_options(isolation_level="REPEATABLE READ").begin():
            device = conn.execute(text("""SELECT q.*, d.position, s.material
                FROM device_quality q JOIN devices d USING(serial)
                JOIN substrates s ON s.code=q.substrate_code WHERE q.serial=:serial"""),
                                  {"serial": serial}).mappings().one_or_none()
            if device is None:
                raise HTTPException(404, "No device with that serial number.")
            history = conn.execute(text("""SELECT m.measured_at,m.value_nm,m.spec_max_nm,m.passed,
                i.instrument,i.external_id,i.sha256 FROM measurements m JOIN imports i ON i.id=m.import_id
                WHERE m.serial=:serial ORDER BY m.measured_at DESC,m.id DESC LIMIT 100"""),
                                   {"serial": serial}).mappings()
            return {"device": dict(device), "history": [dict(row) for row in history]}


@app.get("/api/lots/{lot}/impact")
def impact(lot: Key, status: Literal["pass", "fail", "unmeasured"] | None = None,
           offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    with engine.connect() as conn:
        with conn.execution_options(isolation_level="REPEATABLE READ").begin():
            counts = conn.execute(text("""SELECT status, count(*) AS n FROM device_quality
                  WHERE material_lot=:lot GROUP BY status"""), {"lot": lot}).mappings()
            totals = {"pass": 0, "fail": 0, "unmeasured": 0} | {r["status"]: r["n"] for r in counts}
            suffix = " AND status=:status" if status else ""
            rows = conn.execute(text("""SELECT * FROM device_quality WHERE material_lot=:lot""" + suffix +
                                     " ORDER BY serial LIMIT :limit OFFSET :offset"),
                                {"lot": lot, "status": status, "limit": limit, "offset": offset}).mappings()
            return {"lot": lot, "totals": totals, "devices": [dict(r) for r in rows]}


# The production image serves the compiled React app on the API's origin.
web_dist = Path(__file__).resolve().parents[1] / "web" / "dist"
if web_dist.is_dir():
    app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
