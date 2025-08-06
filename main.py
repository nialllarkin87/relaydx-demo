# main.py
from fastapi import FastAPI
from pipeline import run_pipeline
import uvicorn
import fire
import logging
from db import get_session, init_db
from models import LabResult
from datetime import datetime

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
init_db()

# Initialize FastAPI app
app = FastAPI()

@app.get("/")
def read_root():
    return {"RelayDX": "Pipeline is live. POST to /run-pipeline to execute."}

@app.post("/run-pipeline")
def trigger_pipeline():
    config_path = "lab_pipeline.yaml"
    logger.info(f"Triggering pipeline with config: {config_path}")
    run_pipeline(config_path)
    return {"status": "Pipeline execution completed."}

def save_result(normalized_result):
    """
    Save normalized result to database
    Used by the Streamlit UI
    """
    try:
        with get_session() as session:
            # Convert normalized result to LabResult model
            lab_result = LabResult(
                patient_id=normalized_result.get("patient", {}).get("id", "UNKNOWN"),
                test_code=normalized_result.get("test", {}).get("code", "UNKNOWN"),
                test_name=normalized_result.get("test", {}).get("name", "Lab Test"),
                result_value=float(normalized_result.get("result", {}).get("value", 0)),
                units=normalized_result.get("result", {}).get("unit", ""),
                reference_range="Normal",  # Default value
                collection_date=datetime.now(),  # Use current time if not provided
                lab_name="Unknown Lab",  # Default value
                status="final"
            )
            
            session.add(lab_result)
            session.commit()
            session.refresh(lab_result)
            logger.info(f"Saved lab result with ID: {lab_result.id}")
            return lab_result
            
    except Exception as e:
        logger.error(f"Failed to save result: {e}")
        # Return a minimal result object to prevent UI crashes
        return type('LabResult', (), {'id': 'ERROR'})()

# CLI entrypoint using python-fire
def cli():
    fire.Fire({
        "run_pipeline": run_pipeline
    })

# Entry point for CLI or server
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)