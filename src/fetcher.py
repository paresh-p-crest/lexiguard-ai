import json

import storage

HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "OPTIONS,GET"
}


def lambda_handler(event, context):
    try:
        cases = []
        for row in storage.list_cases():
            cases.append({
                "id": str(row.get("id")),
                "client": row.get("client_name"),
                "type": row.get("case_type"),
                "address": row.get("address"),
                # DynamoDB may return Decimal for number fields; always stringify safely.
                "fee": str(row.get("fee")) if row.get("fee") is not None else None,
                "date": str(row.get("created_at")) if row.get("created_at") is not None else None,
            })

        return {
            "statusCode": 200,
            "headers": HEADERS,
            "body": json.dumps(cases, default=str)
        }
    except Exception as e:
        print(f"Fetcher error: {str(e)}")
        return {"statusCode": 500, "headers": HEADERS, "body": json.dumps({"error": str(e)})}
