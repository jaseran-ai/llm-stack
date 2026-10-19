---
name: Bug Report
about: Create a report to help us improve llm-stack
title: 'fix: '
labels: bug
assignees: ''
---

## 🐛 Bug Description

A clear and concise description of what the bug is.

---

## 🔁 Steps to Reproduce

1. Run `./setup.sh --dns-mode=<mode>`
2. Start the stack with `./start.sh`
3. Execute command or browse to `...`
4. See error

---

## 🎯 Expected Behavior

A clear and concise description of what you expected to happen.

---

## 📋 Environment & Configuration

- **Host OS**: (e.g. Ubuntu 24.04 LTS, Debian 12, macOS)
- **Architecture**: (e.g. x86_64, arm64)
- **Docker Version**: (e.g. 27.x)
- **Docker Compose Version**: (e.g. v2.30.x)
- **DNS Mode**: (`hosts`, `coredns`, or `cloudflare`)
- **TLS Mode**: (`internal`, `http-01`, or `cloudflare-dns01`)

---

## 📜 Logs & Proof

Relevant output from `./smoke_test.sh <SERVICE>` or `docker compose logs <service> --since=10m`:

```text
<paste logs or error tracebacks here>
```

---

## 💡 Additional Context

Add any other context about the problem here (e.g. custom GPU drivers, reverse-proxy setup, firewall rules).
