import json
import urllib.parse
import boto3
import os
import time  # NEW: Added to create unique names

sfn = boto3.client('stepfunctions')

def lambda_handler(event, context):
    print(f"Full Event Received: {json.dumps(event)}") # Debugging log
    
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    # 1. Filter: Only process audio
    if not (key.lower().endswith('.mp3') or key.lower().endswith('.wav')):
        print(f"Ignoring non-audio file: {key}")
        return {'statusCode': 200, 'body': 'Ignored'}

    # 2. Start Execution
    state_machine_arn = os.environ['STATE_MACHINE_ARN']
    
    # NEW: Added timestamp to make the name unique every time
    timestamp = int(time.time())
    execution_name = f"{key.split('/')[-1].replace('.', '-')}-{timestamp}"
    
    print(f"Attempting to start Step Function: {execution_name}")
    
    try:
        sfn.start_execution(
            stateMachineArn=state_machine_arn,
            name=execution_name,
            input=json.dumps({"bucket": bucket, "key": key})
        )
        print("Step Function Started Successfully!")
    except Exception as e:
        print(f"Error starting Step Function: {str(e)}")
        raise e
    
    return {'statusCode': 200, 'body': json.dumps("Pipeline Started!")}