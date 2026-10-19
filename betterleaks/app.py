import logging
import os
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from recognizer import BetterleaksRecognizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("betterleaks_service")

app = FastAPI(
    title="Betterleaks Presidio Unified Security Service",
    description="Unified PII and Secret detection & redaction service powered by Betterleaks and Microsoft Presidio",
    version="1.0.0",
)

import re
import unicodedata

MAX_TEXT_LENGTH = int(os.environ.get("MAX_TEXT_LENGTH", "500000"))
ZERO_WIDTH_CHARS_RE = re.compile(r"[\u200B-\u200F\uFEFF\u00AD]")


class PayloadTooLargeError(HTTPException):
    def __init__(self, length: int, max_length: int = MAX_TEXT_LENGTH):
        super().__init__(
            status_code=413,
            detail=f"Payload too large: input text of length {length} exceeds maximum allowed limit of {max_length} characters.",
        )


def sanitize_input_text(text: str) -> str:
    """
    Validates input size to prevent SpaCy/NER buffer allocation crashes (CWE-400),
    and strips zero-width/invisible separators with NFKC normalization to prevent
    regex/tokenization evasion attacks (CWE-172).
    """
    if len(text) > MAX_TEXT_LENGTH:
        raise PayloadTooLargeError(len(text), MAX_TEXT_LENGTH)
    # Strip invisible zero-width characters that break token boundaries
    cleaned = ZERO_WIDTH_CHARS_RE.sub("", text)
    # Normalize unicode to canonical composition (NFKC)
    return unicodedata.normalize("NFKC", cleaned)


ENABLE_FRENCH_SUPPORT = (
    os.environ.get("ENABLE_FRENCH_SUPPORT", "true").lower() in ("true", "1", "yes")
)
AUTO_DETECT_LANGUAGE = (
    os.environ.get("AUTO_DETECT_LANGUAGE", "true").lower() in ("true", "1", "yes")
)
IGNORED_ENTITIES_RAW = os.environ.get(
    "IGNORED_ENTITIES", "ORGANIZATION,LOCATION,NRP,GPE,DATE_TIME,URL"
)
IGNORED_ENTITIES = set(
    e.strip() for e in IGNORED_ENTITIES_RAW.split(",") if e.strip()
)

