# normalize/transformer.py
from typing import Dict

def normalize_result(raw: Dict) -> Dict:
    """
    Convert raw parser output into your canonical model fields.
    """
    return {
        "patient": {"id": raw["patient_id"]},
        "test":    {"code": raw["test_code"]},
        "result":  {
            "value": raw["result_value"],
            "unit":  raw["unit"]
        },
        "effectiveDateTime": raw["timestamp"]
    }
