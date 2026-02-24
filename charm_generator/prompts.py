"""AI prompt templates for charm generation.

All Pure Storage reference code is embedded here - no external files needed at runtime.
"""

import json
from typing import Any


# =============================================================================
# Embedded Reference Templates (Production-ready, no external files needed)
# =============================================================================

REFERENCE_BACKEND_PY = '''# SPDX-FileCopyrightText: 2025 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Pure Storage FlashArray backend implementation using base step classes."""

import logging
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field
from rich.console import Console

from sunbeam.core.manifest import StorageBackendConfig
from sunbeam.storage.base import StorageBackendBase
from sunbeam.storage.models import SecretDictField

LOG = logging.getLogger(__name__)
console = Console()


class Personality(StrEnum):
    """Enumeration of valid host personality types."""

    AIX = "aix"
    ESXI = "esxi"
    HITACHI_VSP = "hitachi-vsp"
    HPUX = "hpux"
    ORACLE_VM_SERVER = "oracle-vm-server"
    SOLARIS = "solaris"
    VMS = "vms"


class PureStorageConfig(StorageBackendConfig):
    """Configuration model for Pure Storage FlashArray backend.

    This model includes the essential configuration options for deploying
    a Pure Storage backend. Additional configuration can be managed dynamically
    through the charm configuration system.
    """

    # Mandatory connection parameters
    san_ip: Annotated[
        str, Field(description="Pure Storage FlashArray management IP or hostname")
    ]
    pure_api_token: Annotated[
        str,
        Field(description="REST API authorization token from FlashArray"),
        SecretDictField(field="token"),
    ]

    # Optional backend configuration
    protocol: Annotated[
        Literal["iscsi", "fc", "nvme"] | None,
        Field(description="Pure Storage protocol (iscsi, fc, nvme)"),
    ] = None
    
    # Protocol-specific options
    pure_iscsi_cidr: Annotated[
        str | None,
        Field(description="CIDR of FlashArray iSCSI targets hosts can connect to"),
    ] = None
    pure_iscsi_cidr_list: Annotated[
        str | None,
        Field(description="Comma-separated list of CIDR for iSCSI targets"),
    ] = None
    pure_nvme_cidr: Annotated[
        str | None,
        Field(description="CIDR of FlashArray NVMe targets hosts can connect to"),
    ] = None
    pure_nvme_cidr_list: Annotated[
        str | None,
        Field(description="Comma-separated list of CIDR for NVMe targets"),
    ] = None
    pure_nvme_transport: Annotated[
        Literal["tcp"] | None,
        Field(description="NVMe transport layer"),
    ] = None

    # Host and protocol tuning
    pure_host_personality: Annotated[
        Personality | None, Field(description="Host personality for protocol tuning")
    ] = None

    # Storage management
    pure_automatic_max_oversubscription_ratio: Annotated[
        bool | None,
        Field(description="Automatically determine oversubscription ratio"),
    ] = None
    pure_eradicate_on_delete: Annotated[
        bool | None,
        Field(description="Immediately eradicate volumes on delete (WARNING: not recoverable)"),
    ] = None

    # Replication settings
    pure_replica_interval_default: Annotated[
        int | None, Field(description="Snapshot replication interval in seconds")
    ] = None
    pure_replica_retention_short_term_default: Annotated[
        int | None,
        Field(description="Retain all snapshots on target for this time (seconds)"),
    ] = None
    pure_replica_retention_long_term_per_day_default: Annotated[
        int | None, Field(description="Retain how many snapshots for each day")
    ] = None
    pure_replica_retention_long_term_default: Annotated[
        int | None,
        Field(description="Retain snapshots per day on target for this time (days)"),
    ] = None
    pure_replication_pg_name: Annotated[
        str | None,
        Field(description="Pure Protection Group name for async replication"),
    ] = None
    pure_replication_pod_name: Annotated[
        str | None,
        Field(description="Pure Pod name for sync replication"),
    ] = None

    # Advanced replication
    pure_trisync_enabled: Annotated[
        bool | None,
        Field(description="Enable 3-site replication (sync + async)"),
    ] = None
    pure_trisync_pg_name: Annotated[
        str | None,
        Field(description="Protection Group name for trisync replication"),
    ] = None

    # SSL and security
    driver_ssl_cert: Annotated[
        str | None, Field(description="SSL certificate content in PEM format")
    ] = None

    # Performance options
    use_multipath_for_image_xfer: Annotated[
        bool | None,
        Field(description="Enable multipathing for image transfer operations"),
    ] = None


class PureStorageBackend(StorageBackendBase):
    """Pure Storage FlashArray backend implementation."""

    backend_type = "purestorage"
    display_name = "Pure Storage FlashArray"
    generally_available = True

    @property
    def charm_name(self) -> str:
        """Return the charm name for this backend."""
        return "cinder-volume-purestorage"

    @property
    def charm_channel(self) -> str:
        """Return the charm channel for this backend."""
        return "latest/edge"

    @property
    def charm_revision(self) -> str | None:
        """Return the charm revision for this backend."""
        return None

    @property
    def charm_base(self) -> str:
        """Return the charm base for this backend."""
        return "ubuntu@24.04"

    @property
    def supports_ha(self) -> bool:
        """Return whether this backend supports HA deployments."""
        return True

    def config_type(self) -> type[StorageBackendConfig]:
        """Return the configuration class for Pure Storage backend."""
        return PureStorageConfig
'''