COMMON_TECH_TERMS = {
    # Version control & repositories
    "git", "github", "gitlab", "bitbucket", "gitea", "forgejo", "repo", "repository",
    "commit", "branch", "merge", "rebase", "pull", "push", "diff", "patch", "stash",
    # Containers & orchestration
    "docker", "podman", "containerd", "kubernetes", "k8s", "helm", "compose", "swarm",
    # Languages & runtimes
    "python", "pip", "pipenv", "poetry", "uv", "node", "nodejs", "npm", "pnpm", "yarn",
    "bun", "rust", "cargo", "go", "golang", "java", "javac", "jvm", "kotlin", "scala",
    "swift", "ruby", "gem", "php", "composer", "c", "cpp", "csharp", "dotnet", "lua",
    "perl", "r", "julia", "elixir", "erlang", "clojure", "haskell", "typescript", "javascript",
    # OS & kernels
    "linux", "unix", "ubuntu", "debian", "centos", "redhat", "rhel", "fedora", "alpine",
    "arch", "gentoo", "suse", "windows", "macos", "darwin", "android", "ios", "kernel",
    # Databases & caches
    "redis", "memcached", "postgres", "postgresql", "mysql", "mariadb", "sqlite",
    "clickhouse", "mongo", "mongodb", "cassandra", "scylladb", "couchdb", "dynamodb",
    "elasticsearch", "opensearch", "solr", "neo4j", "milvus", "qdrant", "weaviate", "chroma",
    # Queues & streams
    "kafka", "rabbitmq", "nats", "pulsar", "celery",
    # Web servers & proxies
    "traefik", "caddy", "nginx", "envoy", "haproxy", "apache", "kong",
    # Shells, terminals & utils
    "bash", "zsh", "sh", "fish", "powershell", "cmd", "terminal", "tmux", "screen",
    "curl", "wget", "ssh", "scp", "sftp", "rsync", "sudo", "systemd", "cron", "crontab",
    "grep", "sed", "awk", "jq", "cat", "tar", "gzip", "zip", "unzip",
    # Editors & IDEs
    "vim", "nvim", "neovim", "emacs", "nano", "vscode", "sublime", "pycharm", "intellij",
    "cursor", "antigravity", "openwebui",
    # AI & ML frameworks / providers
    "ollama", "litellm", "vllm", "tgi", "huggingface", "openai", "anthropic", "mistral",
    "cohere", "groq", "gemini", "claude", "chatgpt", "deepseek", "langchain", "langfuse",
    "llamaindex", "transformers", "pytorch", "torch", "tensorflow", "keras", "onnx",
    # Observability & Monitoring
    "prometheus", "grafana", "loki", "tempo", "alertmanager", "gatus", "jaeger",
    "opentelemetry", "otel", "datadog",
    # Security, Identity & Secrets
    "authentik", "authelia", "keycloak", "vault", "consul", "certbot", "openssl",
    "wireguard", "openvpn", "tailscale", "zerotier", "cloudflare", "iptables", "nftables",
    # IaC & CI/CD
    "terraform", "tofu", "opentofu", "ansible", "packer", "vagrant", "pulumi",
    "jenkins", "argocd", "flux",
    # Cloud providers
    "aws", "azure", "gcp", "digitalocean", "hetzner", "linode", "ovh", "scaleway",
    # Formats & protocols
    "json", "yaml", "yml", "toml", "xml", "csv", "markdown", "grpc", "protobuf",
    "rest", "api", "sdk", "cli", "http", "https", "tcp", "udp", "dns", "dhcp",
    "ssh", "tls", "ssl", "oauth", "oidc", "sso", "jwt", "saml", "cors",
    "token", "secret", "cookie", "header", "payload",
    # Common dev terms
    "repo", "build", "ci", "cd", "pr", "issue", "bug", "patch", "release",
    "debug", "trace", "log", "logs", "test", "tests", "eval",
}

TECH_CONTEXT_PREFIXES = (
    "repo ", "repository ", "d\u00e9p\u00f4t ", "depot ", "commande ", "command ",
    "outil ", "tool ", "logiciel ", "software ", "service ", "serveur ", "server ",
    "client ", "lib ", "library ", "package ", "module ", "image ", "container ",
    "conteneur ", "branche ", "branch ", "commit ", "fichier ", "file ", "dossier ",
    "directory ", "folder ", "projet ", "project ", "application ", "app ",
)

# ------------------------------------------------------------------------------
# Initialize Presidio Engines with Betterleaks Recognizer
# ------------------------------------------------------------------------------
from presidio_analyzer.nlp_engine import NlpEngineProvider

nlp_models = [{"lang_code": "en", "model_name": "en_core_web_sm"}]
if ENABLE_FRENCH_SUPPORT:
    nlp_models.append({"lang_code": "fr", "model_name": "fr_core_news_sm"})

nlp_configuration = {
    "nlp_engine_name": "spacy",
    "models": nlp_models,
}
nlp_provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
nlp_engine = nlp_provider.create_engine()

supported_langs = ["en", "fr"] if ENABLE_FRENCH_SUPPORT else ["en"]
registry = RecognizerRegistry()
registry.load_predefined_recognizers(languages=supported_langs, nlp_engine=nlp_engine)

betterleaks_en = BetterleaksRecognizer(supported_language="en")
registry.add_recognizer(betterleaks_en)

if ENABLE_FRENCH_SUPPORT:
    betterleaks_fr = BetterleaksRecognizer(supported_language="fr")
    registry.add_recognizer(betterleaks_fr)
    logger.info(
        "Presidio Analyzer initialized with bilingual (en/fr) support and Betterleaks recognizers."
    )
else:
    logger.info(
        "Presidio Analyzer initialized with English-only support and Betterleaks recognizer."
    )

