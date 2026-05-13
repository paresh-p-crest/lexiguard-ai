# LexiGuard AI

LexiGuard AI is a serverless legal-audio intake application. Users upload an audio conversation, AWS transcribes it, Bedrock extracts structured case details, PostgreSQL stores the case record, and Bedrock Knowledge Base answers questions over the generated transcript.

## Architecture

- React + Vite frontend in `lexiguard-ui/`
- AWS SAM/CloudFormation backend in `template.yaml`
- API Gateway routes for upload signing, case list, case delete, and chat
- S3 for uploaded audio, raw Transcribe JSON, and clean Knowledge Base transcripts
- Lambda functions in `src/`
- Step Functions workflow for transcription and analysis
- Amazon Transcribe for audio transcription
- Amazon Bedrock for structured extraction
- Bedrock Knowledge Base for chat retrieval
- RDS PostgreSQL for structured case records

## Important Files

- `template.yaml` - single source of truth for backend infrastructure
- `samconfig.toml` - local deploy settings for this workstation
- `samconfig.example.toml` - copy this when setting up another sandbox/developer
- `src/` - Lambda source code
- `lexiguard-ui/src/App.jsx` - React app

## Deploy Backend

First-time deploy should be guided so SAM stores your sandbox parameters:

```powershell
sam build
sam deploy --guided
```

For later deploys:

```powershell
sam build
sam deploy
```

Use a different stack name per environment, for example:

- `lexiguard-sandbox-paresh`
- `lexiguard-sandbox-manager`
- `lexiguard-dev`

Do not overwrite `template.yaml` for each environment. Use parameters instead.

## Required Deploy Parameters

- `BucketName` - globally unique S3 bucket name. Use a different value for each sandbox/developer.
- `KnowledgeBaseId` - Bedrock Knowledge Base ID.
- `KnowledgeBaseDataSourceId` - optional. Leave blank to use the first data source.
- `DBName` - PostgreSQL database name.
- `DBUsername` - PostgreSQL admin user.
- `DBPassword` - PostgreSQL password.
- `DBInstanceClass` - RDS instance size.
- `VpcId` - VPC for RDS security group.
- `DBSubnetIds` - at least two subnets for RDS.
- `DBAllowedCidr` - CIDR allowed to connect to PostgreSQL.

## Frontend

Install and run:

```powershell
cd lexiguard-ui
npm install
npm run dev
```

Build:

```powershell
npm run build
```

## Lambda Functions

- `signer.py` - returns presigned S3 upload URLs.
- `app.py` - handles S3 create events and starts the Step Function.
- `analyzer.py` - reads Transcribe JSON, writes clean transcript text, extracts case fields with Bedrock, and saves PostgreSQL records.
- `fetcher.py` - returns cases from PostgreSQL.
- `chat.py` - answers questions using Bedrock Knowledge Base.
- `deleter.py` - deletes PostgreSQL case record, S3 audio/transcript objects, Transcribe job, and starts KB sync.
- `kb_sync.py` - starts Bedrock Knowledge Base ingestion.

## S3 Prefixes

- Uploaded audio: bucket root
- Raw Transcribe output: `LexiGuard-transcribe-json/`
- Bedrock KB documents: `LexiGuard-transcripts/`

The Bedrock Knowledge Base data source should point only to:

```text
LexiGuard-transcripts/
```

Do not point the KB to raw Transcribe JSON.

## Clean Setup On Another PC

1. Install AWS CLI, SAM CLI, Python 3.11, Node.js, and npm.
2. Configure AWS credentials:

```powershell
aws configure
```

3. Clone/copy this repo.
4. Install frontend dependencies:

```powershell
cd lexiguard-ui
npm install
cd ..
```

5. Copy `samconfig.example.toml` values into `samconfig.toml` or run:

```powershell
sam deploy --guided
```

6. Deploy backend:

```powershell
sam build
sam deploy
```

7. Update `API_BASE` in `lexiguard-ui/src/App.jsx` if the API Gateway URL changes.
8. Start frontend:

```powershell
cd lexiguard-ui
npm run dev
```

## Notes

CloudFormation can import or generate templates from some existing AWS resources, but it cannot automatically recreate the full application logic, Lambda code, Step Function behavior, CORS rules, permissions, and local frontend setup. For this project, keep `template.yaml` as the maintained infrastructure-as-code source.
