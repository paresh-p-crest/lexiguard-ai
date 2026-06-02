"""Local functional tests for DynamoDB storage and handlers.

Mocks DynamoDB so storage and Lambda handlers can run without AWS.
Run: python -m pytest tests/unit/test_storage.py
"""

import importlib
import json
import os
import sys

import pytest

SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
sys.path.insert(0, os.path.abspath(SRC))


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeTable:
    """Minimal in-memory stand-in for a boto3 DynamoDB Table."""

    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        self.items[Item["id"]] = dict(Item)

    def scan(self, **kwargs):
        return {"Items": list(self.items.values())}

    def get_item(self, Key):
        item = self.items.get(Key["id"])
        return {"Item": item} if item else {}

    def delete_item(self, Key):
        self.items.pop(Key["id"], None)


@pytest.fixture
def dynamo_storage(monkeypatch):
    monkeypatch.setenv("CASES_TABLE", "test-cases")
    import storage
    importlib.reload(storage)

    table = FakeTable()
    monkeypatch.setattr(storage, "_table", lambda: table)
    return storage, table


# --------------------------------------------------------------------------- #
# storage.py - DynamoDB backend
# --------------------------------------------------------------------------- #
def test_save_and_get_roundtrip(dynamo_storage):
    storage, _ = dynamo_storage
    case_id = storage.save_case({
        "client_name": "Acme Corp",
        "case_type": "Contract",
        "address": "1 Main St",
        "fee": "$5000",
        "source_bucket": "bkt",
        "source_key": "audio.mp3",
        "transcribe_job_name": "job-1",
    })
    assert isinstance(case_id, str) and len(case_id) > 0

    fetched = storage.get_case(case_id)
    assert fetched["source_bucket"] == "bkt"
    assert fetched["source_key"] == "audio.mp3"
    assert fetched["transcribe_job_name"] == "job-1"


def test_list_sorted_newest_first(dynamo_storage):
    storage, table = dynamo_storage
    id1 = storage.save_case({"client_name": "First"})
    id2 = storage.save_case({"client_name": "Second"})
    # Force a deterministic created_at ordering.
    table.items[id1]["created_at"] = "2024-01-01T00:00:00+00:00"
    table.items[id2]["created_at"] = "2024-06-01T00:00:00+00:00"

    rows = storage.list_cases()
    assert [r["client_name"] for r in rows] == ["Second", "First"]


def test_delete_removes_case(dynamo_storage):
    storage, _ = dynamo_storage
    case_id = storage.save_case({"client_name": "Temp"})
    assert storage.get_case(case_id) is not None
    storage.delete_case(case_id)
    assert storage.get_case(case_id) is None


def test_none_values_not_persisted(dynamo_storage):
    storage, _ = dynamo_storage
    case_id = storage.save_case({"client_name": "X", "address": None})
    item = storage.get_case(case_id)
    assert "address" not in item


# --------------------------------------------------------------------------- #
# Handlers wired through the storage layer
# --------------------------------------------------------------------------- #
def test_fetcher_handler_shapes_api_response(dynamo_storage):
    storage, _ = dynamo_storage
    storage.save_case({
        "client_name": "Globex",
        "case_type": "Lease",
        "address": "9 Elm",
        "fee": "$10",
    })

    import fetcher
    importlib.reload(fetcher)
    resp = fetcher.lambda_handler({}, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body[0]["client"] == "Globex"
    assert body[0]["type"] == "Lease"
    assert "id" in body[0]


def test_deleter_handler_deletes_and_cleans(dynamo_storage, monkeypatch):
    storage, _ = dynamo_storage
    case_id = storage.save_case({
        "client_name": "ToDelete",
        "source_bucket": "b", "source_key": "a.mp3",
        "kb_doc_bucket": "b", "kb_doc_key": "LexiGuard-transcripts/a.txt",
        "transcribe_job_name": "job-x",
    })

    import deleter
    importlib.reload(deleter)

    deleted_objects = []
    monkeypatch.setattr(deleter.s3, "delete_object",
                        lambda Bucket, Key: deleted_objects.append((Bucket, Key)))
    monkeypatch.setattr(deleter, "delete_transcribe_job", lambda name: None)
    monkeypatch.setattr(deleter, "start_kb_sync", lambda: None)

    resp = deleter.lambda_handler({"pathParameters": {"id": case_id}}, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"deleted": True}
    assert storage.get_case(case_id) is None
    assert ("b", "a.mp3") in deleted_objects


def test_deleter_handler_404_for_missing(dynamo_storage):
    import deleter
    importlib.reload(deleter)
    resp = deleter.lambda_handler({"pathParameters": {"id": "does-not-exist"}}, None)
    assert resp["statusCode"] == 404