REFERENCE_CHARM_PY = '''#!/usr/bin/env python3

#
# Copyright 2025 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Cinder purestorage Operator Charm.

This charm provide Cinder <-> purestorage integration as part
of an OpenStack deployment
"""

import ipaddress
import logging
from enum import (
    StrEnum,
)
import typing

import ops
import ops_sunbeam.charm as charm
import ops_sunbeam.storage as sunbeam_storage
import ops_sunbeam.tracing as sunbeam_tracing
import pydantic

logger = logging.getLogger(__name__)


class NvmeTransport(StrEnum):
    """Enumeration of valid NVMe transport types."""

    TCP = "tcp"


class Personality(StrEnum):
    """Enumeration of valid host personality types."""

    AIX = "aix"
    ESXI = "esxi"
    HITACHI_VSP = "hitachi-vsp"
    HPUX = "hpux"
    ORACLE_VM_SERVER = "oracle-vm-server"
    SOLARIS = "solaris"
    VMS = "vms"


def ip_network_list_validator(value: str) -> list[pydantic.IPvAnyNetwork]:
    """Validate and parse a comma-separated list of IP networks."""
    if not value:
        raise ValueError("Value cannot be empty")
    try:
        return [ipaddress.ip_network(ip.strip()) for ip in value.split(",")]
    except ValueError as e:
        raise ValueError(f"Invalid IP network: {e}")


def list_serializer(value: list) -> str:
    """Serialize a list to a comma-separated string."""
    return ",".join(str(v) for v in value)


CIDR_LIST_TYPING = typing.Annotated[
    list[pydantic.IPvAnyNetwork] | None,
    pydantic.BeforeValidator(ip_network_list_validator),
    pydantic.PlainSerializer(list_serializer, return_type=str),
]


@sunbeam_tracing.trace_sunbeam_charm
class CinderVolumePureStorageOperatorCharm(charm.OSCinderVolumeDriverOperatorCharm):
    """Cinder/PureStorage Operator charm."""

    service_name = "cinder-volume-purestorage"

    @property
    def backend_key(self) -> str:
        """Return the backend key."""
        return "pure." + self.model.app.name

    def _configuration_type_overrides(self) -> dict[str, typing.Any]:
        """Configuration type overrides for pydantic model generation."""
        overrides = super()._configuration_type_overrides()
        overrides.update(
            {
                "pure-api-token": typing.Annotated[
                    str,
                    pydantic.BeforeValidator(sunbeam_storage.secret_validator("token")),
                    sunbeam_storage.Required,
                ],
                "pure-host-personality": Personality | None,
                "pure-iscsi-cidr": pydantic.IPvAnyNetwork | None,
                "pure-iscsi-cidr-list": CIDR_LIST_TYPING,
                "pure-nvme-cidr": pydantic.IPvAnyNetwork | None,
                "pure-nvme-cidr-list": CIDR_LIST_TYPING,
                "pure-nvme-transport": NvmeTransport,
            }
        )
        return overrides


if __name__ == "__main__":  # pragma: nocover
    ops.main(CinderVolumePureStorageOperatorCharm)
'''


