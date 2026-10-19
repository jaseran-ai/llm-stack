"""
title: Betterleaks & Presidio Secret Guard
author: llm-stack
author_url: https://github.com/llm-stack
version: 1.3.0
license: MIT
description: Bidirectional security filter intercepting user prompts (inlet) and LLM responses / RAG documents (outlet) to redact secrets and PII asynchronously.
"""

from typing import Any, Dict, List, Optional, Tuple
import aiohttp
from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0, description="Priority level for filter execution."
        )
        betterleaks_url: str = Field(
            default="http://betterleaks:8080",
            description="Base URL of the Betterleaks-Presidio microservice.",
        )
        enable_inlet: bool = Field(
            default=True,
            description="Enable scanning and redaction of incoming user prompts.",
        )
        enable_outlet: bool = Field(
            default=True,
            description="Enable scanning and redaction of outbound model responses and RAG excerpts.",
        )
        action: str = Field(
            default="redact",
            description="Inlet action on secret detection: 'redact' (replace in-place), 'tokenize' (vaulted ephemeral surrogate), or 'block' (reject prompt).",
        )
        tokenize_ttl: int = Field(
            default=300,
            description="TTL in seconds for vaulted token mappings (default: 300s / 5min).",
        )
        redact_mode: str = Field(
            default="replace",
            description="Redaction style: 'replace' (<GITHUB_PAT>, <VAULT_TOKEN>) or 'mask' (***).",
        )
        mask_char: str = Field(
            default="*",
            description="Character used for masking when redact_mode is 'mask'.",
        )
        request_timeout: int = Field(
            default=3,
            description="Timeout in seconds for redaction API calls.",
        )
        language: str = Field(
            default="auto",
            description="Language for text analysis: 'auto' (detect en/fr), 'en', or 'fr'.",
        )
        enable_french: bool = Field(
            default=True,
            description="Toggle French language processing when auto-detecting language.",
        )
        ignored_entities: str = Field(
            default="ORGANIZATION,LOCATION,NRP,GPE,DATE_TIME,URL",
            description="Comma-separated list of entities to ignore/skip during scanning.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def _tokenize_text(self, text: str) -> Tuple[bool, str, List[str]]:
        """Submits text to Betterleaks /tokenize endpoint."""
        if not text or not isinstance(text, str) or not text.strip():
            return False, text, []

        try:
            timeout = aiohttp.ClientTimeout(total=self.valves.request_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                target_lang = self.valves.language
                if not self.valves.enable_french and target_lang == "auto":
                    target_lang = "en"
                ignored_list = [
                    e.strip()
                    for e in self.valves.ignored_entities.split(",")
                    if e.strip()
                ]
                payload = {
                    "text": text,
                    "language": target_lang,
                    "ttl_seconds": self.valves.tokenize_ttl,
                    "ignored_entities": ignored_list,
                }
                async with session.post(
                    f"{self.valves.betterleaks_url}/tokenize", json=payload
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        has_secrets = bool(data.get("has_secrets"))
                        tokenized_text = data.get("tokenized_text", text)
                        tokens = data.get("tokens", [])
                        entity_types = list(
                            {t.get("entity_type") for t in tokens if t.get("entity_type")}
                        )
                        return has_secrets, tokenized_text, entity_types
        except Exception:
            pass
        return False, text, []

    async def _detokenize_text(self, text: str) -> str:
        """Submits text to Betterleaks /detokenize endpoint to restore secrets."""
        if not text or not isinstance(text, str) or not text.strip():
            return text

        try:
            timeout = aiohttp.ClientTimeout(total=self.valves.request_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload = {"text": text}
                async with session.post(
                    f"{self.valves.betterleaks_url}/detokenize", json=payload
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("detokenized_text", text)
        except Exception:
            pass
        return text

    async def _redact_text(self, text: str) -> Tuple[bool, str, List[str]]:
        """
        Submits text to Betterleaks /redact endpoint.
        Returns (has_secrets, clean_text, finding_types).
        """
        if not text or not isinstance(text, str) or not text.strip():
            return False, text, []

        try:
            timeout = aiohttp.ClientTimeout(total=self.valves.request_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                target_lang = self.valves.language
                if not self.valves.enable_french and target_lang == "auto":
                    target_lang = "en"
                ignored_list = [
                    e.strip()
                    for e in self.valves.ignored_entities.split(",")
                    if e.strip()
                ]
                payload = {
                    "text": text,
                    "language": target_lang,
                    "mode": self.valves.redact_mode,
                    "mask_char": self.valves.mask_char,
                    "ignored_entities": ignored_list,
                }
                async with session.post(
                    f"{self.valves.betterleaks_url}/redact", json=payload
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        has_secrets = bool(data.get("has_secrets"))
                        clean_text = data.get("clean_text", text)
                        findings = data.get("findings", [])
                        entity_types = list(
                            {f.get("entity_type") for f in findings if f.get("entity_type")}
                        )
                        return has_secrets, clean_text, entity_types
        except Exception:
            # Fail-open: if security service is temporarily unreachable, do not crash the chat pipeline
            pass

        return False, text, []

    async def inlet(
        self, body: Dict[str, Any], __user__: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Inlet hook: executed before sending prompt messages to the LLM.
        """
        if not self.valves.enable_inlet:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        last_message = messages[-1]
        if last_message.get("role") != "user":
            return body

        content = last_message.get("content")
        if not isinstance(content, str) or not content.strip():
            return body

        if self.valves.action == "tokenize":
            has_secrets, tokenized_text, _ = await self._tokenize_text(content)
            if has_secrets:
                messages[-1]["content"] = tokenized_text
                body["messages"] = messages
            return body

        has_secrets, clean_text, entity_types = await self._redact_text(content)
        if has_secrets:
            if self.valves.action == "block":
                raise ValueError(
                    f"🛑 [Security Alert] Sensitive information detected ({', '.join(entity_types)}). "
                    f"Prompt blocked by llm-stack security guardrail."
                )
            messages[-1]["content"] = clean_text
            body["messages"] = messages

        return body

    async def outlet(
        self, body: Dict[str, Any], __user__: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Outlet hook: executed after model completion and RAG retrieval before rendering.
        Scans model messages and RAG citations to ensure credentials never leak to the client,
        or rehydrates ephemeral surrogate tokens for authorized user sessions.
        """
        if not self.valves.enable_outlet:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        for message in messages:
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                if self.valves.action == "tokenize":
                    message["content"] = await self._detokenize_text(content)
                else:
                    has_secrets, clean_text, _ = await self._redact_text(content)
                    if has_secrets:
                        message["content"] = clean_text

            # Process RAG source citations if present
            sources = message.get("sources")
            if isinstance(sources, list):
                for source in sources:
                    docs = source.get("document")
                    if isinstance(docs, list):
                        new_docs = []
                        for doc in docs:
                            if isinstance(doc, str):
                                if self.valves.action == "tokenize":
                                    new_docs.append(await self._detokenize_text(doc))
                                else:
                                    _, clean_doc, _ = await self._redact_text(doc)
                                    new_docs.append(clean_doc)
                            else:
                                new_docs.append(doc)
                        source["document"] = new_docs

        return body
