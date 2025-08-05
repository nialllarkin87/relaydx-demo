# pipeline.py
import yaml
import json
import requests
import logging

from ingest.csv_parser import parse_csv
from ingest.hl7_parser import parse_hl7
from normalize.transformer import normalize_result
from output.fhir_builder import build_fhir_resources

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
                # assume your JSON has a top‐level "labResults" array
                return json.load(f)["labResults"]

        with open(self.path) as f:
            content = f.read()

        if self.path.endswith(".csv"):
            # parse_csv returns a list of dicts
            return parse_csv(content)

        elif self.path.endswith(".hl7"):
            # parse_hl7 returns a single dict, so wrap in a list
            return [parse_hl7(content)]

        else:
            raise ValueError(f"Unsupported file type: {self.path}")

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
