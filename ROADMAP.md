# Roadmap

This document lists planned work for LLM Stack. Shipped changes are tracked in [`CHANGELOG.md`](CHANGELOG.md).

---

## Guiding Principle: Configuration as Code & Repeatability

> The entire infrastructure and all its integrations must be **100% automated and declarative**, through versioned configuration files and idempotent provisioning scripts.
> No manual setup through a graphical interface should ever be required for a new user to clone the repository and get a working stack (`./setup.sh && ./start.sh`).

---

## Planned

- [ ] **Text-to-speech in Open WebUI**: add a local neural text-to-speech backend for Open WebUI.
- [ ] **Speech-to-text**: add a local, CPU-friendly transcription backend for Open WebUI voice input.

---

## Ideas & Contributions Welcome

Feature requests are tracked through [GitHub issues](https://github.com/jaseran-ai/llm-stack/issues). New services must follow [`ADDING_AN_APPLICATION.md`](ADDING_AN_APPLICATION.md).
