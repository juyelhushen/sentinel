# Local Observability Stack

This directory runs Prometheus and Grafana locally with Docker Compose. Both
web interfaces bind only to `127.0.0.1`. Prometheus scrapes the deployed
Sentinel API over HTTPS every 15 seconds using the locally supplied API key.

## Prerequisites and Secrets

Use Docker Desktop with Linux containers and Docker Compose. From PowerShell at
the repository root, create the ignored secrets directory and open the API-key
file in Notepad:

```powershell
New-Item -ItemType Directory -Force observability/local/secrets
notepad observability/local/secrets/sentinel_api_key.txt
```

Enter your existing Sentinel API key in that local file and save it. Do not
paste the key into a command, chat, or tracked file. Docker Compose mounts it as
a read-only secret at `/run/secrets/sentinel_api_key.txt`; Prometheus reads the
header value from that file and trims surrounding whitespace.

Create the ignored Grafana environment file in Notepad:

```powershell
notepad observability/local/.env
```

Add a `GRAFANA_ADMIN_PASSWORD` assignment with a strong, locally chosen
password, then save the file. `.env` and the entire `secrets/` directory are
excluded by this directory's `.gitignore`.

## Start and Verify

Run the following from `observability/local`:

```powershell
docker compose up -d
docker compose ps
```

Confirm Prometheus responds at `http://localhost:9090/-/healthy`, then open
`http://localhost:9090/targets`. After a scrape attempt, the `sentinel` target
should show `UP`. This setup does not assert target health before you run it.

Open Grafana at `http://localhost:3000` and sign in as `admin` using the
password from `.env`. In **Connections > Data sources**, the provisioned
Prometheus datasource should be healthy. Prometheus and Grafana data are stored
in named Docker volumes and survive container restarts.

## Stop

From `observability/local`, stop and remove the containers without deleting
stored metrics or Grafana state:

```powershell
docker compose down
```

Do not add `--volumes`/`-v` unless you intend to delete both named data volumes.

## Troubleshooting

- **401/authentication failure:** Check that the local API-key file contains
  the correct existing key, without quotes. If you rotate it, update the file
  and restart Prometheus with `docker compose restart prometheus`. Never print
  or paste the key when troubleshooting.
- **Scrape timeout:** Prometheus allows 10 seconds per scrape. Check Render
  service latency and network access. A target taking longer than the timeout
  will be marked down for that scrape; do not increase the timeout above the
  15-second scrape interval.
- **Render service unavailable:** Check the deployed service's availability in
  Render and retry after it responds again. Prometheus will keep retrying on
  subsequent intervals; prior time series remain in the named volume.
- **Compose reports a missing secret or password:** Create both local files as
  described above before starting the stack. Do not share their contents or
  command output containing environment values.