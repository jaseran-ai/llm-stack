#!/usr/bin/env python3
"""
LLM Stack — Public OpenAPI Specification Generator & Leak Auditor.

Derives the public OpenAPI specification from services, filtering strictly
for operations tagged with `x-llm-stack-audience: public`.
Enforces strict anti-leak checks preventing internal component names,
internal DNS hostnames, or private network ranges from appearing in public documentation.
"""

import sys
import json
import re
from pathlib import Path

# Forbidden terms that must NEVER leak to public user documentation
FORBIDDEN_TERMS = [
    r"authentik-server",
    r"authentik-worker",
    r"vault-agent",
    r"secrets_ram",
    r"100\.73\.",
    r"192\.168\.",
    r"10\.0\.",
    r"llm-stack-network",
    r"internal-backend",
    r"postgres:5432",
    r"clickhouse:9000",
    r"redis:6379",
    r"seaweedfs:8888",
    r"admin_token",
    r"root_token",
]

# Base canonical specification for public LLM Stack interfaces
SOURCE_SPEC = {
    "openapi": "3.1.0",
    "info": {
        "title": "LLM Stack Public API",
        "version": "1.0.0",
        "description": "Public OpenAI-compatible inference and guardrail APIs for LLM Stack."
    },
    "servers": [
        {"url": "https://chat.{DOMAIN}/api", "description": "Production Ingress Gateway"}
    ],
    "paths": {
        "/v1/models": {
            "get": {
                "summary": "List Available Models",
                "operationId": "listModels",
                "x-llm-stack-audience": "public",
                "responses": {
                    "200": {
                        "description": "List of available LLM models and aliases",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "object": {"type": "string", "example": "list"},
                                        "data": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "id": {"type": "string", "example": "lfm2.5-thinking-1.2b"},
                                                    "object": {"type": "string", "example": "model"},
                                                    "owned_by": {"type": "string", "example": "llm-stack"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/v1/chat/completions": {
            "post": {
                "summary": "Create Chat Completion",
                "operationId": "createChatCompletion",
                "x-llm-stack-audience": "public",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["model", "messages"],
                                "properties": {
                                    "model": {"type": "string", "example": "lfm2.5-thinking-1.2b"},
                                    "messages": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                                                "content": {"type": "string", "example": "Hello, how can you help me?"}
                                            }
                                        }
                                    },
                                    "temperature": {"type": "number", "default": 0.7},
                                    "stream": {"type": "boolean", "default": False}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Chat completion response with optional PII redaction applied",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "object": {"type": "string", "example": "chat.completion"},
                                        "created": {"type": "integer"},
                                        "model": {"type": "string"},
                                        "choices": {"type": "array", "items": {"type": "object"}}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/v1/embeddings": {
            "post": {
                "summary": "Generate Text Embeddings",
                "operationId": "createEmbedding",
                "x-llm-stack-audience": "public",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["model", "input"],
                                "properties": {
                                    "model": {"type": "string", "example": "text-embedding-nomic"},
                                    "input": {"type": "string", "example": "Semantic chunk for vector indexing"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Generated embedding vector",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "object": {"type": "string", "example": "list"},
                                        "data": {"type": "array", "items": {"type": "object"}}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/healthz": {
            "get": {
                "summary": "Public Liveness Probe",
                "operationId": "getHealth",
                "x-llm-stack-audience": "public",
                "responses": {
                    "200": {
                        "description": "Gateway is online and operational",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "example": "ok"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/internal/vault/unseal": {
            "post": {
                "summary": "Internal Unseal Endpoint",
                "operationId": "unsealVault",
                "x-llm-stack-audience": "private-internal",
                "responses": {"200": {"description": "Internal only"}}
            }
        }
    }
}

def filter_public_spec(spec: dict) -> dict:
    public_spec = {
        "openapi": spec.get("openapi", "3.1.0"),
        "info": spec.get("info", {}),
        "servers": spec.get("servers", []),
        "paths": {},
        "components": spec.get("components", {})
    }

    for path, methods in spec.get("paths", {}).items():
        public_methods = {}
        for method, operation in methods.items():
            if isinstance(operation, dict) and operation.get("x-llm-stack-audience") == "public":
                public_methods[method] = operation
        if public_methods:
            public_spec["paths"][path] = public_methods

    return public_spec

def audit_spec_for_leaks(json_text: str):
    for pattern in FORBIDDEN_TERMS:
        match = re.search(pattern, json_text, re.IGNORECASE)
        if match:
            raise ValueError(
                f"SECURITY VIOLATION: Forbidden internal term '{match.group(0)}' "
                f"detected in public OpenAPI documentation!"
            )

def main():
    root_dir = Path(__file__).resolve().parent.parent.parent
    user_docs_ref = root_dir / "docs" / "user" / "docs" / "reference"
    user_fr_ref = root_dir / "docs" / "user" / "i18n" / "fr" / "docusaurus-plugin-content-docs" / "current" / "reference"

    user_docs_ref.mkdir(parents=True, exist_ok=True)
    user_fr_ref.mkdir(parents=True, exist_ok=True)

    public_spec = filter_public_spec(SOURCE_SPEC)
    json_output = json.dumps(public_spec, indent=2)

    # Enforce strict zero-leak audit
    audit_spec_for_leaks(json_output)

    # Write English and French copies
    out_en = user_docs_ref / "openapi-public.json"
    out_fr = user_fr_ref / "openapi-public.json"

    out_en.write_text(json_output, encoding="utf-8")
    out_fr.write_text(json_output, encoding="utf-8")

    print(f"PASS: Public OpenAPI specification successfully generated and verified ({len(public_spec['paths'])} endpoints).")
    print(f" -> {out_en}")
    print(f" -> {out_fr}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