analyzer = AnalyzerEngine(registry=registry, nlp_engine=nlp_engine)
anonymizer = AnonymizerEngine()

# ------------------------------------------------------------------------------
# Language Detection & Entity Filtering Helpers
# ------------------------------------------------------------------------------
FRENCH_ACCENTS = re.compile(
    r"[\u00e9\u00e8\u00ea\u00eb\u00e0\u00e2\u00ee\u00ef\u00f4\u00f9\u00fb\u00fc\u00e7\u0153\u00e6"
    r"\u00c9\u00c8\u00ca\u00cb\u00c0\u00c2\u00ce\u00cf\u00d4\u00d9\u00db\u00dc\u00c7\u0152\u00c6]"
)
FRENCH_WORDS = {
    "le", "la", "les", "un", "une", "des", "dans", "sur", "pour", "avec", "sans",
    "pas", "ne", "que", "qui", "est", "sont", "du", "au", "aux", "ce", "cette",
    "ces", "mon", "son", "ton", "si", "tu", "en", "et", "ou", "\u00f9", "mais",
    "donc", "car", "ni", "comme", "nous", "vous", "ils", "elles", "je", "il",
    "elle", "on", "faire", "tout", "tous", "plus", "nouveau", "jamais", "fichier",
}
ENGLISH_WORDS = {
    "the", "is", "are", "in", "on", "at", "to", "for", "with", "without", "this",
    "that", "from", "by", "as", "an", "it", "and", "or", "but", "not", "have",
    "has", "had", "you", "we", "they", "he", "she", "all", "if", "then", "be",
    "can", "will", "do", "file", "token", "never", "need", "new",
}


def detect_language(text: str) -> str:
    """Detects whether text is French or English using fast accent and vocabulary heuristics."""
    if not text or not ENABLE_FRENCH_SUPPORT:
        return "en"
    if FRENCH_ACCENTS.search(text):
        return "fr"
    words = set(re.findall(r"\b[a-zA-Z\u00c0-\u00ff]+\b", text.lower()))
    fr_count = len(words.intersection(FRENCH_WORDS))
    en_count = len(words.intersection(ENGLISH_WORDS))
    if fr_count > en_count:
        return "fr"
    return "en"


def resolve_language(requested_lang: Optional[str], text: str) -> str:
    """Resolves requested language ('auto', 'fr', 'en') to a supported language code."""
    if not ENABLE_FRENCH_SUPPORT:
        return "en"
    if not requested_lang or requested_lang.lower() == "auto":
        return detect_language(text) if AUTO_DETECT_LANGUAGE else "en"
    clean_lang = requested_lang.lower().strip()
    if clean_lang in ("fr", "french"):
        return "fr"
    return "en"


def is_code_or_config_identifier(val: str) -> bool:
    """Determines if a matched PERSON entity is actually a code variable, env var, or technical identifier."""
    v = val.strip("`\"'()[]{}<>,.;:!?-/\\")
    if not v:
        return True
    if v.lower() in COMMON_TECH_TERMS:
        return True
    if "_" in v or "-" in v or "/" in v or "\\" in v:
        return True
    if v.isupper() and len(v) >= 2:
        return True
    if re.search(r"[a-z][A-Z]", v):  # camelCase
        return True
    if any(c.isdigit() for c in v) and any(c.isalpha() for c in v):  # alphanumeric identifier
        return True
    return False


def filter_analyzer_results(
    results: List[RecognizerResult], text: str, ignored_entities: Optional[set] = None
) -> List[RecognizerResult]:
    """
    Filters out noisy NLP entity classifications (e.g. ORGANIZATION, NRP, LOCATION, URL)
    and false-positive PERSON entities on technical code identifiers, lowercase words,
    or developer terms. Technical secrets detected by Betterleaks are never filtered.
    """
    ignored = ignored_entities if ignored_entities is not None else IGNORED_ENTITIES
    filtered = []
    for r in results:
        if r.entity_type in ignored:
            continue
        if r.entity_type == "PERSON":
            val = text[r.start : r.end]
            if is_code_or_config_identifier(val):
                continue
            if val.islower():
                continue
            # Ignore if surrounded by backticks or quotes
            if r.start > 0 and r.end < len(text):
                if text[r.start - 1] in ("`", "\"", "'") and text[r.end] in ("`", "\"", "'"):
                    continue
            # Check preceding technical context indicator
            preceding = text[max(0, r.start - 25) : r.start].lower()
            if any(preceding.endswith(p) for p in TECH_CONTEXT_PREFIXES):
                continue
        filtered.append(r)
    return filtered