# =============================================================================
# System Prompt - Comprehensive Generation Instructions
# =============================================================================

SYSTEM_PROMPT = """You are an expert OpenStack Charm developer. Generate Sunbeam Cinder storage backend components that EXACTLY follow these patterns.

## OUTPUT FORMAT (Critical)

Return a valid JSON object. Keys are file paths, values are complete file contents:
```json
{
  "backend/backend.py": "...",
  "backend/__init__.py": "",
  "charmcraft.yaml": "...",
  "src/charm.py": "...",
  "pyproject.toml": "...",
  "README.md": "...",
  "tests/unit/__init__.py": "",
  "tests/unit/test_charm.py": "..."
}
```

## ARCHITECTURE: Two Components

### Component 1: backend/backend.py (Sunbeam CLI Plugin)

This file enables `sunbeam` CLI to discover and configure the storage backend.

**CRITICAL**: Include ALL config options from the driver spec in the Config class,
not just CLI-prompted ones. The `cli_prompt` field only indicates which fields
are interactively prompted in the CLI wizard - ALL fields must exist in the Config class.

**Field Naming Convention**: Convert hyphenated YAML names to snake_case Python attributes:
- `pure-api-token` → `pure_api_token`
- `san-ip` → `san_ip`
- `pure-host-personality` → `pure_host_personality`
- `pure-iscsi-cidr` → `pure_iscsi_cidr`

**Required Structure:**
```python
# SPDX-FileCopyrightText: 2025 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

\"\"\"Vendor backend implementation using base step classes.\"""

import logging
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field
from rich.console import Console

from sunbeam.core.manifest import StorageBackendConfig
from sunbeam.storage.base import StorageBackendBase
from sunbeam.storage.models import SecretDictField

LOG = logging.getLogger(__name__)
console = Console()


# StrEnum classes for enum options that need validation
class Personality(StrEnum):
    \"\"\"Enumeration of valid host personality types.\"""
    AIX = "aix"
    ESXI = "esxi"
    # ... all values from spec


class {VendorPascal}Config(StorageBackendConfig):
    \"\"\"Configuration model for {VendorDisplay} backend.

    This model includes ALL configuration options for the backend.
    Additional configuration can be managed dynamically through the charm.
    \"\"\"

    # Mandatory connection parameters (required: true in spec)
    san_ip: Annotated[
        str, Field(description="Management IP or hostname")
    ]
    {vendor_lower}_api_token: Annotated[
        str,
        Field(description="REST API authorization token"),
        SecretDictField(field="token"),
    ]

    # Optional backend configuration (required: false in spec)
    protocol: Annotated[
        Literal["iscsi", "fc", "nvme"] | None,
        Field(description="Protocol selector"),
    ] = None
    
    # Protocol-specific options
    {vendor_lower}_iscsi_cidr: Annotated[
        str | None,
        Field(description="CIDR of iSCSI targets"),
    ] = None
    
    # Host and protocol tuning
    {vendor_lower}_host_personality: Annotated[
        Personality | None, Field(description="Host personality for protocol tuning")
    ] = None
    
    # Storage management options
    {vendor_lower}_eradicate_on_delete: Annotated[
        bool | None,
        Field(description="Immediately eradicate volumes on delete"),
    ] = None
    
    # ... ALL other config options from spec with defaults


class {VendorPascal}Backend(StorageBackendBase):
    \"\"\"{VendorDisplay} backend implementation.\"""

    backend_type = "{vendor_lower}"
    display_name = "{VendorDisplay}"
    generally_available = True

    @property
    def charm_name(self) -> str:
        return "cinder-volume-{vendor_lower}"

    @property
    def charm_channel(self) -> str:
        return "latest/edge"

    @property
    def charm_revision(self) -> str | None:
        return None

    @property
    def charm_base(self) -> str:
        return "ubuntu@24.04"

    @property
    def supports_ha(self) -> bool:
        return True  # or False from spec

    def config_type(self) -> type[StorageBackendConfig]:
        return {VendorPascal}Config
```

**Key Rules for backend.py:**
- SPDX header with BOTH `FileCopyrightText` and `License-Identifier` lines
- Include ALL config fields from the spec, not just `cli_prompt: true` ones
- Do NOT include `volume-backend-name` or `backend-availability-zone` (handled by StorageBackendConfig base class)
- ALL optional fields MUST default to `= None` (let Cinder handle actual defaults)
- Use `Literal[...] | None` for simple enums like protocol in the Config class
- Use StrEnum classes only for vendor-prefixed enum fields that need validation (e.g., Personality)
- Use `SecretDictField(field="{key}")` for secrets

### Component 2: src/charm.py (Juju Operator)

This file is the actual Juju charm that configures Cinder.

**Required Structure:**
```python
#!/usr/bin/env python3

#
# Copyright 2025 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

\"\"\"Cinder {vendor} Operator Charm.

This charm provide Cinder <-> {vendor} integration as part
of an OpenStack deployment
\"\"\"

import ipaddress
import logging
from enum import (
    StrEnum,
)
import typing

import ops
import ops_sunbeam.charm as charm
import ops_sunbeam.storage as sunbeam_storage
import ops_sunbeam.tracing as sunbeam_tracing
import pydantic

logger = logging.getLogger(__name__)


# StrEnum classes for enum options
class SomeOption(StrEnum):
    \"\"\"Valid options.\"""
    VALUE_A = "value-a"


# CIDR list utilities (only if needed)
def ip_network_list_validator(value: str) -> list[pydantic.IPvAnyNetwork]:
    if not value:
        raise ValueError("Value cannot be empty")
    try:
        return [ipaddress.ip_network(ip.strip()) for ip in value.split(",")]
    except ValueError as e:
        raise ValueError(f"Invalid IP network: {e}")


def list_serializer(value: list) -> str:
    return ",".join(str(v) for v in value)


CIDR_LIST_TYPING = typing.Annotated[
    list[pydantic.IPvAnyNetwork] | None,
    pydantic.BeforeValidator(ip_network_list_validator),
    pydantic.PlainSerializer(list_serializer, return_type=str),
]


@sunbeam_tracing.trace_sunbeam_charm
class CinderVolume{VendorPascal}OperatorCharm(charm.OSCinderVolumeDriverOperatorCharm):
    \"\"\"Cinder/{VendorPascal} Operator charm.\""\"

    service_name = "cinder-volume-{vendor_lower}"

    @property
    def backend_key(self) -> str:
        return "{vendor_short}." + self.model.app.name

    def _configuration_type_overrides(self) -> dict[str, typing.Any]:
        overrides = super()._configuration_type_overrides()
        overrides.update(
            {
                # Secrets: use secret_validator
                "{vendor}-api-token": typing.Annotated[
                    str,
                    pydantic.BeforeValidator(sunbeam_storage.secret_validator("token")),
                    sunbeam_storage.Required,
                ],
                # Enums: reference StrEnum class
                "{vendor}-option": SomeOption | None,
                # IP networks
                "{vendor}-cidr": pydantic.IPvAnyNetwork | None,
                # CIDR lists
                "{vendor}-cidr-list": CIDR_LIST_TYPING,
            }
        )
        return overrides


if __name__ == "__main__":  # pragma: nocover
    ops.main(CinderVolume{VendorPascal}OperatorCharm)
```

**Key Rules for charm.py:**
- Apache 2.0 license header
- EXACT import order shown above
- Use `StrEnum` for enum options
- `@sunbeam_tracing.trace_sunbeam_charm` decorator
- Inherit from `charm.OSCinderVolumeDriverOperatorCharm`
- Override `_configuration_type_overrides()` for special types

## TYPE OVERRIDE PATTERNS (Only override when NECESSARY)

**IMPORTANT**: Only add overrides for fields that need special pydantic validation.
Do NOT override simple string, boolean, or int fields - the base class handles those.

| Config Type | When to Override | Override Pattern |
|-------------|------------------|-----------------|
| Secret | Always (for Juju secret handling) | `typing.Annotated[str, pydantic.BeforeValidator(sunbeam_storage.secret_validator("{key}")), sunbeam_storage.Required]` |
| Enum (vendor-prefixed, default null) | When option has vendor prefix and default is null | `EnumClassName \\| None` |
| Enum (vendor-prefixed, has default) | When option has vendor prefix and a non-null default | `EnumClassName` (NO `\\| None`) |
| IP Network (CIDR) | When single CIDR validation needed | `pydantic.IPvAnyNetwork \\| None` |
| CIDR List | When comma-separated CIDR list | `CIDR_LIST_TYPING` |
| Simple string enum (protocol) | Do NOT override | Handled by base class |
| IP Address (san-ip) | Do NOT override | Handled by base class |

**Reference Example** - Pure Storage only overrides:
```python
{
    "pure-api-token": ...,           # Secret
    "pure-host-personality": ...,    # Vendor-prefixed enum
    "pure-iscsi-cidr": ...,          # CIDR
    "pure-iscsi-cidr-list": ...,     # CIDR list
    "pure-nvme-cidr": ...,           # CIDR
    "pure-nvme-cidr-list": ...,      # CIDR list
    "pure-nvme-transport": ...,      # Vendor-prefixed enum
}
# NOTE: "protocol" and "san-ip" are NOT overridden
```

## charmcraft.yaml Template

```yaml
type: charm
name: cinder-volume-{vendor}
summary: OpenStack volume service - {vendor} backend
description: |
  Cinder is the OpenStack project that provides volume management for
  instances.  This charm provides integration with {vendor} storage backends.
assumes:
  - juju >= 3.3
links:
  source:
    - https://opendev.org/openstack/sunbeam-charms
  issues:
    - https://bugs.launchpad.net/sunbeam-charms

base: ubuntu@24.04
platforms:
  amd64:

subordinate: true

config:
  options:
    volume-backend-name:
      default: null
      description: |
        Name that Cinder will report for this backend.
      type: string
    backend-availability-zone:
      default: null
      description: |
        Availability zone to associate with this backend.
      type: string
    # RULES for vendor-specific options:
    # 1. Secret fields MUST use `type: secret` (NOT `type: string`)
    # 2. Required fields (like san-ip) should NOT have `default: null` - omit the default key entirely
    # 3. Optional fields use `default: null` or their explicit default from the spec
    # Add all vendor-specific options from driver spec

requires:
  cinder-volume:
    interface: cinder-volume
    scope: container
    limit: 1
  tracing:
    interface: tracing
    optional: true
    limit: 1

parts:
  update-certificates:
    plugin: nil
    override-build: |
      apt update
      apt install -y ca-certificates
      update-ca-certificates
  charm:
    after:
      - update-certificates
    build-packages:
      - git
      - libffi-dev
      - libssl-dev
      - pkg-config
      - rustc-1.80
      - cargo-1.80
    charm-binary-python-packages:
      - cryptography
      - jsonschema
      - pydantic
      - jinja2
    build-snaps: [astral-uv]
    override-build: |
      uv export --frozen --no-hashes --format=requirements-txt -o requirements.txt
      craftctl default
    charm-requirements: [requirements.txt]
```

## pyproject.toml Template

```toml
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

[project]
name = "cinder-volume-{vendor}"
version = "2025.1"
requires-python = "~=3.12.0"

dependencies = [
    "cryptography",
    "jinja2",
    "pydantic",
    "lightkube",
    "lightkube-models",
    "requests",
    "ops",
    "netifaces",
    "tenacity",
    "opentelemetry-api~=1.21.0",
]
```

## README.md Template

```markdown
# cinder-volume-{vendor}

## Description

The cinder-volume-{vendor} is an operator to manage the Cinder service
integration with {VendorDisplay} backend on a snap based deployment.

## Usage

### Deployment

cinder-volume-{vendor} is deployed using below command:

    juju deploy cinder-volume-{vendor}

Now connect the application to cinder-volume:

    juju relate cinder-volume:cinder-volume cinder-volume-{vendor}:cinder-volume

### Configuration

See file `config.yaml` for options. See [Juju documentation][juju-docs-config-apps].

## Relations

`cinder-volume`: Required relation to Cinder service

## Bugs

Report bugs on [Launchpad][lp-bugs-sunbeam-charms].

[lp-bugs-sunbeam-charms]: https://bugs.launchpad.net/sunbeam-charms
[juju-docs-config-apps]: https://juju.is/docs/configuring-applications
```

## tests/unit/test_charm.py Template

CRITICAL: The test MUST include proper secret handling, relation setup, config updates,
and assertions. A minimal test that only calls `begin_with_initial_hooks()` and
`evaluate_status()` is NOT sufficient.

```python
#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

\"\"\"Unit tests for Cinder {vendor} operator charm.\"""

from unittest.mock import (
    MagicMock,
    Mock,
    patch,
)

import charm
import ops.testing
import ops_sunbeam.test_utils as test_utils


class _CinderVolume{VendorPascal}OperatorCharm(charm.CinderVolume{VendorPascal}OperatorCharm):
    \"\"\"Charm wrapper for test usage.\"\"\"

    def __init__(self, framework):
        self.seen_events = []
        super().__init__(framework)
        self._snap = Mock()

    def _log_event(self, event):
        self.seen_events.append(type(event).__name__)

    def get_snap(self):
        return self._snap


def add_complete_cinder_volume_relation(harness: ops.testing.Harness) -> int:
    \"\"\"Add a complete cinder-volume relation to the charm.\"\"\"
    return harness.add_relation(
        "cinder-volume",
        "cinder-volume",
        unit_data={
            "snap-name": "cinder-volume",
        },
    )


class TestCinder{VendorPascal}OperatorCharm(test_utils.CharmTestCase):
    \"\"\"Test cases for CinderVolume{VendorPascal}OperatorCharm class.\"\"\"

    PATCHES = []

    def setUp(self):
        \"\"\"Setup fixtures ready for testing.\"\"\"
        super().setUp(charm, self.PATCHES)
        self.mock_event = MagicMock()
        self.snap = Mock()
        snap_patch = patch.object(
            _CinderVolume{VendorPascal}OperatorCharm,
            "_import_snap",
            Mock(return_value=self.snap),
        )
        snap_patch.start()
        self.harness = test_utils.get_harness(
            _CinderVolume{VendorPascal}OperatorCharm,
            container_calls=self.container_calls,
        )
        self.addCleanup(snap_patch.stop)
        self.addCleanup(self.harness.cleanup)

    def test_all_relations(self):
        \"\"\"Test charm in context of full set of relations.\"\"\"
        self.harness.begin_with_initial_hooks()
        # Add secret for the secret-type config field
        # Use the secret_key value from the driver spec for the secret dict
        secret = self.harness.add_user_secret({"{secret_key}": "test-value"})
        add_complete_cinder_volume_relation(self.harness)
        self.harness.grant_secret(secret, self.harness.charm.app)
        # Update config with required fields and the secret reference
        self.harness.update_config(
            {"{required_field}": "10.20.20.3", "{secret_field}": secret}
        )
        self.harness.evaluate_status()
        self.assertSetEqual(
            self.harness.charm.get_mandatory_relations_not_ready(
                self.mock_event
            ),
            set(),
        )
```

## DO NOT:
- Add extra lifecycle handlers
- Use StoredState
- Use @validator decorators
- Add __init__ to charm class
- Hallucinate IPs, URLs, or credentials
- Create BaseModel config classes in charm.py
- Forget backend/__init__.py (empty string)
- Mix license headers (SPDX for backend.py, Apache for charm.py)
- Use `type: string` for secret fields in charmcraft.yaml (use `type: secret`)
- Add `default: null` for required fields in charmcraft.yaml (omit the default key)
- Set explicit defaults (like `= "iscsi"`, `= True`, `= 3600`) for optional fields in backend.py Config class (always use `= None`)
- Include `volume_backend_name` or `backend_availability_zone` in the vendor Config class (inherited from base)

## REFERENCE IMPLEMENTATION (Pure Storage - use as pattern)

### Reference backend/backend.py
```python
""" + REFERENCE_BACKEND_PY + """
```

### Reference src/charm.py
```python
""" + REFERENCE_CHARM_PY + """
```
"""


