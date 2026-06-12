# LexiGuard AI

LexiGuard AI is a serverless legal-audio intake and intelligence application. Users upload an audio conversation, AWS transcribes it, Amazon Bedrock extracts structured case details, DynamoDB stores the case record, and a Bedrock Knowledge Base answers questions over the generated transcript.

**Demo doc:** [documentation.md](./documentation.md) · [online](https://legal-audio-ai.vercel.app/documentation)

## Architecture

- **Frontend:** React + Vite app in `lexiguard-ui/`
- **Infrastructure:** AWS SAM/CloudFormation in `template.yaml`
- **API:** Amazon API Gateway for upload signing, case listing, case deletion, and chat
- **Storage:** Amazon S3 for uploaded audio, raw Transcribe JSON, and clean transcript documents
- **Case records:** Amazon DynamoDB table (`${ResourcePrefix}-lexiguard-cases`), pay-per-request
- **Processing:** AWS Lambda functions in `src/`
- **Workflow:** AWS Step Functions for transcription, analysis, and Knowledge Base sync
- **Audio transcription:** Amazon Transcribe
- **AI extraction:** Amazon Bedrock Claude model
- **Chat retrieval:** Amazon Bedrock Knowledge Base

## Important Files

- `documentation.md` - requirements, technical overview, architecture diagram, demo video link
- `template.yaml` - single source of truth for backend AWS resources
- `samconfig.toml` - local SAM deploy settings for one workstation/environment
- `samconfig.example.toml` - example SAM config for another developer or sandbox
- `src/` - Lambda function source code
- `src/storage.py` - DynamoDB read/write for case records
- `src/requirements.txt` - Python Lambda dependencies
- `lexiguard-ui/` - React/Vite frontend project
- `lexiguard-ui/.env` - `VITE_API_BASE` for the deployed API URL

## Prerequisites

Install these before setting up the project:

- Git
- AWS CLI
- AWS SAM CLI
- Python 3.11
- Node.js and npm
- AWS account access with permissions for CloudFormation, Lambda, API Gateway, S3, DynamoDB, Step Functions, Transcribe, Bedrock, IAM, and CloudWatch Logs

Configure AWS credentials:

```powershell
aws configure
```

Bedrock prerequisites:

- Model access enabled for the Bedrock model used by the app
- Existing Bedrock Knowledge Base
- Existing Knowledge Base data source pointing to the S3 prefix `LexiGuard-transcripts/` in your LexiGuard bucket

## Required Deploy Parameters

These parameters are provided during `sam deploy --guided` or in `samconfig.toml`.

- `ResourcePrefix` - lowercase namespace/developer prefix, for example `paresh`, `friend1`, or `demo`.
- `BucketName` - existing S3 bucket name (default: `lexiguard-legal-data-ps-b402`). The stack does **not** create an S3 bucket. Ensure this bucket has CORS allowing browser `PUT` uploads and that your Bedrock KB data source points at `LexiGuard-transcripts/` in this bucket.
- `KnowledgeBaseId` - Bedrock Knowledge Base ID.
- `KnowledgeBaseDataSourceId` - optional. Leave blank to use the first data source in the Knowledge Base.

After the first deploy, wire S3 to the watchman Lambda once (replace function ARN as needed):

```powershell
$arn = aws lambda get-function --function-name sandbox-lexiguard-watchman --region us-east-1 --query Configuration.FunctionArn --output text
aws s3api put-bucket-notification-configuration --bucket lexiguard-legal-data-ps-b402 --notification-configuration "{`"LambdaFunctionConfigurations`":[{`"LambdaFunctionArn`":`"$arn`",`"Events`":[`"s3:ObjectCreated:*`"]}]}"
```

Use a different stack name per environment, for example:

- `lexiguard-sandbox-paresh`
- `lexiguard-sandbox-manager`
- `lexiguard-dev`

In a shared AWS account, each developer should use a unique CloudFormation stack name and `ResourcePrefix`.

## Lambda Functions

- `signer.py` - returns presigned S3 upload URLs.
- `app.py` - handles S3 object-created events and starts the Step Functions workflow.
- `storage.py` - DynamoDB read/write for case records.
- `analyzer.py` - reads Transcribe JSON, writes clean transcript text, extracts case fields with Bedrock, saves to DynamoDB.
- `fetcher.py` - returns case records from DynamoDB.
- `chat.py` - answers questions using Bedrock Knowledge Base retrieval.
- `deleter.py` - deletes the DynamoDB case record, related S3 objects, related Transcribe job, and starts Knowledge Base sync.
- `kb_sync.py` - starts a Bedrock Knowledge Base ingestion job.

## S3 Prefixes

- Uploaded audio: bucket root
- Raw Transcribe output: `LexiGuard-transcribe-json/`
- Bedrock Knowledge Base documents: `LexiGuard-transcripts/`

The Bedrock Knowledge Base data source should point only to:

```text
LexiGuard-transcripts/
```

## Fresh Setup On A New PC

1. Clone the repository and install frontend dependencies.
2. Deploy the backend: `sam build` then `sam deploy --guided`.
3. Copy `ApiBaseUrl` from deploy outputs into `lexiguard-ui/.env` as `VITE_API_BASE`.
4. Wire S3 bucket notification to watchman (see above).
5. Start frontend: `cd lexiguard-ui && npm run dev`.

## Normal Development Workflow

```powershell
sam build
sam deploy
```

```powershell
cd lexiguard-ui
npm run dev
```

## Validation

```powershell
sam validate
python -m pytest tests/unit/test_storage.py
```
