## 📌 Summary

Briefly describe the purpose and scope of this pull request.

---

## 🔗 Related Issues

Closes #<issue_number>
Refs #<issue_number>

---

## 🏷️ Type of Change

- [ ] `feat`: New feature or capability
- [ ] `fix`: Bug fix
- [ ] `security`: Security enhancement or vulnerability remediation
- [ ] `docs`: Documentation updates or additions
- [ ] `refactor`: Code refactoring without behavior change
- [ ] `chore`: Build, tooling, CI, or dependency updates

---

## 📋 Quality Gate & Verification Checklist

Before submitting, please ensure you have verified the following:

- [ ] **Empirical Validation**: Ran `./smoke_test.sh` or targeted service verification with raw output.
- [ ] **Linters & CI Quality Gate**: Ran `make lint` locally and all checks passed (shellcheck, yamllint, no-french, markdown-links, Gitleaks).
- [ ] **Zero Hardcoded Secrets**: No plaintext passwords or tokens in code or compose files (all secrets generated in `setup.sh` and managed in Vault).
- [ ] **Multi-Arch Pinned Tags**: Container images are explicitly pinned with exact tags/digests (never `:latest`).
- [ ] **Zero Unilateral Restarts**: No disruptions to core gateway services (e.g. `litellm`) without prior CAB alignment.