# =============================================================================
# Vendor Name Mappings (for proper capitalization)
# =============================================================================

# Maps lowercase vendor names to their proper PascalCase display names
VENDOR_PASCAL_NAMES = {
    "purestorage": "PureStorage",
    "pure-storage": "PureStorage",
    "netapp": "NetApp",
    "net-app": "NetApp",
    "hitachi": "Hitachi",
    "dellemc": "DellEMC",
    "dell-emc": "DellEMC",
    "dell": "Dell",
    "hpe": "HPE",
    "ibm": "IBM",
    "infinidat": "Infinidat",
    "huawei": "Huawei",
    "solidfire": "SolidFire",
    "nimble": "Nimble",
}

# Maps vendor names to their short prefix for backend_key
VENDOR_SHORT_PREFIXES = {
    "purestorage": "pure",
    "pure-storage": "pure",
    "netapp": "netapp",
    "hitachi": "hitachi",
    "dellemc": "dell",
    "dell-emc": "dell",
    "dell": "dell",
    "hpe": "hpe",
    "ibm": "ibm",
    "infinidat": "infinidat",
    "huawei": "huawei",
    "solidfire": "solidfire",
    "nimble": "nimble",
}


# =============================================================================
# Utility Functions
# =============================================================================

def to_pascal_case(vendor: str) -> str:
    """Convert vendor name to proper PascalCase using known mappings.
    
    Examples:
        'purestorage' -> 'PureStorage'
        'netapp' -> 'NetApp'
        'hitachi' -> 'Hitachi'
        'dell-emc' -> 'DellEMC'
    """
    vendor_lower = vendor.lower().replace("_", "-")
    
    # Check known mappings first
    if vendor_lower in VENDOR_PASCAL_NAMES:
        return VENDOR_PASCAL_NAMES[vendor_lower]
    
    # Fallback: simple capitalization
    return "".join(word.capitalize() for word in vendor.replace("-", " ").replace("_", " ").split())


