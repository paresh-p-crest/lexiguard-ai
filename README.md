# LexiGuard AI

LexiGuard AI is a serverless legal-audio intake and intelligence application. Users upload an audio conversation, AWS transcribes it, Amazon Bedrock extracts structured case details, PostgreSQL stores the case record, and a Bedrock Knowledge Base answers questions over the generated transcript.

## Architecture

- **Frontend:** React + Vite app in `lexiguard-ui/`
- **Infrastructure:** AWS SAM/CloudFormation in `template.yaml`
- **API:** Amazon API Gateway for upload signing, case listing, case deletion, and chat
- **Storage:** Amazon S3 for uploaded audio, raw Transcribe JSON, and clean transcript documents
- **Processing:** AWS Lambda functions in `src/`
- **Workflow:** AWS Step Functions for transcription, analysis, and Knowledge Base sync
- **Audio transcription:** Amazon Transcribe
- **AI extraction:** Amazon Bedrock Claude model
- **Chat retrieval:** Amazon Bedrock Knowledge Base
- **Database:** Amazon RDS PostgreSQL for structured case records

## Important Files

- `template.yaml` - single source of truth for backend AWS resources
- `samconfig.toml` - local SAM deploy settings for one workstation/environment
- `samconfig.example.toml` - example SAM config for another developer or sandbox
- `src/` - Lambda function source code
- `src/requirements.txt` - Python Lambda dependencies
- `lexiguard-ui/` - React/Vite frontend project
- `lexiguard-ui/src/App.jsx` - main React application

## Prerequisites

Install these before setting up the project:

- Git
- AWS CLI
- AWS SAM CLI
- Python 3.11
- Node.js and npm
- AWS account access with permissions for CloudFormation, Lambda, API Gateway, S3, Step Functions, Transcribe, Bedrock, RDS, EC2 networking, IAM, and CloudWatch Logs

Configure AWS credentials:

```powershell
aws configure
```

Bedrock prerequisites:

- Model access enabled for the Bedrock model used by the app
- Existing Bedrock Knowledge Base
- Existing Knowledge Base data source pointing to the S3 prefix `LexiGuard-transcripts/`

## Required Deploy Parameters

These parameters are provided during `sam deploy --guided` or in `samconfig.toml`.

- `ResourcePrefix` - lowercase namespace/developer prefix, for example `paresh`, `friend1`, or `demo`.
- `BucketName` - optional globally unique S3 bucket name. Leave blank to generate `lexiguard-{ResourcePrefix}-{AccountId}-{Region}`.
- `KnowledgeBaseId` - Bedrock Knowledge Base ID.
- `KnowledgeBaseDataSourceId` - optional. Leave blank to use the first data source in the Knowledge Base.
- `DBName` - PostgreSQL database name.
- `DBUsername` - PostgreSQL admin username.
- `DBPassword` - PostgreSQL password.
- `DBInstanceClass` - RDS instance type, for example `db.t3.micro`.
- `VpcId` - VPC where the RDS security group is created.
- `DBSubnetIds` - at least two subnet IDs for the RDS DB subnet group.
- `DBAllowedCidr` - CIDR allowed to connect to PostgreSQL. Restrict this for non-sandbox use.

Use a different stack name per environment, for example:

- `lexiguard-sandbox-paresh`
- `lexiguard-sandbox-manager`
- `lexiguard-dev`

Do not overwrite `template.yaml` for different environments. Keep one template and change parameter values per stack.

In a shared AWS account, each developer should use a unique CloudFormation stack name and `ResourcePrefix`. For example, Paresh can deploy `lexiguard-sandbox-paresh` with `ResourcePrefix=paresh`, while another developer can deploy `lexiguard-sandbox-friend1` with `ResourcePrefix=friend1`. This avoids S3 bucket, Lambda, API, Step Function, RDS, and security group naming collisions.

The stack name itself is not controlled by `template.yaml`; it is chosen by SAM/CloudFormation before the template is processed. Set it during `sam deploy --guided` or in `samconfig.toml`.

## Lambda Functions

- `signer.py` - returns presigned S3 upload URLs.
- `app.py` - handles S3 object-created events and starts the Step Functions workflow.
- `analyzer.py` - reads Transcribe JSON, writes clean transcript text, extracts case fields with Bedrock, and saves PostgreSQL records.
- `fetcher.py` - returns case records from PostgreSQL.
- `chat.py` - answers questions using Bedrock Knowledge Base retrieval.
- `deleter.py` - deletes the PostgreSQL case record, related S3 objects, related Transcribe job, and starts Knowledge Base sync.
- `kb_sync.py` - starts a Bedrock Knowledge Base ingestion job.

## S3 Prefixes

- Uploaded audio: bucket root
- Raw Transcribe output: `LexiGuard-transcribe-json/`
- Bedrock Knowledge Base documents: `LexiGuard-transcripts/`

The Bedrock Knowledge Base data source should point only to:

```text
LexiGuard-transcripts/
```

Do not point the Knowledge Base to `LexiGuard-transcribe-json/`. That folder contains raw Amazon Transcribe JSON and can fail or pollute KB ingestion.

## Fresh Setup On A New PC

1. Clone the repository:

```powershell
git clone <your-repo-url>
cd lexiguard-ai
```

2. Install frontend dependencies:

```powershell
cd lexiguard-ui
npm install
cd ..
```

3. Deploy the backend for the first time:

```powershell
sam build
sam deploy --guided
```

During guided deploy, provide the required parameters listed above. Choose `yes` when SAM asks to save settings to `samconfig.toml`.

4. Copy the deployed API base URL from the CloudFormation/SAM output named `ApiBaseUrl`.

5. Update `API_BASE` in `lexiguard-ui/src/App.jsx` if the API Gateway URL is different from the current value.

6. Start the frontend:

```powershell
cd lexiguard-ui
npm run dev
```

7. Open the Vite local URL shown in the terminal and test:

- Upload audio
- Confirm the case appears in the table
- Ask a chat question
- Delete a case
- Confirm Bedrock Knowledge Base sync completes

## Normal Development Workflow

For backend changes:

```powershell
sam build
sam deploy
```

For frontend changes:

```powershell
cd lexiguard-ui
npm run dev
```

For frontend production build check:

```powershell
cd lexiguard-ui
npm run build
```

## Validation

Backend template validation:

```powershell
sam validate
```

Frontend lint:

```powershell
cd lexiguard-ui
npm run lint
```

## Notes

`template.yaml` should be treated as the maintained infrastructure-as-code source. AWS Console tools can help inspect existing resources, but they will not reliably recreate the full application, including Lambda code, Step Function logic, permissions, CORS behavior, Bedrock sync behavior, and the React frontend.
