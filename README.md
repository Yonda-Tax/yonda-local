# yonda-local

Local development environment that emulates the shared AWS account used in the cloud. The stack is intentionally minimal today — LocalStack for AWS APIs, DynamoDB Admin for UI access, OpenSearch, and PostgreSQL — but is meant to grow with future infrastructure needs.

## Prerequisites

- Docker / Docker Compose v2
- [uv](https://github.com/astral-sh/uv) for Python dependency management
- Python 3.11+ (uv can provision it automatically)

## Usage

### Infrastructure

```bash
docker compose up -d
```

Services exposed locally:

- LocalStack edge: `http://localhost:4566`
- DynamoDB Admin UI: `http://localhost:8001`
- OpenSearch: `http://localhost:9200`
- PostgreSQL: `localhost:5432` (`yonda` / `yonda` / db `yonda_local`)

### Component Services

With the infrastructure up and running, it is time to deploy our services. Each of the below services must be deployed in the following order for the test suite to pass successfully.

#### Knox

1. Clone the [knox](https://github.com/Yonda-Tax/knox) repo
```
git clone git@github.com:Yonda-Tax/knox.git
```

2. Follow the setup instructions in the knox [README.md](https://github.com/Yonda-Tax/knox-ingestion/blob/main/README.md#setting-up-a-development-environment)

#### Knox Ingestion

1. Clone the [knox-ingestion](https://github.com/Yonda-Tax/knox-ingestion) repo
```
git clone git@github.com:Yonda-Tax/knox-ingestion.git
```

2. Follow the setup instructions in the knox-ingestion [README.md](https://github.com/Yonda-Tax/knox-ingestion/blob/main/README.md#setting-up-a-development-environment)


#### Alchemy


#### Heimdall


### Tests

Install dependencies and run pytest via uv:

```bash
uv sync
uv run pytest
```

The supplied smoke test is skipped by default. Provide a reachable service and opt-in via:

```bash
export YONDA_ENABLE_SMOKE=1
export YONDA_BASE_URL=http://localhost:8080  # customize if needed
uv run pytest -m smoke
```

`tests/conftest.py` exposes fixtures for the base URL, HTTP timeouts, and a shared `httpx.AsyncClient` so future integration tests can remain concise.

