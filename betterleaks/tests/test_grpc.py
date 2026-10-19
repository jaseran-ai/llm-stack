"""Unit tests for Betterleaks ExtMcp gRPC service."""
import pytest
import grpc
from proto import ext_mcp_pb2, ext_mcp_pb2_grpc


@pytest.fixture(scope="module")
def grpc_channel():
    channel = grpc.insecure_channel("localhost:50052")
    yield channel
    channel.close()


@pytest.fixture(scope="module")
def stub(grpc_channel):
    return ext_mcp_pb2_grpc.ExtMcpStub(grpc_channel)


def test_grpc_check_request_with_secret(stub):
    """Verify tool call arguments containing secrets are mutated/redacted."""
    raw_payload = b'{"name": "searxng_search", "arguments": {"query": "ghp_123456789012345678901234567890123456"}}'  # gitleaks:allow
    req = ext_mcp_pb2.McpRequest(
        service_names=["searxng"],
        method="tools/call",
        mcp_request=raw_payload,
    )
    res = stub.CheckRequest(req)
    assert res.WhichOneof("result") == "mutated"
    mutated_text = res.mutated.decode("utf-8")
    assert "<GITHUB_PAT>" in mutated_text
    assert "ghp_" not in mutated_text


def test_grpc_check_request_clean(stub):
    """Verify clean tool call arguments pass through unmodified."""
    raw_payload = b'{"name": "searxng_search", "arguments": {"query": "standard search query"}}'
    req = ext_mcp_pb2.McpRequest(
        service_names=["searxng"],
        method="tools/call",
        mcp_request=raw_payload,
    )
    res = stub.CheckRequest(req)
    assert res.WhichOneof("result") == "pass"


def test_grpc_check_response_with_secret(stub):
    """Verify tool output containing credentials is sanitized before reaching agent."""
    raw_payload = b'{"results": [{"content": "Here is API key: ghp_123456789012345678901234567890123456"}]}'  # gitleaks:allow
    resp = ext_mcp_pb2.McpResponse(
        service_names=["searxng"],
        method="tools/call",
        mcp_response=raw_payload,
    )
    res = stub.CheckResponse(resp)
    assert res.WhichOneof("result") == "mutated"
    mutated_text = res.mutated.decode("utf-8")
    assert "<GITHUB_PAT>" in mutated_text
    assert "ghp_" not in mutated_text


def test_grpc_check_response_clean(stub):
    """Verify clean tool output passes through unmodified."""
    raw_payload = b'{"results": [{"content": "Safe information"}]}'
    resp = ext_mcp_pb2.McpResponse(
        service_names=["searxng"],
        method="tools/call",
        mcp_response=raw_payload,
    )
    res = stub.CheckResponse(resp)
    assert res.WhichOneof("result") == "pass"
