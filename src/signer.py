import json
import boto3
import os
from botocore.config import Config

# Force the client to use the specific region and modern signature version
s3 = boto3.client('s3', 
    region_name='us-east-1', 
    config=Config(signature_version='s3v4')
)

def lambda_handler(event, context):
    try:
        query_params = event.get('queryStringParameters') or {}
        file_name = query_params['file_name']
        file_type = query_params.get('file_type') or 'audio/mpeg'
        bucket = os.environ['BUCKET_NAME']
        
        # The browser must upload with the same Content-Type used to sign the URL.
        url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket, 
                'Key': file_name,
                'ContentType': file_type
            },
            ExpiresIn=300
        )
        
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,*",
                "Access-Control-Allow-Methods": "OPTIONS,GET"
            },
            "body": json.dumps({"upload_url": url})
        }
    except Exception as e:
        return {"statusCode": 500, "body": str(e)}
