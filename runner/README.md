# Containerized GitHub Actions Runner

The repository uses the unmodified, version-pinned `myoung34/github-runner` image. CI tools run
in isolated job containers; no package is installed in the runner image or on the host.

## Docker-outside-of-Docker path contract

The runner accesses the host Docker daemon through `/var/run/docker.sock`. When GitHub starts a
job container, it asks that daemon to mount the runner's `externals` directory at `/__e`. JavaScript
actions such as `actions/checkout` execute the bundled Node runtime from that mount.

Container paths passed to the host daemon must also exist on the host. An `externals` directory
that exists only in the runner container therefore produces errors such as
`/__e/node24/bin/node: no such file or directory`.

`runner-files-init` solves this declaratively without a custom image:

1. it copies the files from the pinned runner image to the host path `/actions-runner`;
2. it verifies that the bundled Node 24 executable exists;
3. `gh-actions-runner` starts only after that one-shot service succeeds;
4. the runner bind-mounts the same `/actions-runner` path, so sibling job containers receive a
   valid read-only `/__e` mount from the host daemon.

The work directory follows the same identity rule: `/tmp/runner/work` is mounted at the identical
path on the host and in the runner. The `runner_data` volume preserves registration and runner
state across recreations.

## Lifecycle

Obtain a short-lived repository runner registration token, then run:

```bash
./scripts/setup_runner.sh "${RUNNER_TOKEN}"
```

The script recreates only the runner Compose project. It waits for the init service, verifies the
Node 24 bridge on both sides of the bind mount, and then reports success. It does not interact with
the application Compose project.

Validate the topology without starting it:

```bash
make runner-compose-validate
```

## Rollback

Revert the runner configuration commit and run `scripts/setup_runner.sh` again with a fresh
registration token. The named `runner_data` volume is not removed. Do not use `docker compose
down --volumes` for the runner project.
