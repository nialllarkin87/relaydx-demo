# pipeline.py
import yaml
from ingest.csv_parser import CSVParser
from ingest.hl7_parser import HL7Parser
from normalize.transformer import normalize_result
from output.fhir_builder import build_fhir_resources
import requests
import logging

logger = logging.getLogger(__name__)

def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)

class FileConnector:
    def __init__(self, cfg):
        self.path = cfg["settings"]["path"]

    def read(self):
        # choose parser by file extension
        if self.path.endswith(".json"):
            import json
            with open(self.path) as f:
                return json.load(f)["labResults"]
        elif self.path.endswith(".csv"):
            return CSVParser(self.path).parse()
        elif self.path.endswith(".hl7"):
            return HL7Parser(self.path).parse()
        else:
            raise ValueError("Unsupported file type")

class Parser:
    def __init__(self, records, stage_cfg):
        self.records = records
        self.record_path = stage_cfg["settings"]["recordPath"]

    def run(self):
        # for JSON with $.labResults[*], simply pass through
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
        # stub: identity mapping
        return self.normalized

class FHIRTransformer:
    def __init__(self, mapped):
        self.mapped = mapped

    def run(self):
        # build a list of FHIR resources (DiagnosticReport + Observations)
        all_resources = []
        for record in self.mapped:
            resources = build_fhir_resources(record)
            all_resources.extend(resources)
        return all_resources

class FHIRConnector:
    def __init__(self, cfg):
        self.base_url = cfg["baseUrl"].rstrip("/")
        self.headers = cfg.get("headers", {})

    def send(self, resources):
        for resource in resources:
            rtype = resource["resourceType"]
            url = f"{self.base_url}/{rtype}"
            resp = requests.post(url, json=resource, headers=self.headers)
            if resp.status_code not in (200, 201):
                logger.error(f"Failed to POST {rtype}: {resp.status_code} {resp.text}")
                resp.raise_for_status()
            else:
                logger.info(f"POST {rtype} → {resp.status_code}")

def run_pipeline(config_path: str):
    cfg = load_yaml(config_path)

    # Inbound – only support the first file source for now
    file_cfg = cfg["connectors"]["inbound"][0]
    records = FileConnector(file_cfg).read()
    logger.info(f"Ingested {len(records)} records")

    # Stages (assumes order parse → normalize → map → transform → send)
    parsed = Parser(records, cfg["stages"][0]).run()
    normalized = Normalizer(parsed).run()
    mapped = SmartMapper(normalized).run()
    fhir_resources = FHIRTransformer(mapped).run()

    # Outbound connector – again, first outbound FHIR
    fhir_cfg = cfg["connectors"]["outbound"][0]
    FHIRConnector(fhir_cfg).send(fhir_resources)
