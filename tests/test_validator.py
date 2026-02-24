"""Tests for charm_generator.validator module."""

import shutil
import textwrap
from pathlib import Path

import pytest
import yaml

from charm_generator.validator import (
    CharmValidator,
    ValidationResult,
    compare_charms,
)
from charm_generator.settings import GENERATED_CHARMS_DIR, DRIVER_SPECS_DIR


@pytest.fixture
def tmp_charm_dir(tmp_path):
    """Create a minimal valid charm directory for testing."""
    charm_dir = tmp_path / "test-vendor"
    (charm_dir / "src").mkdir(parents=True)
    (charm_dir / "backend").mkdir(parents=True)
    (charm_dir / "tests" / "unit").mkdir(parents=True)

    (charm_dir / "charmcraft.yaml").write_text(yaml.dump({
        "type": "charm",
        "name": "cinder-volume-test",
        "subordinate": True,
        "requires": {
            "cinder-volume": {"interface": "cinder-volume", "scope": "container", "limit": 1},
        },
        "config": {"options": {}},
    }))

    (charm_dir / "src" / "charm.py").write_text(textwrap.dedent("""\
        import ops_sunbeam.charm as charm
        import ops_sunbeam.tracing as sunbeam_tracing

        @sunbeam_tracing.trace_sunbeam_charm
        class CinderVolumeTestOperatorCharm(charm.OSCinderVolumeDriverOperatorCharm):
            pass
    """))

    (charm_dir / "backend" / "backend.py").write_text(textwrap.dedent("""\
        # SPDX-FileCopyrightText: 2025 - Canonical Ltd
        # SPDX-License-Identifier: Apache-2.0
        from sunbeam.core.manifest import StorageBackendConfig
        from sunbeam.storage.base import StorageBackendBase
        class TestConfig(StorageBackendConfig):
            pass
        class TestBackend(StorageBackendBase):
            backend_type = "test"
    """))

    (charm_dir / "backend" / "__init__.py").write_text("")
    (charm_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (charm_dir / "README.md").write_text("# Test\n")
    (charm_dir / "tests" / "unit" / "__init__.py").write_text("")
    (charm_dir / "tests" / "unit" / "test_charm.py").write_text("# tests\n")

    return charm_dir


@pytest.fixture
def validator(tmp_path):
    return CharmValidator(generated_dir=tmp_path)


class TestValidationResult:
    def test_initial_state(self):
        result = ValidationResult(vendor="test")
        assert result.valid is True
        assert result.error_count == 0
        assert result.warning_count == 0

    def test_add_error(self):
        result = ValidationResult(vendor="test")
        result.add_issue("error", "test", "something broke")
        assert result.valid is False
        assert result.error_count == 1

    def test_add_warning(self):
        result = ValidationResult(vendor="test")
        result.add_issue("warning", "test", "something looks off")
        assert result.valid is True
        assert result.warning_count == 1

    def test_to_dict(self):
        result = ValidationResult(vendor="test")
        result.add_issue("error", "cat", "msg")
        d = result.to_dict()
        assert d["vendor"] == "test"
        assert d["valid"] is False
        assert d["error_count"] == 1
        assert len(d["issues"]) == 1


class TestCharmValidator:
    def test_missing_directory(self, validator):
        result = validator.validate("nonexistent")
        assert result.valid is False
        assert result.error_count == 1

    def test_valid_charm(self, validator, tmp_charm_dir):
        result = validator.validate(tmp_charm_dir.name)
        assert result.valid is True
        assert result.error_count == 0

    def test_missing_required_file(self, validator, tmp_charm_dir):
        (tmp_charm_dir / "pyproject.toml").unlink()
        result = validator.validate(tmp_charm_dir.name)
        assert result.valid is False
        assert any("pyproject.toml" in i.message for i in result.issues)

    def test_invalid_charmcraft_type(self, validator, tmp_charm_dir):
        data = yaml.safe_load((tmp_charm_dir / "charmcraft.yaml").read_text())
        data["type"] = "bundle"
        (tmp_charm_dir / "charmcraft.yaml").write_text(yaml.dump(data))
        result = validator.validate(tmp_charm_dir.name)
        assert any("Invalid type" in i.message for i in result.issues)

    def test_missing_cinder_volume_relation(self, validator, tmp_charm_dir):
        data = yaml.safe_load((tmp_charm_dir / "charmcraft.yaml").read_text())
        data["requires"] = {}
        (tmp_charm_dir / "charmcraft.yaml").write_text(yaml.dump(data))
        result = validator.validate(tmp_charm_dir.name)
        assert any("cinder-volume" in i.message for i in result.issues)

    def test_missing_spdx_header(self, validator, tmp_charm_dir):
        (tmp_charm_dir / "backend" / "backend.py").write_text(textwrap.dedent("""\
            from sunbeam.core.manifest import StorageBackendConfig
            from sunbeam.storage.base import StorageBackendBase
            class TestConfig(StorageBackendConfig):
                pass
            class TestBackend(StorageBackendBase):
                backend_type = "test"
        """))
        result = validator.validate(tmp_charm_dir.name)
        assert any("SPDX-FileCopyrightText" in i.message for i in result.issues)


class TestSpecBasedValidation:
    @pytest.fixture
    def spec(self):
        return {
            "vendor": "test",
            "display_name": "Test Storage",
            "charm": {"name": "cinder-volume-test"},
            "config_options": [
                {"name": "san-ip", "type": "string", "required": True, "cli_prompt": True},
                {"name": "test-api-token", "type": "secret", "required": True, "secret_key": "token", "cli_prompt": True},
                {"name": "protocol", "type": "string", "required": False, "enum": ["iscsi", "fc"]},
            ],
        }

    def test_missing_config_option(self, validator, tmp_charm_dir, spec):
        result = validator.validate(tmp_charm_dir.name, spec_path=None)
        # Without spec, no spec-based errors
        assert result.error_count == 0

    def test_secret_type_mismatch(self, validator, tmp_charm_dir, spec):
        data = yaml.safe_load((tmp_charm_dir / "charmcraft.yaml").read_text())
        data["config"]["options"] = {
            "san-ip": {"type": "string"},
            "test-api-token": {"type": "string", "default": None},
            "protocol": {"type": "string", "default": "iscsi"},
        }
        (tmp_charm_dir / "charmcraft.yaml").write_text(yaml.dump(data))

        # Write spec to a temp file
        spec_file = tmp_charm_dir.parent / "spec.yaml"
        spec_file.write_text(yaml.dump(spec))

        result = validator.validate(tmp_charm_dir.name, spec_path=str(spec_file))
        secret_errors = [i for i in result.issues if "type: secret" in i.message]
        assert len(secret_errors) == 1
        assert "test-api-token" in secret_errors[0].message

    def test_required_field_with_default_null(self, validator, tmp_charm_dir, spec):
        data = yaml.safe_load((tmp_charm_dir / "charmcraft.yaml").read_text())
        data["config"]["options"] = {
            "san-ip": {"type": "string", "default": None},
            "test-api-token": {"type": "secret", "default": None},
            "protocol": {"type": "string", "default": "iscsi"},
        }
        (tmp_charm_dir / "charmcraft.yaml").write_text(yaml.dump(data))

        spec_file = tmp_charm_dir.parent / "spec.yaml"
        spec_file.write_text(yaml.dump(spec))

        result = validator.validate(tmp_charm_dir.name, spec_path=str(spec_file))
        default_warnings = [i for i in result.issues if "default: null" in i.message]
        assert len(default_warnings) == 2

    def test_test_completeness_warnings(self, validator, tmp_charm_dir, spec):
        spec_file = tmp_charm_dir.parent / "spec.yaml"
        spec_file.write_text(yaml.dump(spec))

        # Minimal test file without proper secret handling
        data = yaml.safe_load((tmp_charm_dir / "charmcraft.yaml").read_text())
        data["config"]["options"] = {
            "san-ip": {"type": "string"},
            "test-api-token": {"type": "secret"},
            "protocol": {"type": "string", "default": "iscsi"},
        }
        (tmp_charm_dir / "charmcraft.yaml").write_text(yaml.dump(data))

        result = validator.validate(tmp_charm_dir.name, spec_path=str(spec_file))
        test_warnings = [i for i in result.issues if i.category == "test"]
        assert len(test_warnings) >= 2

    def test_backend_base_class_fields_warning(self, validator, tmp_charm_dir, spec):
        (tmp_charm_dir / "backend" / "backend.py").write_text(textwrap.dedent("""\
            # SPDX-FileCopyrightText: 2025 - Canonical Ltd
            # SPDX-License-Identifier: Apache-2.0
            from sunbeam.core.manifest import StorageBackendConfig
            from sunbeam.storage.base import StorageBackendBase
            class TestConfig(StorageBackendConfig):
                volume_backend_name: str | None = None
                backend_availability_zone: str | None = None
            class TestBackend(StorageBackendBase):
                backend_type = "test"
        """))

        spec_file = tmp_charm_dir.parent / "spec.yaml"
        spec_file.write_text(yaml.dump(spec))

        data = yaml.safe_load((tmp_charm_dir / "charmcraft.yaml").read_text())
        data["config"]["options"] = {
            "san-ip": {"type": "string"},
            "test-api-token": {"type": "secret"},
            "protocol": {"type": "string", "default": "iscsi"},
        }
        (tmp_charm_dir / "charmcraft.yaml").write_text(yaml.dump(data))

        result = validator.validate(tmp_charm_dir.name, spec_path=str(spec_file))
        base_warnings = [i for i in result.issues if "inherited from base" in i.message]
        assert len(base_warnings) == 2


class TestCompareCharms:
    def test_compare_nonexistent(self):
        result = compare_charms("nonexistent1", "nonexistent2")
        assert "error" in result

    def test_compare_existing(self, tmp_path):
        dir1 = GENERATED_CHARMS_DIR / "cinder-volume-purestorage"
        if not dir1.exists():
            pytest.skip("No generated charms to compare")
        result = compare_charms("cinder-volume-purestorage", "cinder-volume-purestorage")
        assert result["vendor1_file_count"] == result["vendor2_file_count"]
        assert len(result["common_files"]) > 0
