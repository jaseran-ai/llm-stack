# Installation & First Boot

Follow these instructions to deploy a fully functional LLM Stack on your machine.

---

## Prerequisites

Before beginning, ensure your environment meets the minimum requirements:
* **Operating System**: Linux (Ubuntu 22.04+, Debian 12+, Fedora, or equivalent).
* **Hardware**:
  * Minimum: 4 CPU cores, 16 GB RAM, 30 GB free storage.
  * Recommended for heavy local inference: 8+ CPU cores, 32 GB RAM, or NVIDIA GPU with `nvidia-container-toolkit`.
* **Software**:
  * **Docker Engine** (version 24.0 or newer).
  * **Docker Compose** (v2.20 or newer).
  * **OpenSSL** (for dynamic secret generation).

---

## Installation

The entire platform is deployed using the automated setup script.

1. Clone the repository and navigate into the project directory:
   ```bash
   git clone https://github.com/jaseran-ai/llm-stack.git
   cd llm-stack
   ```

2. Run the initialization script:
   ```bash
   ./setup.sh
   ```

   `setup.sh` automatically performs the following tasks:
   * Generates cryptographically secure random passwords and secrets using `openssl rand -hex 32`.
   * Provisions HashiCorp Vault KV v2 storage and configures AppRole authentication.
   * Generates a 10-year internal Certificate Authority and SAN TLS certificate.
   * Renders environment files into an in-memory volatile `tmpfs` volume (`/vault/secrets_ram`).
   * Starts all core containers in the correct dependency order.

3. Verify stack health:
   ```bash
   ./smoke_test.sh
   ```
   All 28 automated test suites should report `[OK]`.

---

## First Login

Once the stack is running, access the central application portal:
* **URL**: `https://authentik.${DOMAIN}` (or `http://localhost:9000` locally).
* **Username**: `admin`
* **Password**: Generated dynamically in `setup.sh` and displayed at the conclusion of initialization.

From the Authentik Application Dashboard, you can launch:
* **Open WebUI**: Interactive chat and RAG knowledge bases.
* **Grafana**: Real-time observability and container metrics.
* **Langfuse**: LLMOps prompt traces and execution graphs.
* **Dozzle**: Container logs viewer.