def to_snake_case(name: str) -> str:
    """Convert name to snake_case."""
    return name.replace("-", "_")


def get_vendor_short(vendor: str) -> str:
    """Get short vendor prefix for backend_key.
    
    Examples:
        'purestorage' -> 'pure'
        'hitachi' -> 'hitachi'
        'dell-emc' -> 'dell'
    """
    vendor_lower = vendor.lower().replace("_", "-")
    
    # Check known mappings first
    if vendor_lower in VENDOR_SHORT_PREFIXES:
        return VENDOR_SHORT_PREFIXES[vendor_lower]
    
    # Fallback: use first part of hyphenated name
    return vendor_lower.split("-")[0]


def detect_type_overrides(config_options: list[dict]) -> dict:
    """Analyze config options and return required type overrides for charm.py.
    
    IMPORTANT: Only detect overrides for fields that need special handling:
    - Secrets (always need override)
    - Vendor-prefixed enums (e.g., pure-host-personality, hitachi-copy-method)
    - CIDR/IP network fields (need pydantic.IPvAnyNetwork)
    - CIDR list fields (need custom CIDR_LIST_TYPING)
    
    Do NOT override:
    - Simple protocol enum (handled by base class)
    - Simple IP address fields like san-ip (handled by base class)
    """
    overrides = {}
    enums = []
    vendor_prefixes = ["pure", "hitachi", "netapp", "dell", "hpe", "ibm", "infinidat", "huawei", "solidfire", "nimble"]
    
    for opt in config_options:
        name = opt.get("name", "")
        opt_type = opt.get("type", "string")
        
        # Check if this is a vendor-prefixed field
        parts = name.split("-")
        has_vendor_prefix = len(parts) > 1 and parts[0] in vendor_prefixes
        
        # Secret fields - always need override
        if opt_type == "secret":
            overrides[name] = {
                "type": "secret",
                "secret_key": opt.get("secret_key", "token"),
                "required": opt.get("required", False),
            }
        
        # Enum fields - only vendor-prefixed ones need override
        elif opt.get("enum") and has_vendor_prefix:
            # Generate class name from option name (skip vendor prefix)
            enum_parts = parts[1:]  # Skip vendor prefix
            enum_class = opt.get("enum_class", "".join(w.capitalize() for w in enum_parts))
            
            if not any(e["name"] == enum_class for e in enums):
                enums.append({
                    "name": enum_class,
                    "values": opt["enum"],
                })
            
            overrides[name] = {"type": "enum", "class": enum_class}
        
        # IP Network (CIDR) - only vendor-prefixed CIDR fields
        elif opt.get("validation") == "ip_network" and has_vendor_prefix:
            overrides[name] = {"type": "ip_network"}
        
        # CIDR List - only vendor-prefixed
        elif opt.get("validation") == "ip_network_list" and has_vendor_prefix:
            overrides[name] = {"type": "ip_network_list"}
        
        # Note: ip_address validation for non-prefixed fields (like san-ip) is NOT overridden
    
    return {"overrides": overrides, "enums": enums}


