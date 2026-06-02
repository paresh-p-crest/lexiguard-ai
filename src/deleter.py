import json
import os

import boto3
from botocore.exceptions import ClientError

import storage

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

    try:
        case_id = (event.get('pathParameters') or {}).get('id')
        if not case_id:
            return {
                "statusCode": 400,
                "headers": HEADERS,
                "body": json.dumps({"error": "Case id is required"})
            }

        case = storage.get_case(case_id)
        if not case:
            return {
                "statusCode": 404,
                "headers": HEADERS,
                "body": json.dumps({"error": "Case not found"})
            }

        delete_s3_object(case.get('source_bucket'), case.get('source_key'))
        delete_s3_object(case.get('transcript_bucket'), case.get('transcript_key'))
        delete_s3_object(case.get('kb_doc_bucket'), case.get('kb_doc_key'))
        delete_kb_access_check_file(case.get('kb_doc_bucket'), case.get('kb_doc_key'))
        delete_transcribe_job(case.get('transcribe_job_name'))

        storage.delete_case(case_id)

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
        print(f"Delete error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": HEADERS,
            "body": json.dumps({"error": str(e)})
        }