# ------------------------------------------------------------------------------
# Prometheus Telemetry Metrics
# ------------------------------------------------------------------------------
from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from fastapi import Response

SCANS_TOTAL = Counter(
    "betterleaks_scans_total",
    "Total number of redaction and analysis scans performed",
    ["endpoint", "status"],
)

FINDINGS_TOTAL = Counter(
    "betterleaks_findings_total",
    "Total count of detected secrets and PII entities",
    ["entity_type", "recognizer_name"],
)

SCAN_DURATION_SECONDS = Histogram(
    "betterleaks_scan_duration_seconds",
    "Latency of detection and redaction requests in seconds",
    ["endpoint"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)


# ------------------------------------------------------------------------------
# Redis Storage for Ephemeral Tokenization
# ------------------------------------------------------------------------------
import redis
import secrets
import re
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "2"))
REDIS_AUTH = os.environ.get("REDIS_AUTH", None)
TOKEN_ENCRYPTION_KEY = os.environ.get("TOKEN_ENCRYPTION_KEY", None)

redis_client = None
aesgcm_cipher = None


def get_cipher():
    global aesgcm_cipher
    if aesgcm_cipher is None and TOKEN_ENCRYPTION_KEY:
        try:
            key_bytes = bytes.fromhex(TOKEN_ENCRYPTION_KEY.strip())
            if len(key_bytes) in (16, 24, 32):
                aesgcm_cipher = AESGCM(key_bytes)
                logger.info("Initialized AES-GCM cipher with Vault token encryption key.")
            else:
                logger.warning("TOKEN_ENCRYPTION_KEY has invalid byte length: %d", len(key_bytes))
        except Exception as e:
            logger.error("Failed to initialize AESGCM cipher: %s", e)
    return aesgcm_cipher


def encrypt_token_value(raw_secret: str) -> str:
    """Encrypts raw secret with AES-256-GCM before storing in Redis."""
    cipher = get_cipher()
    if not cipher:
        return raw_secret
    nonce = os.urandom(12)
    ciphertext = cipher.encrypt(nonce, raw_secret.encode("utf-8"), None)
    return "enc:" + base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_token_value(stored_value: str) -> str:
    """Decrypts ciphertext from Redis, restoring the original secret."""
    if not stored_value or not isinstance(stored_value, str):
        return stored_value
    if not stored_value.startswith("enc:"):
        return stored_value
    cipher = get_cipher()
    if not cipher:
        logger.error("Cannot decrypt token: TOKEN_ENCRYPTION_KEY not configured")
        return stored_value
    try:
        raw_payload = base64.b64decode(stored_value[4:])
        nonce = raw_payload[:12]
        ciphertext = raw_payload[12:]
        return cipher.decrypt(nonce, ciphertext, None).decode("utf-8")
    except Exception as e:
        logger.error("Decryption failed for stored token: %s", e)
        return stored_value


def get_redis_client():
    global redis_client
    if redis_client is None:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_AUTH if REDIS_AUTH else None,
            decode_responses=True,
            socket_timeout=2.0,
        )
    return redis_client


# ------------------------------------------------------------------------------
# Request / Response Schemas
# ------------------------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    text: str = Field(..., description="Text to analyze for PII and secrets")
    language: str = Field(default="auto", description="Language of text: 'auto', 'en', or 'fr'")
    correlation_id: Optional[str] = Field(default=None)
    score_threshold: Optional[float] = Field(default=0.4)
    entities: Optional[List[str]] = Field(default=None)
    ignored_entities: Optional[List[str]] = Field(default=None, description="Optional entity types to ignore")


