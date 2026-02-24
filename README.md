# Sunbeam Cinder Factory

**Charm and Snap Scaffolding Automation System for OpenStack Sunbeam**

This system automatically generates subordinate charms for OpenStack Cinder storage backends by reading structured driver specifications and using AI to produce production-quality scaffolding code.

## Features

- **AI-Powered Generation**: Uses OpenAI API to generate complete charm scaffolding
- **Multi-Protocol Support**: iSCSI, Fibre Channel, NVMe-oF
- **Vendor Extensibility**: Easy to add new storage vendors via spec files
- **Spec-Based Validation**: Validate generated charms against driver specifications
- **Reference Patterns**: Generated code follows the Pure Storage reference implementation
- **CLI Interface**: Full command-line tooling for generation and validation

## Project Structure

```
sunbeam-cinder-factory/
├── purestorage-reference/     # Pure Storage reference implementation
├── generated-charms/          # AI-generated vendor charms
│   └── cinder-volume-<vendor>/
├── driver-specs/              # Driver specifications (YAML)
│   ├── pure.yaml
│   └── hitachi.yaml
├── charm_generator/           # Core generation engine
│   ├── __init__.py
│   ├── __main__.py           # CLI entry point
│   ├── generator.py          # Main orchestrator
│   ├── openai_client.py      # API client with retries
│   ├── prompts.py            # AI prompt templates
│   ├── file_writer.py        # File output handling
│   ├── settings.py           # Global settings
│   └── validator.py          # Structure validation
├── tests/                    # Generator test suite
│   └── test_*.py
├── requirements.txt
├── env.example
└── README.md
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

```bash
cp env.example .env
# Edit .env and add your OpenAI API key
```

### 3. Generate a Charm

```bash
# Generate from Pure Storage spec
python -m charm_generator generate pure.yaml

# Generate Hitachi charm
python -m charm_generator generate hitachi.yaml

# Generate with custom output directory
python -m charm_generator generate pure.yaml -o ./my-output

# Dry run (show what would be generated)
python -m charm_generator generate pure.yaml --dry-run
```

### 4. Validate Generated Charm

```bash
# Validate structure
python -m charm_generator validate cinder-volume-hitachi

# Validate against driver spec
python -m charm_generator validate cinder-volume-hitachi --spec hitachi.yaml
```

## CLI Commands

### `generate`

Generate a charm from a driver specification.

```bash
python -m charm_generator generate <spec-file> [options]

Options:
  -o, --output-dir PATH       Output directory for generated charm
  --overwrite/--no-overwrite   Overwrite existing files (default: overwrite)
  --model TEXT                 OpenAI model to use
  --dry-run                    Show what would be generated
```

### `validate`

Validate a generated charm structure.

```bash
python -m charm_generator validate <vendor> [options]

Options:
  -s, --spec TEXT         YAML spec file to validate against
  --json-output           Output results as JSON
```

### `list-specs`

List available driver specification files.

```bash
python -m charm_generator list-specs
```

### `compare`

Compare two generated charms.

```bash
python -m charm_generator compare <vendor1> <vendor2> [--json-output]
```

### `list-vendors`

List all generated vendor charms.

```bash
python -m charm_generator list-vendors [--json-output]
```

### `info`

Show system configuration.

```bash
python -m charm_generator info
```

### `clean`

Delete a generated vendor charm.

```bash
python -m charm_generator clean <vendor> [--yes]
```

## Driver Specification Format

Driver specs define the storage backend and its configuration options.

```yaml
# Core fields
vendor: purestorage
display_name: Pure Storage FlashArray
description: Pure Storage FlashArray integration

# Supported protocols
protocols:
  - iscsi
  - fc
  - nvme

# High Availability
ha_enabled: true

# Driver class information
driver_class_base: cinder.volume.drivers.pure
driver_classes:
  iscsi: PureISCSIDriver
  fc: PureFCDriver
  nvme: PureNVMEDriver

# Configuration options
config_options:
  - name: san-ip
    type: string
    required: true
    description: Storage array management IP
    
  - name: api-token
    type: secret
    required: true
    description: API authentication token
    
  - name: iscsi-cidr
    type: string
    default: "0.0.0.0/0"
    protocol_specific: iscsi
    description: CIDR for iSCSI targets

# Feature flags
feature_flags:
  - name: enable_replication
    default: true
    description: Enable replication features
```

## Generated Charm Structure

Each generated charm includes:

| File | Purpose |
|------|---------|
| `charmcraft.yaml` | Charm metadata, config options, relations |
| `src/charm.py` | Main charm operator class |
| `backend/backend.py` | Sunbeam CLI backend plugin |
| `backend/__init__.py` | Python package marker |
| `pyproject.toml` | Python project configuration |
| `README.md` | Deployment documentation |
| `tests/unit/test_charm.py` | Unit test scaffolding |
| `tests/unit/__init__.py` | Python package marker |

## Configuration

Settings can be configured via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | Model for generation |
| `OPENAI_MAX_TOKENS` | `16000` | Max response tokens |
| `OPENAI_TEMPERATURE` | `0.3` | Generation temperature |
| `OPENAI_API_TIMEOUT` | `120` | Request timeout (seconds) |
| `OPENAI_API_RETRY_ATTEMPTS` | `3` | Number of API retry attempts |

## Adding a New Vendor

1. Create a driver spec file in `driver-specs/`:
   ```bash
   cp driver-specs/hitachi.yaml driver-specs/newvendor.yaml
   ```

2. Edit the spec with vendor-specific details

3. Generate the charm:
   ```bash
   python -m charm_generator generate newvendor.yaml
   ```

4. Validate the output:
   ```bash
   python -m charm_generator validate cinder-volume-newvendor --spec newvendor.yaml
   ```

## Architecture

```
┌─────────────────────┐
│   Driver Spec       │
│   (YAML)            │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   CLI Interface     │
│   (__main__.py)     │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   Generator Core    │
│   (generator.py)    │
├─────────────────────┤
│ • Load spec         │
│ • Build prompts     │
│ • Call API          │
│ • Write files       │
└─────────┬───────────┘
          │
    ┌─────┴─────┐
    ▼           ▼
┌────────┐  ┌────────┐
│Prompts │  │OpenAI  │
│Builder │  │Client  │
└────────┘  └────────┘
          │
          ▼
┌─────────────────────┐
│   File Writer       │
│   (file_writer.py)  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Generated Charm    │
│  (vendor folder)    │
└─────────────────────┘
```

## Metrics

The system tracks generation metrics including:

- Generation duration
- API token usage
- Files generated per vendor

Metrics are returned in the `GenerationResult` object:

```python
from charm_generator.generator import CharmGenerator

generator = CharmGenerator()
result = generator.generate("pure.yaml")
print(f"Duration: {result.duration_seconds:.2f}s")
print(f"Tokens used: {result.tokens_used}")
print(f"Files generated: {result.files_generated}")
```

## Development

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-cov

# Run generator tests
pytest tests/

# With coverage
pytest --cov=charm_generator tests/

# Validate a generated charm against its spec
python -m charm_generator validate cinder-volume-purestorage --spec pure.yaml
```

### Code Quality

```bash
# Install linting tools
pip install black ruff

# Format code
black .

# Lint
ruff check .
```

## License

Apache License 2.0

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## Reference Implementation

The Pure Storage charm in `purestorage-reference/` serves as the canonical
example for generated charms. All AI-generated charms follow its patterns
for structure, naming conventions, and code style.

