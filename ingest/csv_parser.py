import pandas as pd
import io

def parse_csv(csv_content: str):
    """
    Parse CSV lab results into a list of raw dictionaries.
    Expected columns: patient_id, test_code, test_name, value, units, collection_date, lab_name
    """
    df = pd.read_csv(io.StringIO(csv_content))
    results = []
    for _, row in df.iterrows():
        raw = {
            "patient_id": str(row.get("patient_id")),
            "vendor_code": row.get("test_code"),
            "test_name": row.get("test_name"),
            "value": row.get("value"),
            "units": row.get("units"),
            "collection_date": row.get("collection_date"),
            "lab_name": row.get("lab_name", "UNKNOWN")
        }
        results.append(raw)
    return results