class AnonymizeRequest(BaseModel):
    text: str = Field(..., description="Text to anonymize")
    analyzer_results: List[Dict[str, Any]] = Field(..., description="List of RecognizerResult dicts")
    anonymizers: Optional[Dict[str, Any]] = Field(default=None)


class RedactRequest(BaseModel):
    text: str = Field(..., description="Raw text containing potential secrets or PII")
    language: str = Field(default="auto", description="Text language: 'auto', 'en', or 'fr'")
    mask_char: str = Field(default="*", description="Mask character if using mask operator")
    mode: str = Field(default="replace", description="Redaction mode: 'replace' (<ENTITY_TYPE>) or 'mask' (***)")
    ignored_entities: Optional[List[str]] = Field(default=None, description="Optional entity types to ignore")


class RedactResponse(BaseModel):
    has_secrets: bool
    findings_count: int
    clean_text: str
    findings: List[Dict[str, Any]]


class TokenMapping(BaseModel):
    token: str
    entity_type: str
    ttl_seconds: int


class TokenizeRequest(BaseModel):
    text: str = Field(..., description="Text to scan and tokenize")
    language: str = Field(default="auto", description="Language of text: 'auto', 'en', or 'fr'")
    ttl_seconds: int = Field(default=300, description="TTL for token mappings in seconds (default 5 min)")
    prefix: str = Field(default="TOK", description="Prefix for surrogate tokens")
    score_threshold: Optional[float] = Field(default=0.4, description="Score threshold for entity detection")
    entities: Optional[List[str]] = Field(default=None, description="Optional entity types to filter for tokenization")
    ignored_entities: Optional[List[str]] = Field(default=None, description="Optional entity types to ignore")


class TokenizeResponse(BaseModel):
    has_secrets: bool
    findings_count: int
    tokenized_text: str
    tokens: List[TokenMapping]


class DetokenizeRequest(BaseModel):
    text: str = Field(..., description="Text containing surrogate tokens to rehydrate")


class DetokenizeResponse(BaseModel):
    detokenized_text: str
    rehydrated_count: int



# ------------------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------------------
@app.get("/healthz")
def healthz():
    return {"status": "healthy", "service": "betterleaks-presidio"}


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/analyze")
def analyze_endpoint(req: AnalyzeRequest):
    """
    Standard Presidio /analyze endpoint compatible with LiteLLM and external clients.
    Detects both native Presidio PII (names, cards, emails) and Betterleaks secrets.
    """
    start_t = time.perf_counter()
    try:
        sanitized_text = sanitize_input_text(req.text)
        target_lang = resolve_language(req.language, sanitized_text)
        raw_results = analyzer.analyze(
            text=sanitized_text,
            language=target_lang,
            entities=req.entities,
            score_threshold=req.score_threshold,
        )
        ignored_set = set(req.ignored_entities) if req.ignored_entities is not None else IGNORED_ENTITIES
        results = filter_analyzer_results(raw_results, sanitized_text, ignored_entities=ignored_set)
        duration = time.perf_counter() - start_t
        SCAN_DURATION_SECONDS.labels(endpoint="/analyze").observe(duration)
        status = "secrets_detected" if len(results) > 0 else "clean"
        SCANS_TOTAL.labels(endpoint="/analyze", status=status).inc()
        for r in results:
            rec_name = "unknown"
            if r.recognition_metadata and "recognizer_name" in r.recognition_metadata:
                rec_name = r.recognition_metadata["recognizer_name"]
            FINDINGS_TOTAL.labels(entity_type=r.entity_type, recognizer_name=rec_name).inc()

        return [r.to_dict() for r in results]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in /analyze")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/anonymize")
