import json
import boto3
import os

bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')

HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
    "Access-Control-Allow-Methods": "OPTIONS,POST"
}

def lambda_handler(event, context):
    if event.get('httpMethod') == 'OPTIONS':
        return {"statusCode": 200, "headers": HEADERS, "body": ""}

    try:
        body = json.loads(event.get('body') or '{}')
        user_question = body.get('question', '').strip()
        if not user_question:
            return {
                "statusCode": 400,
                "headers": HEADERS,
                "body": json.dumps({"error": "Question is required"})
            }

        kb_id = os.environ['KB_ID']

        # Call the Knowledge Base
        response = bedrock_agent_runtime.retrieve_and_generate(
            input={'text': user_question},
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': kb_id,
                    'modelArn': 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0'
                }
            }
        )

        return {
            "statusCode": 200,
            "headers": HEADERS,
            "body": json.dumps({"answer": response['output']['text']})
        }
    except Exception as e:
        print(f"Chat error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": HEADERS,
            "body": json.dumps({"error": str(e)})
        }
