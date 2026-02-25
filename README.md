# Sunbeam Cinder Factory

AI-powered scaffolding generator for OpenStack Sunbeam Cinder storage backend charms.

Given a driver spec YAML file, the factory calls the OpenAI API and produces a
complete, production-quality subordinate charm -- ready for `charmcraft pack`.

## Quick Start

```bash
# Install
uv sync

# Configure
cp env.example .env
# Edit .env and set OPENAI_API_KEY

# Generate a charm
python -m charm_generator generate dellsc.yaml

# Validate it
python -m charm_generator validate cinder-volume-dellsc --spec dellsc.yaml
```

## Project Layout

```
sunbeam-cinder-factory/
├── driver-specs/              # Driver specifications (one per vendor)
│   ├── sample.yaml            # Annotated template -- start here
│   ├── pure.yaml              # Pure Storage FlashArray
│   └── dellsc.yaml            # Dell SC Series
├── generated-charms/          # Output directory
│   └── cinder-volume-<vendor>/
├── charm_generator/           # Generator engine
│   ├── __main__.py            # CLI entry point
│   ├── generator.py           # Orchestrator
│   ├── prompts.py             # AI prompts + type override logic
│   ├── openai_client.py       # OpenAI API client
│   ├── validator.py           # Spec-based validation
│   ├── file_writer.py         # File output
│   └── settings.py            # Configuration
└── tests/
    └── test_*.py
```

## Adding a New Vendor

1. Copy the template and fill in your vendor details:

   ```bash
   cp driver-specs/sample.yaml driver-specs/myvendor.yaml
   ```

   The `sample.yaml` file documents every field with inline comments.
   The key sections are:

   | Section | Purpose |
   |---------|---------|
   | `vendor`, `display_name` | Identity and naming |
   | `protocols`, `driver_classes` | Cinder driver mapping |
   | `charm`, `relations` | Juju charm metadata |
   | `config_options` | All config fields for charmcraft.yaml and backend.py |
   | `type_overrides` | Fields needing special pydantic validation in charm.py |
   | `unsupported_driver` | Set `true` if driver needs `enable-unsupported-driver` |
   | `remove_base_config` | Base class config options to remove (e.g. `driver-ssl-cert`) |

2. Generate and validate:

   ```bash
   python -m charm_generator generate myvendor.yaml
   python -m charm_generator validate cinder-volume-myvendor --spec myvendor.yaml
   ```

## What Gets Generated

| File | Source | Purpose |
|------|--------|---------|
| `charmcraft.yaml` | `charm` + `relations` + `config_options` | Juju charm metadata and config declaration |
| `src/charm.py` | `type_overrides` + `config_options` | Operator charm with `_configuration_type_overrides()` |
| `backend/backend.py` | `config_options` | Sunbeam CLI plugin (Config class + Backend class) |
| `pyproject.toml` | `charm.name` | Python project metadata |
| `tests/unit/test_charm.py` | `config_options` | Unit test scaffolding |
| `README.md` | `charm.name` | Deployment docs |

The `charm.py` file intentionally has fewer fields than `config_options`.
Simple string/boolean/int fields work automatically from `charmcraft.yaml` at
runtime. Only fields listed in `type_overrides` (secrets, `Required`, `Literal`,
`RequiredIfGroup`, etc.) get explicit overrides in `_configuration_type_overrides()`.

## CLI Reference

```bash
# Generate a charm from a spec file
python -m charm_generator generate <spec-file> [--output-dir PATH] [--dry-run] [--model TEXT]

# Validate a generated charm (optionally against its spec)
python -m charm_generator validate <vendor> [--spec <spec-file>] [--json-output]

# List available driver specs
python -m charm_generator list-specs

# List generated charms
python -m charm_generator list-vendors

# Compare two generated charms
python -m charm_generator compare <vendor1> <vendor2>

# Delete a generated charm
python -m charm_generator clean <vendor> [--yes]

# Show configuration
python -m charm_generator info
```

## Configuration

Set via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | Model for generation |
| `OPENAI_MAX_TOKENS` | `16000` | Max response tokens |
| `OPENAI_TEMPERATURE` | `0.3` | Generation temperature |
| `OPENAI_API_TIMEOUT` | `120` | Request timeout (seconds) |
| `OPENAI_API_RETRY_ATTEMPTS` | `3` | Retry attempts |

## Development

```bash
# Run tests
uv run pytest tests/ -v

# With coverage
uv run pytest --cov=charm_generator tests/
```

## License

Apache License 2.0
