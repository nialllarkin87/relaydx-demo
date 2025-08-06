# pipeline.py
import yaml, json, requests, logging

from ingest.csv_parser import parse_csv
from ingest.hl7_parser import parse_hl7
from normalize.transformer import normalize_result
from output.fhir_builder import build_fhir_output

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)

class FileConnector:
    def __init__(self, cfg):
        self.path = cfg["settings"]["path"]

    def read(self):
        if self.path.endswith(".json"):
            with open(self.path) as f:
                return json.load(f)["labResults"]
        with open(self.path) as f:
            content = f.read()
        if self.path.endswith(".csv"):
            return parse_csv(content)
        elif self.path.endswith(".hl7"):
            return [parse_hl7(content)]
        else:
            raise ValueError(f"Unsupported file type: {self.path}")

class Parser:
    def __init__(self, records, stage_cfg):
        self.records = records

    def run(self):
        return self.records

class Normalizer:
    def __init__(self, parsed):
        self.parsed = parsed

    def run(self):
        return [normalize_result(r) for r in self.parsed]

class SmartMapper:
    def __init__(self, normalized):
        self.normalized = normalized

    def run(self):
        # No-op for POC
        return self.normalized

class FHIRTransformer:
    def __init__(self, mapped):
        self.mapped = mapped

    def run(self):
        all_resources = []
        for rec in self.mapped:
            bundle = build_fhir_output(rec)
            # append Observation first, then DiagnosticReport
            all_resources.append(bundle["observation"])
            all_resources.append(bundle["diagnostic_report"])
        return all_resources

class FHIRConnector:
    def __init__(self, cfg):
        self.base_url = cfg["baseUrl"].rstrip("/")
        self.headers  = cfg.get("headers", {})

    def send(self, resources):
        for resource in resources:
            rtype = resource["resourceType"]
            url   = f"{self.base_url}/{rtype}"
            resp  = requests.post(url, json=resource, headers=self.headers)
            if resp.status_code not in (200, 201):
                logger.error(f"Failed to POST {rtype}: {resp.status_code} {resp.text}")
                resp.raise_for_status()
            else:
                logger.info(f"POST {rtype} → {resp.status_code}")

def run_pipeline(config_path: str):
    logger.info(f"Loading pipeline config from {config_path}")
    cfg = load_yaml(config_path)

    # Ingest
    file_cfg = cfg["connectors"]["inbound"][0]
    records  = FileConnector(file_cfg).read()
    logger.info(f"Ingested {len(records)} records")

    # Stages
    parsed     = Parser(records, cfg["stages"][0]).run()
    normalized = Normalizer(parsed).run()
    mapped     = SmartMapper(normalized).run()
    resources  = FHIRTransformer(mapped).run()

    # Send
    fhir_cfg = cfg["connectors"]["outbound"][0]
    FHIRConnector(fhir_cfg).send(resources)
    logger.info("Pipeline run complete.")
