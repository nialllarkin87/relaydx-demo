# ingest/csv_parser.py
import pandas as pd
from typing import List, Dict

def parse_csv(content: str) -> List[Dict]:
    """
    content: full CSV text
    returns: list of raw dicts matching your canonical model keys
    """
    df = pd.read_csv(pd.compat.StringIO(content))
    records = []
    for _, row in df.iterrows():
        records.append({
            "patient_id": row["Patient_ID"],
            "test_code": row["Test_LOINC_Code"],
            "result_value": row["Result"],
            "unit": row["Units"],
            "timestamp": row["Result_Date"],
        })
    return records
