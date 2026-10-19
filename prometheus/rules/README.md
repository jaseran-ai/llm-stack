# Prometheus Alerting Rules & Incidents Guide

This folder contains declarative Prometheus alerting rules for the **`llm-stack`** platform.

Alerts are evaluated continuously by Prometheus every 15 seconds and forwarded directly to **Alertmanager** when trigger conditions are met.

---

## 📋 Alert Catalog by Subsystem

### 1. 🖥️ Core Infrastructure & Host Health (`stack_infrastructure`)

| Alert Name | Severity | Threshold / Duration | Actionable Remediation |
| :--- | :---: | :--- | :--- |
| **`ServiceDown`** | `critical` | `up == 0` for 1m | Check `docker compose ps` and logs of the failing service (`docker compose logs <service>`). |
| **`ContainerCrashLooping`** | `critical` | Restart rate $> 0.01$ for 2m | Inspect container crash logs or OOM kill events (`dmesg -T \| grep -i oom`). |
| **`ContainerHighMemoryWorkingSet`** | `warning` | Working set $> 90\%$ for 3m | Assess workload or increase memory limits in `docker-compose.yml`. |
| **`HostDiskFillingUp`** | `warning` | Free space $< 15\%$ for 5m | Prune unused Docker images (`docker system prune -a`) or clean logs. |
| **`HostHighCPU`** | `warning` | Host CPU $> 90\%$ for 10m | Identify CPU-intensive process via `top` or cAdvisor dashboard. |

---

### 2. 🏎️ LLM Inference & Remote GPU Backend (`llm_inference_backend`)

| Alert Name | Severity | Threshold / Duration | Actionable Remediation |
| :--- | :---: | :--- | :--- |
| **`LlamaServerOffline`** | `critical` | `up{job="llama-server"} == 0` for 1m | Check GPU node connectivity or restart `llama-server` process on the GPU node. |
| **`LlamaServerQueueOverflow`** | `warning` | `requests_deferred > 0` for 2m | Inferences are waiting for slots. Consider increasing `--parallel` / batch slots or scaling back concurrency. |

---

### 3. 🤖 LLM Gateway & API Spend (`llm_gateway`)

| Alert Name | Severity | Threshold / Duration | Actionable Remediation |
| :--- | :---: | :--- | :--- |
| **`LiteLLMHighErrorRate`** | `warning` | Failed requests $> 10\%$ for 3m | Check upstream LLM backend errors and LiteLLM logs in Grafana. |
| **`LiteLLMBudgetDepleted`** | `warning` | Remaining budget $\le 0$ for 1m | Top up or reset the API key spend budget via LiteLLM Admin UI. |

---

### 4. 🚦 Reverse Proxy & Ingress (`ingress_and_routing`)

| Alert Name | Severity | Threshold / Duration | Actionable Remediation |
| :--- | :---: | :--- | :--- |
| **`TraefikHigh5xxErrorRate`** | `warning` | 5xx errors $> 5\%$ for 3m | Inspect Traefik routing logs in Grafana to pinpoint backend failures. |

---

### 5. 🛡️ Security, Identity & SSO (`security_and_identity`)

| Alert Name | Severity | Threshold / Duration | Actionable Remediation |
| :--- | :---: | :--- | :--- |
| **`AuthentikOutpostDisconnected`** | `critical` | Outposts $= 0$ for 1m | Check `authentik-server` health and embedded outpost communication. |
| **`AuthentikWorkerDown`** | `critical` | Workers $= 0$ for 2m | Restart `authentik-worker` (`docker compose restart authentik-worker`). |
| **`AuthentikBruteForceAttempt`** | `warning` | $> 5$ 401/403 req/s for 1m | Inspect source IPs in Traefik / Cloudflare Zero Trust and ban malicious clients. |

---

### 6. 🗄️ Vector Database & RAG Storage (`vector_storage`)

| Alert Name | Severity | Threshold / Duration | Actionable Remediation |
| :--- | :---: | :--- | :--- |
| **`QdrantOffline`** | `critical` | `up{job="qdrant"} == 0` for 1m | Check Qdrant container logs and storage volumes (`qdrant_data`). |

---

## 📱 Notification Channels

Alertmanager ships with a single `default-receiver` and no notification integration: firing alerts are visible in the Alertmanager UI (`https://alertmanager.${DOMAIN}`) and in Grafana. To be notified, add a receiver (email, chat webhook, generic webhook, ...) and a route in [`../alertmanager.yml`](../alertmanager.yml), following the [Alertmanager receiver documentation](https://prometheus.io/docs/alerting/latest/configuration/#receiver). Routing only `severity: critical` alerts to a paging channel keeps notification fatigue low.

---

## 🔧 Managing & Adding Alert Rules

1. **Add new rules** in [`alerts.yml`](alerts.yml).
2. **Reload Prometheus on the fly** without restarting:
   ```bash
   curl -X POST http://127.0.0.1:9190/-/reload
   ```
3. **Verify rule syntax and active state**:
   ```bash
   curl -s http://127.0.0.1:9190/api/v1/rules | jq '.data.groups[].rules[].name'
   ```
