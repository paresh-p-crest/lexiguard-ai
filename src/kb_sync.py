import json
import os

import boto3
from botocore.exceptions import ClientError

bedrock_agent = boto3.client('bedrock-agent')

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
    knowledge_base_id = os.environ['KB_ID']
    data_source_id = get_data_source_id(knowledge_base_id)

    try:
        response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=data_source_id,
            description='LexiGuard automatic sync after S3 transcript change'
        )
        ingestion_job = response.get('ingestionJob', {})
        return {
            "status": "STARTED",
            "ingestionJobId": ingestion_job.get('ingestionJobId')
        }
    except ClientError as e:
        if e.response.get('Error', {}).get('Code') == 'ConflictException':
            return {"status": "SKIPPED", "reason": "A KB sync is already running"}
        raise

def lambda_handler(event, context):
    result = start_kb_sync()
    print(f"Knowledge Base sync result: {json.dumps(result)}")
    return result
