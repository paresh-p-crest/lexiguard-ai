import json
import os

import boto3
import psycopg2
from botocore.exceptions import ClientError

s3 = boto3.client('s3')
transcribe = boto3.client('transcribe')
bedrock_agent = boto3.client('bedrock-agent')

HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
    "Access-Control-Allow-Methods": "OPTIONS,DELETE"
}

def delete_s3_object(bucket, key):
    if bucket and key:
        s3.delete_object(Bucket=bucket, Key=key)

def delete_kb_access_check_file(bucket, key):
    if not bucket or not key:
        return

    prefix = key.rsplit('/', 1)[0] if '/' in key else ''
    access_check_key = f"{prefix}/.write_access_check_file.temp" if prefix else ".write_access_check_file.temp"
    s3.delete_object(Bucket=bucket, Key=access_check_key)

def delete_transcribe_job(job_name):
    if job_name:
        try:
            transcribe.delete_transcription_job(TranscriptionJobName=job_name)
        except transcribe.exceptions.BadRequestException as e:
            if 'does not exist' not in str(e):
                raise

def get_data_source_id(knowledge_base_id):
    configured_data_source_id = os.environ.get('DATA_SOURCE_ID')
    if configured_data_source_id:
        return configured_data_source_id

    response = bedrock_agent.list_data_sources(
        knowledgeBaseId=knowledge_base_id,
        maxResults=100
    )
    data_sources = response.get('dataSourceSummaries', [])
    if not data_sources:
        raise ValueError(f"No data source found for knowledge base {knowledge_base_id}")

    return data_sources[0]['dataSourceId']

def start_kb_sync():
    knowledge_base_id = os.environ.get('KB_ID')
    if not knowledge_base_id:
        return

    data_source_id = get_data_source_id(knowledge_base_id)
    try:
        response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=data_source_id,
            description='LexiGuard automatic sync after case delete'
        )
        print(f"Started KB sync: {json.dumps(response.get('ingestionJob', {}))}")
    except ClientError as e:
        if e.response.get('Error', {}).get('Code') == 'ConflictException':
            print("Skipped KB sync because another ingestion job is already running")
            return
        raise

def lambda_handler(event, context):
    if event.get('httpMethod') == 'OPTIONS':
        return {"statusCode": 200, "headers": HEADERS, "body": ""}

    conn = None
    try:
        case_id = (event.get('pathParameters') or {}).get('id')
        if not case_id:
            return {
                "statusCode": 400,
                "headers": HEADERS,
                "body": json.dumps({"error": "Case id is required"})
            }

        conn = psycopg2.connect(
            host=os.environ['DB_HOST'],
            database=os.environ['DB_NAME'],
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASS']
        )
        cur = conn.cursor()

        cur.execute("ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS source_bucket TEXT")
        cur.execute("ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS source_key TEXT")
        cur.execute("ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS transcript_bucket TEXT")
        cur.execute("ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS transcript_key TEXT")
        cur.execute("ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS kb_doc_bucket TEXT")
        cur.execute("ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS kb_doc_key TEXT")
        cur.execute("ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS transcribe_job_name TEXT")

        cur.execute("""
            SELECT
                source_bucket,
                source_key,
                transcript_bucket,
                transcript_key,
                kb_doc_bucket,
                kb_doc_key,
                transcribe_job_name
            FROM legal_cases
            WHERE id = %s
        """, (case_id,))
        row = cur.fetchone()

        if not row:
            cur.close()
            conn.close()
            return {
                "statusCode": 404,
                "headers": HEADERS,
                "body": json.dumps({"error": "Case not found"})
            }

        source_bucket, source_key, transcript_bucket, transcript_key, kb_doc_bucket, kb_doc_key, transcribe_job_name = row
        delete_s3_object(source_bucket, source_key)
        delete_s3_object(transcript_bucket, transcript_key)
        delete_s3_object(kb_doc_bucket, kb_doc_key)
        delete_kb_access_check_file(kb_doc_bucket, kb_doc_key)
        delete_transcribe_job(transcribe_job_name)

        cur.execute("DELETE FROM legal_cases WHERE id = %s", (case_id,))
        conn.commit()
        cur.close()
        conn.close()

        try:
            start_kb_sync()
        except Exception as e:
            print(f"Case deleted, but KB sync did not start: {str(e)}")

        return {
            "statusCode": 200,
            "headers": HEADERS,
            "body": json.dumps({"deleted": True})
        }
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()

        print(f"Delete error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": HEADERS,
            "body": json.dumps({"error": str(e)})
        }
