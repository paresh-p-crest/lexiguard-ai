"""DynamoDB storage for LexiGuard case records."""

import os
import uuid
from datetime import datetime, timezone

# Metadata fields persisted for every case. "id" and "created_at" are managed here.
CASE_FIELDS = [
    "client_name",
    "case_type",
    "address",
    "fee",
    "source_bucket",
    "source_key",
    "transcript_bucket",
    "transcript_key",
    "kb_doc_bucket",
    "kb_doc_key",
    "transcribe_job_name",
]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _table():
    import boto3

    return boto3.resource("dynamodb").Table(os.environ["CASES_TABLE"])


def save_case(record):
    """Persist a new case record and return its id."""
    item = {key: record.get(key) for key in CASE_FIELDS if record.get(key) is not None}
    item["id"] = uuid.uuid4().hex
    item["created_at"] = _now_iso()
    _table().put_item(Item=item)
    return item["id"]


def list_cases():
    """Return all cases newest-first as a list of dicts."""
    table = _table()
    items = []
    response = table.scan()
    items.extend(response.get("Items", []))
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    items.sort(key=lambda row: row.get("created_at", ""), reverse=True)
    return items


def get_case(case_id):
    """Return a single case dict (or None) including S3/Transcribe metadata."""
    return _table().get_item(Key={"id": case_id}).get("Item")


def delete_case(case_id):
    """Delete a case record by id."""
    _table().delete_item(Key={"id": case_id})
