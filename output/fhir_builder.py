from fhir.resources.observation import Observation
from fhir.resources.diagnosticreport import DiagnosticReport
from typing import Dict
import uuid

def build_fhir_output(record: Dict) -> Dict:
    """
    Returns a dict with two keys:
      - "observation": FHIR Observation dict
      - "diagnostic_report": FHIR DiagnosticReport dict
    """
    obs_id = str(uuid.uuid4())
    dr_id  = str(uuid.uuid4())

    observation = Observation.construct(
        id=obs_id,
        status="final",
        category=[{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                               "code": "laboratory"}]}],
        code={"coding": [{"system": "http://loinc.org",
                          "code": record["test"]["code"]}]},
        subject={"reference": f"Patient/{record['patient']['id']}"},
        effectiveDateTime=record["effectiveDateTime"],
        valueQuantity={
            "value": record["result"]["value"],
            "unit": record["result"]["unit"],
            "system": "http://unitsofmeasure.org",
            "code": record["result"]["unit"]
        }
    )

    diagnostic_report = DiagnosticReport.construct(
        id=dr_id,
        status="final",
        category=[{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                               "code": "laboratory"}]}],
        code={"coding": [{"system": "http://loinc.org",
                          "code": record["test"]["code"]}]},
        subject={"reference": f"Patient/{record['patient']['id']}"},
        effectiveDateTime=record["effectiveDateTime"],
        result=[{"reference": f"Observation/{obs_id}"}]
    )

    return {
        "observation": observation.dict(),
        "diagnostic_report": diagnostic_report.dict()
    }
