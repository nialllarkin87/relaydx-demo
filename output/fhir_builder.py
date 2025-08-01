from fhir.resources.observation import Observation
from fhir.resources.diagnosticreport import DiagnosticReport

def build_fhir_output(data):
    observation = Observation.construct(
        status="final",
        code={"text": data["test_name"]},
        valueQuantity={"value": float(data["result_value"]), "unit": data["units"]}
    )
    report = DiagnosticReport.construct(
        status="final",
        result=[{"reference": f"Observation/{observation.id}"}],
        code={"text": data["test_name"]}
    )
    return {"diagnostic_report": report.dict(), "observation": observation.dict()}
