# main.py
from fastapi import FastAPI
from pipeline import run_pipeline
import uvicorn
import fire
import logging

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# CLI entrypoint using python-fire
def cli():
    fire.Fire({
        "run_pipeline": run_pipeline
    })

# Entry point for CLI or server
if __name__ == "__main__":
    cli()
    # Uncomment to run the API locally (for testing outside Render):
    # uvicorn.run(app, host="0.0.0.0", port=8000)