# =============================================================================
# Prompt Builder Functions
# =============================================================================

def build_user_prompt(driver_spec: dict[str, Any]) -> str:
    """Build the user prompt from a driver specification."""
    vendor = driver_spec.get("vendor", "unknown")
    display_name = driver_spec.get("display_name", vendor)
    charm_info = driver_spec.get("charm", {})
    charm_name = charm_info.get("name", f"cinder-volume-{vendor.lower()}")
    
    vendor_lower = vendor.lower().replace("_", "-")
    vendor_pascal = to_pascal_case(vendor)
    vendor_short = get_vendor_short(vendor)
    
    config_options = driver_spec.get("config_options", [])
    override_info = detect_type_overrides(config_options)
    
    cli_fields = [opt for opt in config_options if opt.get("cli_prompt")]
    secrets = [opt for opt in config_options if opt.get("type") == "secret"]
    enums = [opt for opt in config_options if opt.get("enum")]
    
    prompt = f"""Generate a Sunbeam Cinder backend for **{display_name}**.

## EXACT Naming (use these values):
- charm_name: `{charm_name}`
- backend_type: `"{vendor_lower}"`
- Backend class: `{vendor_pascal}Backend`
- Config class: `{vendor_pascal}Config`
- Charm class: `CinderVolume{vendor_pascal}OperatorCharm`
- service_name: `"{charm_name}"`
- backend_key: `"{vendor_short}." + self.model.app.name`
- display_name: `"{display_name}"`
- supports_ha: `{str(driver_spec.get('ha_enabled', True))}`

## Driver Specification
```json
{json.dumps(driver_spec, indent=2)}
```

## ALL Fields for backend.py Config class (include ALL, not just cli_prompt: true)
Convert hyphenated names to snake_case: `pure-api-token` → `pure_api_token`
```json
{json.dumps([{
    "name": f["name"],
    "python_name": f["name"].replace("-", "_"),
    "type": f.get("type", "string"),
    "required": f.get("required", False),
    "default": f.get("default"),
    "description": (f.get("description", "") or "")[:80].strip(),
    "secret_key": f.get("secret_key"),
    "enum": f.get("enum"),
} for f in config_options], indent=2)}
```

## Secret Fields (use SecretDictField in backend.py, secret_validator in charm.py)
```json
{json.dumps([{"name": s["name"], "python_name": s["name"].replace("-", "_"), "secret_key": s.get("secret_key", "token")} for s in secrets], indent=2) if secrets else "[]"}
```

## Enum Fields (create StrEnum classes in BOTH backend.py and charm.py)
```json
{json.dumps([{"name": e["name"], "python_name": e["name"].replace("-", "_"), "values": e["enum"], "enum_class": e.get("enum_class")} for e in enums], indent=2) if enums else "[]"}
```

## Type Overrides for charm.py _configuration_type_overrides() (vendor-prefixed only)
```json
{json.dumps(override_info, indent=2)}
```

## IMPORTANT REMINDERS:
1. backend.py Config class must have ALL fields from the spec above EXCEPT `volume-backend-name` and `backend-availability-zone` (inherited from base class)
2. Use snake_case for Python attribute names (e.g., `pure_api_token` not `api_token`)
3. Required fields have no default; ALL optional fields MUST use `= None` (never explicit defaults like `= "iscsi"` or `= True`)
4. Create StrEnum classes for vendor-prefixed enum fields (e.g., Personality, NvmeTransport). Use `Literal[...] | None` for simple enums like protocol
5. In charmcraft.yaml: secret fields MUST use `type: secret` (NOT `type: string`); required fields must NOT have `default: null`
6. The test file must include secret handling, relation setup, config updates, and assertions (see template)

Generate ALL files as a JSON object.
"""
    return prompt


def assemble_prompts(driver_spec: dict[str, Any]) -> tuple[str, str]:
    """Assemble complete system and user prompts for charm generation."""
    return SYSTEM_PROMPT, build_user_prompt(driver_spec)
