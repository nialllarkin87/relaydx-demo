from fastapi import FastAPI, UploadFile, File, HTTPException
from ingest.hl7_parser import parse_hl7
from ingest.csv_parser import parse_csv
from normalize.transformer import normalize_result
from output.fhir_builder import build_fhir_output

from db import init_db, get_session
from models import LabResult
from datetime import datetime

app = FastAPI()

# Initialize DB and tables at startup
@app.on_event("startup")
def on_startup():
    init_db()

def save_result(norm: dict):
    # Convert collection_date string to datetime
    cd = norm["collection_date"]
    # assume ISO or basic: try parsing
    # normalize collection_date into a Python datetime
    def parse_datetime(cd: str) -> datetime:
        # 1) Strip Zulu “Z” and try ISO8601
        if cd.endswith("Z"):
            try:
                return datetime.fromisoformat(cd[:-1])
            except ValueError:
                pass
        # 2) Try plain fromisoformat (YYYY-MM-DDTHH:MM:SS)
        try:
            return datetime.fromisoformat(cd)
        except ValueError:
            pass
        # 3) Fallback to compact format YYYYMMDDHHMMSS
        try:
            return datetime.strptime(cd, "%Y%m%d%H%M%S")
        except ValueError:
            pass
        # 4) Give up
        raise ValueError(f"Unrecognized date format: {cd}")

    dt = parse_datetime(norm["collection_date"])
    lr = LabResult(
        patient_id=norm["patient_id"],
        test_code=norm["test_code"],
        test_name=norm["test_name"],
        result_value=norm["result_value"],
        units=norm["units"],
        reference_range=norm["reference_range"],
        collection_date=dt,
        lab_name=norm["lab_name"],
        status=norm["status"]
    )
    with get_session() as session:
        session.add(lr)
        session.commit()
        session.refresh(lr)
        return lr

@app.post("/ingest/hl7")
async def ingest_hl7(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        parsed = parse_hl7(raw.decode())
    except Exception as e:
        raise HTTPException(400, f"HL7 parsing error: {e}")
    norm = normalize_result(parsed)
    record = save_result(norm)
    return {"saved_id": record.id, "normalized": norm}

@app.post("/ingest/csv")
async def ingest_csv(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        csv_str = raw.decode()
        raws = parse_csv(csv_str)
    except Exception as e:
        raise HTTPException(400, f"CSV parsing error: {e}")
    saved = []
    for r in raws:
        norm = normalize_result(r)
        rec = save_result(norm)
        saved.append({"id": rec.id, **norm})
    return {"saved": saved}

@app.get("/lab-result/{id}")
def get_lab_result(id: int, format: str = "json"):
    with get_session() as session:
        rec = session.get(LabResult, id)
    if not rec:
        raise HTTPException(404, "Result not found")
    norm = rec.dict()
    if format == "fhir":
        return build_fhir_output(norm)
    return norm

import fire
from pipeline import run_pipeline

def main():
    fire.Fire({"run_pipeline": run_pipeline})

if __name__ == "__main__":
    main()