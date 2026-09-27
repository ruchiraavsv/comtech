# Deployment preparation

The images are deployable, but the mock scaffold has no authentication, per-user
authorization, or rate limiting. Complete those assessment features before public
exposure. No hosting resources are provisioned by these files.

## Preferred: GitHub to Railway

Railway builds and stores container images from our Dockerfile. No Docker Hub,
GHCR account, or local Docker installation is needed.

1. Connect the source repository. Create separate API and UI services with build
   context at repository root. Set service variable `APP_TARGET=api` or
   `APP_TARGET=ui` respectively. The Dockerfile declares this build argument and
   selects the matching runtime stage; the default is `api`.
2. Add a Postgres service with persistent storage. Supply its private connection
   URL as API `DATABASE_URL`; use a direct session connection, not transaction
   pooling, because the API holds a session-level advisory lock.
3. Run `python -m comtech.migrate` as the API pre-deploy command. Keep one replica
   and one worker, and stop the old instance before starting its replacement.
   The singleton database lock intentionally rejects overlapping API processes;
   this scaffold does not support zero-downtime rolling replacement. Remove the
   active API deployment before deploying the replacement. Merely setting
   overlap seconds to zero does not stop the old process before the new process
   becomes healthy. Set `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=20` for shutdown.
4. Supply API runtime secrets/config from `.env.remote.example`, omitting the
   Compose-only Postgres bootstrap variables and `PUBLIC_DOMAIN`. Use production
   mode, hosted Pinecone, and enabled LangSmith tracing for the demo.
5. Set UI `API_BASE_URL` to the API's private hostname and configured port. Both
   start commands honor `PORT`; API also honors `HOST` (set `::` if the private
   network requires IPv6). Provider keys belong only to the API service.
6. Give only the UI a public Railway HTTPS domain. Configure API readiness at
   `/health/ready` and UI health at `/_stcore/health` on their respective ports.
7. Verify live activity, Streamlit browser connectivity, cursor replay, persistent
   data after redeploy, LangSmith traces, and hosted Pinecone connectivity.

Use platform resource limits and billing controls. Budget from measured memory,
CPU and storage usage rather than assuming a fixed total. Arrange database backup
and restore verification separately; a persistent volume alone is not a backup.

Compose remains our local orchestration. Railway runs equivalent services using
the same Dockerfile, not necessarily the Compose file itself.

## Alternative: remote Linux host using Compose

Copy `.env.remote.example` to `.env.remote`, fill in unique database credentials,
the database URL, provider secrets, and a DNS name pointing to the host. Keep this
file private and out of Git. The `.env.remote` file must contain complete values;
Compose interpolation and container environment use it explicitly:

```sh
export APP_ENV_FILE=.env.remote
docker compose --env-file .env.remote -f compose.yaml -f compose.remote.yaml config --quiet
docker compose --env-file .env.remote -f compose.yaml -f compose.remote.yaml up --build -d
```

Only Caddy publishes ports 80/443; it obtains TLS certificates for `PUBLIC_DOMAIN`
and proxies Streamlit with immediate flushing. API and Postgres stay on the
container network. There are no development source mounts or reload processes.
Do not activate `vector-test` on this host.

Check host firewall/DNS, HTTPS issuance, upstream streaming, graceful shutdown,
and backup restoration on the actual host. Preserve Postgres/Caddy volumes across
deployments. Database migrations are run by the one-shot `migrate` service.

Publishing images to GHCR can be added later if CI-built artifacts are preferred.
Use immutable tags/digests when introducing that workflow.

Reference: https://docs.railway.com/guides/docker-compose
Build arguments: https://docs.railway.com/builds/dockerfiles
Deployment lifecycle: https://docs.railway.com/deployments/deployment-teardown
