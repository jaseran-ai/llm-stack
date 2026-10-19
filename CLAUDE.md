# Claude Code Guidelines — `llm-stack`

All development and operations in this repository are governed by the authoritative rules defined in [`AGENTS.md`](./AGENTS.md).

## Quick Reference Summary

1. **CAB Protocol Before Changes**: Always perform a Change Advisory Board (CAB) impact analysis before touching code, configs, or running containers. Never restart `litellm` without explicit user permission.
2. **Zero-Downtime Hot-Reload Rule**: If modifying a host file that is hot-reloaded by a running container to reference a new dependency (e.g. `include:`), use `docker cp` to inject the dependency into the container BEFORE modifying the host file.
3. **No Unilateral Changes**: Always propose changes and obtain explicit approval from the user before executing.
4. **Everything as Code & No Hardcoded Secrets**: Secrets are generated in `setup.sh` and managed in Vault (`vault/secrets_ram/`). Never use fallback defaults like `${VAR:-default}` in `docker-compose.yml`.
5. **Empirical Proof**: Always verify changes with `python3 scripts/smoke_test.py`, `curl`, and `docker compose logs <service> --since=30s`.
6. **Adding Applications**: Follow the 7-step procedure in [`ADDING_AN_APPLICATION.md`](./ADDING_AN_APPLICATION.md).
7. **Read Official Docs & Investigate Edge-Cases**: ALWAYS read version-matched official documentation and research edge-cases (WebSockets, CORS, headers, auth quirks) BEFORE implementing any service or configuration.
8. **Code & Docs in English**: All public documentation, comments, and commit messages must be in English. Use Conventional Commits (`feat:`, `fix:`, `docs:`).

For full architectural invariants and governance rules, read [`AGENTS.md`](./AGENTS.md).