def anonymize_endpoint(req: AnonymizeRequest):
    """
    Standard Presidio /anonymize endpoint compatible with LiteLLM and external clients.
    """
    try:
        sanitized_text = sanitize_input_text(req.text)
        res_objs = [RecognizerResult.from_json(r) for r in req.analyzer_results]
        operators = {}
        if req.anonymizers:
            for entity_type, op_data in req.anonymizers.items():
                operators[entity_type] = OperatorConfig(
                    operator_name=op_data.get("type", "replace"),
                    params=op_data.get("params", {}),
                )
        anonymized = anonymizer.anonymize(
            text=sanitized_text,
            analyzer_results=res_objs,
            operators=operators if operators else None,
        )
        return {
            "text": anonymized.text,
            "items": [item.to_dict() for item in anonymized.items],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in /anonymize")
        raise HTTPException(status_code=500, detail=str(e))


def redact_text(
    text: str,
    language: str = "auto",
    mode: str = "replace",
    mask_char: str = "*",
    endpoint: str = "/redact",
    ignored_entities: Optional[List[str]] = None,
) -> tuple[bool, str, List[Dict[str, Any]]]:
    """Reusable secret and PII redaction function used by HTTP and gRPC services."""
    text = sanitize_input_text(text)
    start_t = time.perf_counter()
    target_lang = resolve_language(language, text)
    raw_results = analyzer.analyze(text=text, language=target_lang)
    ignored_set = set(ignored_entities) if ignored_entities is not None else IGNORED_ENTITIES
    results = filter_analyzer_results(raw_results, text, ignored_entities=ignored_set)

    operators = None
    if mode == "mask":
        operators = {
            "DEFAULT": OperatorConfig(
                operator_name="mask",
                params={"masking_char": mask_char, "chars_to_mask": 100, "from_end": True},
            )
        }

    anonymized = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=operators,
    )

    duration = time.perf_counter() - start_t
    SCAN_DURATION_SECONDS.labels(endpoint=endpoint).observe(duration)
    status = "secrets_detected" if len(results) > 0 else "clean"
    SCANS_TOTAL.labels(endpoint=endpoint, status=status).inc()
    for r in results:
        rec_name = "unknown"
        if r.recognition_metadata and "recognizer_name" in r.recognition_metadata:
            rec_name = r.recognition_metadata["recognizer_name"]
        FINDINGS_TOTAL.labels(entity_type=r.entity_type, recognizer_name=rec_name).inc()

    findings = [r.to_dict() for r in results]
    return (len(findings) > 0, anonymized.text, findings)


