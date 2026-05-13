import json
import os
import psycopg2

HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "OPTIONS,GET"
}

def lambda_handler(event, context):
    try:
        conn = psycopg2.connect(
            host=os.environ['DB_HOST'],
            database=os.environ['DB_NAME'],
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASS']
        )
        cur = conn.cursor()
        cur.execute("""
            SELECT id, client_name, case_type, address, fee, created_at
            FROM legal_cases
            ORDER BY created_at DESC
        """)
        
        rows = cur.fetchall()
        cases = []
        for r in rows:
            cases.append({
                "id": r[0],
                "client": r[1],
                "type": r[2],
                "address": r[3],
                "fee": r[4],
                "date": str(r[5])
            })
        
        cur.close()
        conn.close()

        return {
            "statusCode": 200,
            "headers": HEADERS,
            "body": json.dumps(cases)
        }
    except Exception as e:
        return {"statusCode": 500, "headers": HEADERS, "body": str(e)}
