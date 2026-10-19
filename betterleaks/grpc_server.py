import logging
from concurrent import futures
import grpc
from proto import ext_mcp_pb2, ext_mcp_pb2_grpc

logger = logging.getLogger("betterleaks_grpc")


import json

def _redact_json_value(val, redact_fn, endpoint: str):
    if isinstance(val, str):
        _, clean_text, findings = redact_fn(val, endpoint=endpoint)
        return clean_text, findings
    if isinstance(val, dict):
        new_dict = {}
        all_findings = []
        for k, v in val.items():
            new_v, findings = _redact_json_value(v, redact_fn, endpoint)
            new_dict[k] = new_v
            all_findings.extend(findings)
        return new_dict, all_findings
    if isinstance(val, list):
        new_list = []
        all_findings = []
        for item in val:
            new_item, findings = _redact_json_value(item, redact_fn, endpoint)
            new_list.append(new_item)
            all_findings.extend(findings)
        return new_list, all_findings
    return val, []


def redact_json_bytes(raw_bytes: bytes, redact_fn, endpoint: str) -> tuple[bool, bytes, list]:
    """Safely redact secrets in JSON bytes, preserving valid JSON structure and escaping."""
    try:
        raw_text = raw_bytes.decode("utf-8")
        parsed = json.loads(raw_text)
        cleaned_obj, findings = _redact_json_value(parsed, redact_fn, endpoint)
        if findings:
            cleaned_bytes = json.dumps(cleaned_obj).encode("utf-8")
            return True, cleaned_bytes, findings
        return False, raw_bytes, []
    except Exception:
        # Fallback to plain text redaction if not JSON
        raw_text = raw_bytes.decode("utf-8")
        has_secrets, clean_text, findings = redact_fn(raw_text, endpoint=endpoint)
        return has_secrets, clean_text.encode("utf-8"), findings


class BetterleaksExtMcpServicer(ext_mcp_pb2_grpc.ExtMcpServicer):
    """
    gRPC Servicer implementing Agentgateway's ExtMcp interface.
    Intercepts MCP tool calls (arguments) and responses (results) to redact secrets and PII.
    """

    def __init__(self, redact_fn):
        self.redact_fn = redact_fn

    def CheckRequest(self, request: ext_mcp_pb2.McpRequest, context):
        try:
            logger.debug(
                "gRPC CheckRequest method=%s services=%s",
                request.method,
                list(request.service_names),
            )
            if request.mcp_request:
                has_secrets, clean_bytes, findings = redact_json_bytes(
                    request.mcp_request, self.redact_fn, endpoint="grpc/mcp_request"
                )
                if has_secrets:
                    logger.info(
                        "MCP tool call %s intercepted: %d secret(s) redacted from arguments.",
                        request.method,
                        len(findings),
                    )
                    return ext_mcp_pb2.McpRequestResult(mutated=clean_bytes)
            return ext_mcp_pb2.McpRequestResult(**{"pass": ext_mcp_pb2.Pass()})
        except Exception:
            logger.exception("Error processing MCP CheckRequest")
            # Fail-open on unhandled exception in processor
            return ext_mcp_pb2.McpRequestResult(**{"pass": ext_mcp_pb2.Pass()})

    def CheckResponse(self, request: ext_mcp_pb2.McpResponse, context):
        try:
            logger.debug(
                "gRPC CheckResponse method=%s services=%s",
                request.method,
                list(request.service_names),
            )
            if request.mcp_response:
                has_secrets, clean_bytes, findings = redact_json_bytes(
                    request.mcp_response, self.redact_fn, endpoint="grpc/mcp_response"
                )
                if has_secrets:
                    logger.info(
                        "MCP tool response %s intercepted: %d secret(s) redacted from tool output.",
                        request.method,
                        len(findings),
                    )
                    return ext_mcp_pb2.McpResponseResult(mutated=clean_bytes)
            return ext_mcp_pb2.McpResponseResult(**{"pass": ext_mcp_pb2.Pass()})
        except Exception:
            logger.exception("Error processing MCP CheckResponse")
            # Fail-open on unhandled exception in processor
            return ext_mcp_pb2.McpResponseResult(**{"pass": ext_mcp_pb2.Pass()})


def create_grpc_server(port: int, redact_fn, max_workers: int = 10) -> grpc.Server:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    ext_mcp_pb2_grpc.add_ExtMcpServicer_to_server(
        BetterleaksExtMcpServicer(redact_fn=redact_fn), server
    )
    server.add_insecure_port(f"0.0.0.0:{port}")
    return server