@app.post("/redact", response_model=RedactResponse)
def redact_endpoint(req: RedactRequest):
    """
    Unified one-step detection and redaction endpoint.
    Ideal for Open-WebUI Inlet filters, MCP gateway ExtProc hooks, and automation scripts.
    """
    try:
        has_secrets, clean_text, findings = redact_text(
            text=req.text,
            language=req.language,
            mode=req.mode,
            mask_char=req.mask_char,
            endpoint="/redact",
            ignored_entities=req.ignored_entities,
        )
        return RedactResponse(
            has_secrets=has_secrets,
            findings_count=len(findings),
            clean_text=clean_text,
            findings=findings,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in /redact")
        raise HTTPException(status_code=500, detail=str(e))


def remove_conflicting_spans(results: List[RecognizerResult]) -> List[RecognizerResult]:
    """Filters out overlapping detection spans, prioritizing highest score and largest span."""
    sorted_by_priority = sorted(
        results,
        key=lambda r: (r.score, (r.end - r.start)),
        reverse=True,
    )
    accepted: List[RecognizerResult] = []
    for candidate in sorted_by_priority:
        overlaps = any(
            max(candidate.start, acc.start) < min(candidate.end, acc.end)
            for acc in accepted
        )
        if not overlaps:
            accepted.append(candidate)
    return accepted


@app.post("/tokenize", response_model=TokenizeResponse)
def tokenize_endpoint(req: TokenizeRequest):
    """
    Scans input text, generates pseudorandom surrogate tokens (TOK_<ENTITY>_<hex>)
    for each detected secret/PII, and caches the mapping in Redis with TTL.
    """
    start_t = time.perf_counter()
    try:
        sanitized_text = sanitize_input_text(req.text)
        target_lang = resolve_language(req.language, sanitized_text)
        raw_results = analyzer.analyze(
            text=sanitized_text,
            language=target_lang,
            entities=req.entities,
            score_threshold=req.score_threshold,
        )
        ignored_set = set(req.ignored_entities) if req.ignored_entities is not None else IGNORED_ENTITIES
        results = filter_analyzer_results(raw_results, sanitized_text, ignored_entities=ignored_set)
        if not results:
            duration = time.perf_counter() - start_t
            SCAN_DURATION_SECONDS.labels(endpoint="/tokenize").observe(duration)
            SCANS_TOTAL.labels(endpoint="/tokenize", status="clean").inc()
            return TokenizeResponse(
                has_secrets=False,
                findings_count=0,
                tokenized_text=sanitized_text,
                tokens=[],
            )

        # Remove conflicting/overlapping spans to guarantee clean string slicing
        filtered_results = remove_conflicting_spans(results)
        # Sort findings descending by start index to substitute from right to left
        sorted_results = sorted(filtered_results, key=lambda r: r.start, reverse=True)
        r_client = get_redis_client()
        pipe = r_client.pipeline()

        tokens_info = []
        tokenized_text = sanitized_text
        for r in sorted_results:
            raw_val = sanitized_text[r.start : r.end]
            ent = re.sub(r"[^A-Z0-9]", "_", r.entity_type.upper())
            rand_suffix = secrets.token_hex(6)
            token = f"{req.prefix}_{ent}_{rand_suffix}"
            pipe.set(
                f"betterleaks:token:{token}",
                encrypt_token_value(raw_val),
                ex=req.ttl_seconds,
            )
            tokens_info.append(
                TokenMapping(
                    token=token,
                    entity_type=r.entity_type,
                    ttl_seconds=req.ttl_seconds,
                )
            )
            tokenized_text = tokenized_text[: r.start] + token + tokenized_text[r.end :]

        pipe.execute()

        duration = time.perf_counter() - start_t
        SCAN_DURATION_SECONDS.labels(endpoint="/tokenize").observe(duration)
        SCANS_TOTAL.labels(endpoint="/tokenize", status="secrets_detected").inc()
        for r in results:
            rec_name = "unknown"
            if r.recognition_metadata and "recognizer_name" in r.recognition_metadata:
                rec_name = r.recognition_metadata["recognizer_name"]
            FINDINGS_TOTAL.labels(entity_type=r.entity_type, recognizer_name=rec_name).inc()

        return TokenizeResponse(
            has_secrets=True,
            findings_count=len(results),
            tokenized_text=tokenized_text,
            tokens=tokens_info,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in /tokenize")
        raise HTTPException(status_code=500, detail=str(e))


TOKEN_PATTERN = re.compile(r"\b[A-Za-z0-9_]*TOK_[A-Za-z0-9_]+_[a-f0-9]{12}\b")


@app.post("/detokenize", response_model=DetokenizeResponse)
def detokenize_endpoint(req: DetokenizeRequest):
    """
    Scans text for surrogate tokens, fetches encrypted secrets from Redis,
    decrypts them with AES-GCM, and restores them for authorized client presentation.
    """
    try:
        tokens_found = set(TOKEN_PATTERN.findall(req.text))
        if not tokens_found:
            return DetokenizeResponse(detokenized_text=req.text, rehydrated_count=0)

        r_client = get_redis_client()
        pipe = r_client.pipeline()
        token_list = list(tokens_found)
        for tok in token_list:
            pipe.get(f"betterleaks:token:{tok}")
        values = pipe.execute()

        rehydrated_text = req.text
        count = 0
        for tok, stored_val in zip(token_list, values):
            if stored_val is not None:
                plain_val = decrypt_token_value(stored_val)
                rehydrated_text = rehydrated_text.replace(tok, plain_val)
                count += 1

        return DetokenizeResponse(
            detokenized_text=rehydrated_text,
            rehydrated_count=count,
        )
    except Exception as e:
        logger.exception("Error in /detokenize")
        raise HTTPException(status_code=500, detail=str(e))


