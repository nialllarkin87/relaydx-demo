def normalize_result(raw):
    TEST_CODE_MAPPING = {
        "UA123": "UA123"
    }
    return {
        "patient_id": raw["patient_id"],
        "test_code": TEST_CODE_MAPPING.get(raw["vendor_code"], raw["vendor_code"]),
        "test_name": raw["test_name"],
        "result_value": float(raw["value"]),
        "units": raw["units"],
        "reference_range": "<30",
        "collection_date": raw["collection_date"],
        "lab_name": raw["lab_name"],
        "status": "final"
    }
