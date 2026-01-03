Text to CAD design
====================

<img src="index.png" alt="repo representation" width="500">

# Setup virtual environment
- Install `uv`: `curl -LsSf https://astral.sh/uv/install.sh | sh`

```commandline
uv venv
source .venv/bin/activate
uv sync
```

## Install dependencies from a group

- install from `dev` block

```commandline
uv sync --dev
```

- install from different group

```commandline
uv sync --group group_name
```

## Add dependency to group

- `dev`

```commandline
uv add --dev package_name
```

- create a new group

```commandline
uv add --goup group_name ruff
```