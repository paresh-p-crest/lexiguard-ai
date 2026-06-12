# [LexiGuard AI](https://legal-audio-ai.vercel.app/) — Demo & Documentation

**↗ The title [LexiGuard AI](https://legal-audio-ai.vercel.app/) is a link — click it to open the live app.**

**Online (rendered):** [https://legal-audio-ai.vercel.app/documentation](https://legal-audio-ai.vercel.app/documentation) · **Raw markdown:** [/documentation.md](https://legal-audio-ai.vercel.app/documentation.md)

**Product:** LexiGuard AI — serverless legal-audio intake and case intelligence  
**One-line:** Upload a legal conversation audio file; AWS transcribes it, Bedrock extracts structured case fields, and you chat over the transcript via a Bedrock Knowledge Base.

---

## At a glance

| | |
|---|---|
| **Problem** | Legal teams spend time re-listening to intake calls to find client name, matter type, fee, and key facts. |
| **Solution** | Upload audio → automatic transcription → AI extraction → structured case list + RAG chat over the conversation. |
| **Users** | Legal intake teams, demos of serverless AI on AWS, sandbox developers. |
| **Data** | Audio and transcripts in **S3**; structured cases in **DynamoDB**; semantic search via **Bedrock Knowledge Base**. |
| **Stack** | React (Vercel) · API Gateway · Lambda · Step Functions · Transcribe · Bedrock · S3 · DynamoDB · KMS |

---

## 1. Requirements & business value

### Problem statement

Intake conversations are often captured as audio. Staff must replay recordings or manually type client name, matter type, property address, and fee into a case system. That is slow and inconsistent.

### Goals

- **Faster intake** — upload audio; AI fills the case table  
- **Searchable conversations** — ask natural-language questions about what was said  
- **Serverless AWS** — no servers to manage; SAM-deployed infrastructure  
- **Clean lifecycle** — delete removes DB record, S3 files, Transcribe job, and re-syncs the Knowledge Base  

### Core features

| Area | What it does |
|------|----------------|
| **Upload** | Browser gets presigned S3 URL; audio uploads directly to S3 (not through Lambda) |
| **Processing** | S3 event → Step Functions → Transcribe → Bedrock analyzer → KB sync |
| **Case list** | Client name, case type, address, fee, status — extracted by Bedrock from transcript |
| **Chat** | Questions answered from **Bedrock Knowledge Base** (retrieve-and-generate over indexed transcripts) |
| **Delete** | Removes DynamoDB record, audio, raw JSON, clean transcript, Transcribe job; triggers KB re-ingestion |

### Demo examples

| User action | System does |
|-------------|-------------|
| Upload legal audio | Presign → S3 → workflow starts; UI polls until new case row appears |
| View case list | `GET /cases` from DynamoDB |
| Ask *“What is the matter for this client?”* | `POST /chat` → Bedrock KB retrieval over transcript |
| Ask *“What fee was discussed?”* | Same — grounded in indexed `.txt` transcript |
| Delete case | `DELETE /cases/{id}` — full cleanup + KB sync |

### Out of scope

Court filing automation · multi-tenant auth · guaranteed legal advice · real-time streaming transcription in the UI

### Demo success checklist

- [ ] Upload completes and case row appears within a few minutes  
- [ ] Extracted fields match the conversation  
- [ ] Chat answers reflect the uploaded transcript  
- [ ] Delete removes case and related S3 objects  

---

## 2. Technical overview

### Flow in 9 steps

1. **React UI** calls `GET /sign` → **Signer Lambda** returns presigned S3 PUT URL.  
2. Browser uploads audio **directly to S3** (bucket root).  
3. S3 **ObjectCreated** invokes **Watchman Lambda** (`app.py`) → starts **Step Functions**.  
4. **Step Functions** starts **Amazon Transcribe**; waits and polls until job **COMPLETED**.  
5. **Analyzer Lambda** reads Transcribe JSON from `LexiGuard-transcribe-json/`, writes clean `.txt` to `LexiGuard-transcripts/`, calls **Bedrock Claude** for structured JSON, saves case to **DynamoDB**.  
6. **KB Sync Lambda** starts Bedrock Knowledge Base **ingestion** so chat can retrieve the new transcript.  
7. UI polls `GET /cases` until the new record appears.  
8. User asks a question → `POST /chat` → **Chat Lambda** uses **retrieve_and_generate** on the Knowledge Base.  
9. **Delete** → **Deleter Lambda** removes DynamoDB + S3 + Transcribe job → KB sync again.

**Chat uses a Knowledge Base** (indexed transcripts in S3). **Structured case fields** come from direct Bedrock extraction in the analyzer — not from the KB.

### AWS services used

| Service | Role |
|---------|------|
| **Amazon S3** | Audio uploads, raw Transcribe JSON, clean KB transcript `.txt` files |
| **API Gateway** | `GET /sign`, `GET /cases`, `POST /chat`, `DELETE /cases/{id}` |
| **AWS Lambda** | Signer, watchman, analyzer, fetcher, chat, deleter, kb-sync |
| **AWS Step Functions** | Orchestrate Transcribe → analyze → KB sync |
| **Amazon Transcribe** | Speech-to-text from uploaded audio |
| **Amazon Bedrock** | Claude extraction (analyzer) + KB retrieve-and-generate (chat) |
| **Bedrock Knowledge Base** | Vector index over `LexiGuard-transcripts/` prefix |
| **Amazon DynamoDB** | Structured case records (`{ResourcePrefix}-lexiguard-cases`) |
| **AWS KMS** | Encryption key for the stack |
| **CloudWatch** | Lambda and Step Functions logs |
| **AWS SAM** | Deploy from `template.yaml` |

**External:** React + Vite UI on [Vercel](https://legal-audio-ai.vercel.app/)

### S3 prefixes

| Prefix | Content |
|--------|---------|
| Bucket root | Uploaded audio files |
| `LexiGuard-transcribe-json/` | Raw Amazon Transcribe JSON output |
| `LexiGuard-transcripts/` | Clean plain-text transcripts for **Bedrock KB** indexing |

The Knowledge Base data source must point only at **`LexiGuard-transcripts/`** — not raw JSON.

### Lambda functions

| Handler | API / trigger | Purpose |
|---------|---------------|---------|
| `signer.py` | `GET /sign` | Presigned S3 upload URL |
| `app.py` | S3 ObjectCreated | Start Step Functions workflow |
| `analyzer.py` | Step Functions task | Transcribe JSON → Bedrock extract → DynamoDB + KB `.txt` |
| `fetcher.py` | `GET /cases` | List cases from DynamoDB |
| `chat.py` | `POST /chat` | Bedrock KB retrieve-and-generate |
| `deleter.py` | `DELETE /cases/{id}` | Delete case, S3 objects, Transcribe job; KB sync |
| `kb_sync.py` | Step Functions / deleter | Start KB ingestion job |

Function names follow `{ResourcePrefix}-lexiguard-*` (e.g. `sandbox-lexiguard-analyzer`).

### Deploy (quick)

```bash
sam build && sam deploy
```

**Guided first deploy** — set `ResourcePrefix`, `BucketName`, `KnowledgeBaseId`, optional `KnowledgeBaseDataSourceId`.

**After deploy:** wire S3 bucket notification to the watchman Lambda (see `README.md`).

**UI:** copy `ApiBaseUrl` from stack outputs → `lexiguard-ui/.env` as `VITE_API_BASE`.

```bash
cd lexiguard-ui && npm run dev
```

---

## 3. Architecture diagram (AWS environment)

<p align="center">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 360" width="100%" max-width="920" role="img" aria-label="LexiGuard AI AWS architecture">
  <defs>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
      <path d="M0,0 L8,3 L0,6 Z" fill="#475569"/>
    </marker>
    <style>
      .box { fill: #1e293b; stroke: #64748b; stroke-width: 1.5; }
      .ext { fill: #0f172a; stroke: #38bdf8; stroke-width: 1.5; }
      .store { fill: #1e293b; stroke: #a78bfa; stroke-width: 1.5; }
      .lbl { fill: #e2e8f0; font-family: system-ui, Segoe UI, sans-serif; font-size: 12px; font-weight: 600; }
      .subl { fill: #94a3b8; font-family: system-ui, Segoe UI, sans-serif; font-size: 10px; }
      .edge { stroke: #64748b; stroke-width: 1.5; fill: none; marker-end: url(#arrow); }
      .elbl { fill: #64748b; font-family: system-ui, sans-serif; font-size: 9px; }
    </style>
  </defs>
  <rect class="box" x="20" y="30" width="100" height="48" rx="8"/>
  <text class="lbl" x="70" y="50" text-anchor="middle">React UI</text>
  <text class="subl" x="70" y="64" text-anchor="middle">Vercel</text>
  <rect class="box" x="150" y="30" width="110" height="48" rx="8"/>
  <text class="lbl" x="205" y="50" text-anchor="middle">API Gateway</text>
  <text class="subl" x="205" y="64" text-anchor="middle">sign / cases / chat</text>
  <rect class="box" x="290" y="30" width="100" height="48" rx="8"/>
  <text class="lbl" x="340" y="50" text-anchor="middle">Signer</text>
  <text class="subl" x="340" y="64" text-anchor="middle">presign URL</text>
  <ellipse class="store" cx="470" cy="54" rx="55" ry="28"/>
  <text class="lbl" x="470" y="52" text-anchor="middle">Amazon S3</text>
  <text class="subl" x="470" y="66" text-anchor="middle">audio + transcripts</text>
  <rect class="box" x="560" y="30" width="100" height="48" rx="8"/>
  <text class="lbl" x="610" y="50" text-anchor="middle">Watchman</text>
  <text class="subl" x="610" y="64" text-anchor="middle">S3 trigger</text>
  <rect class="box" x="690" y="30" width="120" height="48" rx="8"/>
  <text class="lbl" x="750" y="50" text-anchor="middle">Step Functions</text>
  <text class="subl" x="750" y="64" text-anchor="middle">orchestration</text>
  <line class="edge" x1="120" y1="54" x2="150" y2="54"/>
  <line class="edge" x1="260" y1="54" x2="290" y2="54"/>
  <line class="edge" x1="390" y1="54" x2="415" y2="54"/>
  <text class="elbl" x="130" y="46" text-anchor="middle">API</text>
  <line class="edge" x1="70" y1="78" x2="70" y2="100"/>
  <line class="edge" x1="70" y1="100" x2="470" y2="100"/>
  <line class="edge" x1="470" y1="100" x2="470" y2="82"/>
  <text class="elbl" x="270" y="94" text-anchor="middle">PUT audio direct</text>
  <line class="edge" x1="525" y1="54" x2="560" y2="54"/>
  <line class="edge" x1="660" y1="54" x2="690" y2="54"/>
  <rect class="ext" x="20" y="130" width="110" height="40" rx="8"/>
  <text class="lbl" x="75" y="155" text-anchor="middle">Transcribe</text>
  <rect class="box" x="160" y="130" width="100" height="40" rx="8"/>
  <text class="lbl" x="210" y="150" text-anchor="middle">Analyzer</text>
  <text class="subl" x="210" y="162" text-anchor="middle">Bedrock extract</text>
  <rect class="box" x="290" y="130" width="90" height="40" rx="8"/>
  <text class="lbl" x="335" y="150" text-anchor="middle">KB Sync</text>
  <rect class="box" x="410" y="130" width="100" height="40" rx="8"/>
  <text class="lbl" x="460" y="150" text-anchor="middle">Fetcher</text>
  <text class="subl" x="460" y="162" text-anchor="middle">GET /cases</text>
  <rect class="box" x="540" y="130" width="90" height="40" rx="8"/>
  <text class="lbl" x="585" y="150" text-anchor="middle">Chat</text>
  <text class="subl" x="585" y="162" text-anchor="middle">POST /chat</text>
  <rect class="box" x="660" y="130" width="90" height="40" rx="8"/>
  <text class="lbl" x="705" y="150" text-anchor="middle">Deleter</text>
  <line class="edge" x1="750" y1="78" x2="750" y2="115"/>
  <line class="edge" x1="750" y1="115" x2="75" y2="130"/>
  <line class="edge" x1="130" y1="150" x2="160" y2="150"/>
  <line class="edge" x1="260" y1="150" x2="290" y2="150"/>
  <line class="edge" x1="380" y1="150" x2="410" y2="150"/>
  <ellipse class="store" cx="210" cy="250" rx="65" ry="30"/>
  <text class="lbl" x="210" y="248" text-anchor="middle">DynamoDB</text>
  <text class="subl" x="210" y="262" text-anchor="middle">case records</text>
  <rect class="ext" x="360" y="220" width="130" height="48" rx="8"/>
  <text class="lbl" x="425" y="242" text-anchor="middle">Bedrock KB</text>
  <text class="subl" x="425" y="256" text-anchor="middle">retrieve + generate</text>
  <rect class="ext" x="530" y="220" width="110" height="48" rx="8"/>
  <text class="lbl" x="585" y="242" text-anchor="middle">Bedrock</text>
  <text class="subl" x="585" y="256" text-anchor="middle">Claude model</text>
  <line class="edge" x1="210" y1="170" x2="210" y2="220"/>
  <line class="edge" x1="335" y1="170" x2="425" y2="220"/>
  <line class="edge" x1="470" y1="82" x2="470" y2="200"/>
  <line class="edge" x1="470" y1="200" x2="335" y2="200"/>
  <line class="edge" x1="585" y1="170" x2="585" y2="220"/>
  <line class="edge" x1="210" y1="130" x2="210" y2="115"/>
  <line class="edge" x1="210" y1="115" x2="585" y2="115"/>
  <line class="edge" x1="585" y1="115" x2="585" y2="130"/>
  <text class="elbl" x="400" y="318" text-anchor="middle">Upload path + async workflow + KB-grounded chat</text>
</svg>
</p>

| Path | Flow |
|------|------|
| **Upload** | UI → `GET /sign` → presigned PUT → S3 audio |
| **Process** | S3 → Watchman → Step Functions → Transcribe → Analyzer → S3 `.txt` + DynamoDB → KB sync |
| **List** | UI → `GET /cases` → Fetcher → DynamoDB |
| **Chat** | UI → `POST /chat` → Chat Lambda → Bedrock Knowledge Base |
| **Delete** | UI → `DELETE /cases/{id}` → Deleter → DynamoDB + S3 + Transcribe → KB sync |

---

## 4. Demo recording

<p style="font-size: 1.2em; font-weight: 600; line-height: 1.6; margin: 0.75em 0;">
  <a href="https://legal-audio-ai.vercel.app/">→ Open live app — legal-audio-ai.vercel.app</a>
</p>

<p style="font-size: 1.2em; font-weight: 600; line-height: 1.6; margin: 0.75em 0;">
  <a href="https://screenrec.com/share/at6BGZgdpx/">→ Watch recorded walkthrough</a>
</p>

---

*Repo layout: `template.yaml` + `src/` (SAM backend) · `lexiguard-ui/` (React app)*
