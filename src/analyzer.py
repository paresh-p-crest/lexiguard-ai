import json
import boto3
import os
import psycopg2
import re # Added for text cleaning
import urllib.parse

s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime')

KB_DOC_PREFIX = os.environ.get('KB_DOC_PREFIX', 'LexiGuard-transcripts/')

def parse_s3_uri(uri):
    if not uri:
        return None, None

    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme == 's3':
        return parsed.netloc, urllib.parse.unquote(parsed.path.lstrip('/'))

    path_parts = parsed.path.lstrip('/').split('/', 1)
    if len(path_parts) == 2:
        return path_parts[0], urllib.parse.unquote(path_parts[1])

    return None, None

def build_kb_doc_key(source_key, transcribe_job_name):
    source_name = os.path.basename(source_key or transcribe_job_name or 'case-audio')
    source_root = os.path.splitext(source_name)[0]
    safe_source_root = re.sub(r'[^A-Za-z0-9._-]+', '-', source_root).strip('-') or 'case-audio'
    safe_job_name = re.sub(r'[^A-Za-z0-9._-]+', '-', transcribe_job_name or 'transcript').strip('-')
    return f"{KB_DOC_PREFIX.rstrip('/')}/{safe_source_root}-{safe_job_name}.txt"

def lambda_handler(event, context):
    try:
        # 1. Get Transcript from S3
        transcription_job = event['TranscriptionJob']
        transcript_bucket, transcript_key = parse_s3_uri(transcription_job['Transcript']['TranscriptFileUri'])
        source_bucket, source_key = parse_s3_uri(transcription_job.get('Media', {}).get('MediaFileUri'))
        response = s3.get_object(Bucket=transcript_bucket, Key=transcript_key)
        transcript_data = json.loads(response['Body'].read().decode('utf-8'))
        raw_text = transcript_data['results']['transcripts'][0]['transcript']
        kb_doc_bucket = transcript_bucket
        kb_doc_key = build_kb_doc_key(source_key, transcription_job.get('TranscriptionJobName'))
        s3.put_object(
            Bucket=kb_doc_bucket,
            Key=kb_doc_key,
            Body=raw_text.encode('utf-8'),
            ContentType='text/plain; charset=utf-8'
        )
        print(f"Wrote KB transcript document: s3://{kb_doc_bucket}/{kb_doc_key}")
        
        # 2. Bedrock Analysis
        model_id = os.environ['BEDROCK_MODEL_ID']
        # We tell the model strictly NOT to talk, only give JSON
        system_prompt = "You are a legal expert. Extract fields as JSON: Client_Name, Case_Type, Property_Address, Fee_Amount. Return ONLY JSON. No preamble."
        
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "system": system_prompt,
            "messages": [{"role": "user", "content": f"Extract JSON from this: {raw_text}"}]
        })
        
        res = bedrock.invoke_model(body=body, modelId=model_id)
        raw_ai_response = json.loads(res.get('body').read())['content'][0]['text']
        print(f"Raw AI Response: {raw_ai_response}")

        # CLEANING LOGIC: Remove markdown backticks if AI included them
        json_match = re.search(r'\{.*\}', raw_ai_response, re.DOTALL)
        if json_match:
            ai_json = json.loads(json_match.group())
        else:
            ai_json = json.loads(raw_ai_response)

        # 3. SAVE TO DATABASE
        conn = psycopg2.connect(
            host=os.environ['DB_HOST'],
            database=os.environ['DB_NAME'],
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASS'],
            connect_timeout=10
        )
        cur = conn.cursor()
        
        # Create Table (Always runs first)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS legal_cases (
                id SERIAL PRIMARY KEY,
                client_name TEXT,
                case_type TEXT,
                address TEXT,
                fee TEXT,
                source_bucket TEXT,
                source_key TEXT,
                transcript_bucket TEXT,
                transcript_key TEXT,
                kb_doc_bucket TEXT,
                kb_doc_key TEXT,
                transcribe_job_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS source_bucket TEXT")
        cur.execute("ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS source_key TEXT")
        cur.execute("ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS transcript_bucket TEXT")
        cur.execute("ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS transcript_key TEXT")
        cur.execute("ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS kb_doc_bucket TEXT")
        cur.execute("ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS kb_doc_key TEXT")
        cur.execute("ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS transcribe_job_name TEXT")
        
        cur.execute("""
            INSERT INTO legal_cases (
                client_name,
                case_type,
                address,
                fee,
                source_bucket,
                source_key,
                transcript_bucket,
                transcript_key,
                kb_doc_bucket,
                kb_doc_key,
                transcribe_job_name
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            ai_json.get('Client_Name', 'N/A'), 
            ai_json.get('Case_Type', 'N/A'), 
            ai_json.get('Property_Address', 'N/A'), 
            ai_json.get('Fee_Amount', 'N/A'),
            source_bucket,
            source_key,
            transcript_bucket,
            transcript_key,
            kb_doc_bucket,
            kb_doc_key,
            transcription_job.get('TranscriptionJobName')
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        print("Successfully saved to RDS!")
        
        return {"status": "SUCCESS"}

    except Exception as e:
        print(f"ERROR: {str(e)}")
        raise e
