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

1. Clone the [alchemy](https://github.com/Yonda-Tax/alchemy) repo
```
git clone git@github.com:Yonda-Tax/alchemy.git
```

2. Follow the setup instructions in the alchemy [README.md](https://github.com/Yonda-Tax/alchemy/blob/main/README.md#setting-up-a-development-environment)


#### Heimdall

1. Clone the [alchemy](https://github.com/Yonda-Tax/heimdall) repo
```
git clone git@github.com:Yonda-Tax/heimdall.git
```

2. Follow the setup instructions in the heimdall [README.md](https://github.com/Yonda-Tax/heimdall/blob/main/README.md#setting-up-a-development-environment)


### Tests

To run the tests, first set up a python environment and install dependencies and run pytest via uv:

```bash
uv venv -p 3.13 --clear
. .venv/bin/activate
uv sync
uv pip install -e .
```

To validate that all the component services are up and running, you can just run the smoke tests:
```bash
export $(grep -v '^#' tests/local.env | xargs)
uv run pytest -m smoke
```

Run all the tests with:
```bash
export $(grep -v '^#' tests/local.env | xargs)
uv run pytest
```

Or just the integration tests with:
```bash
export $(grep -v '^#' tests/local.env | xargs)
uv run pytest -m incremental
```

To run against dev or prod environments, export credentials from the [AWS Access Portal](https://d-9c67596e31.awsapps.com/start/#/) for the respective
account then export the relevant .env file.

Running against production should only be done in exceptional circumstances. Speak to another member of the team before embarking on this path.
```bash
# For dev
export $(grep -v '^#' tests/dev.env | xargs)
uv run pytest -m smoke
# For prod
export $(grep -v '^#' tests/prod.env | xargs)
uv run pytest -m smoke
```