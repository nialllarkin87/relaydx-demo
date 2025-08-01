def parse_hl7(hl7_str):
    lines = hl7_str.strip().split('\n')
    result = {
        "patient_id": "UNKNOWN",
        "test_name": "",
        "vendor_code": "",
        "value": "",
        "units": "",
        "collection_date": "",
        "lab_name": "LGC",
        "status": "final"
    }

    for line in lines:
        fields = line.strip().split('|')
        if line.startswith("PID"):
            result["patient_id"] = fields[3]
        elif line.startswith("OBR"):
            result["collection_date"] = fields[7]
        elif line.startswith("OBX"):
            result["vendor_code"] = fields[3].split('^')[0]
            result["test_name"] = fields[3].split('^')[1]
            result["value"] = fields[5]
            result["units"] = fields[6]

    return result
