"""Tests for charm_generator.prompts module."""

import json

import pytest
import yaml

from charm_generator.prompts import (
    BASE_CLASS_OVERRIDES,
    COMMON_CONFIG_OPTIONS,
    SYSTEM_PROMPT,
    REFERENCE_BACKEND_PY,
    REFERENCE_CHARM_PY,
    VENDOR_PASCAL_NAMES,
    VENDOR_SHORT_PREFIXES,
    _normalize_config_options,
    assemble_prompts,
    build_user_prompt,
    detect_type_overrides,
    get_vendor_short,
    to_pascal_case,
    to_snake_case,
)
from charm_generator.settings import DRIVER_SPECS_DIR


class TestToPascalCase:
    def test_known_vendors(self):
        assert to_pascal_case("purestorage") == "PureStorage"
        assert to_pascal_case("netapp") == "NetApp"
        assert to_pascal_case("hitachi") == "Hitachi"
        assert to_pascal_case("dellemc") == "DellEMC"
        assert to_pascal_case("dell-emc") == "DellEMC"

    def test_fallback_capitalization(self):
        assert to_pascal_case("newvendor") == "Newvendor"
        assert to_pascal_case("my-vendor") == "MyVendor"
        assert to_pascal_case("multi_word_vendor") == "MultiWordVendor"

    def test_case_insensitive(self):
        assert to_pascal_case("PURESTORAGE") == "PureStorage"
        assert to_pascal_case("HiTaChI") == "Hitachi"


class TestToSnakeCase:
    def test_basic(self):
        assert to_snake_case("pure-api-token") == "pure_api_token"
        assert to_snake_case("san-ip") == "san_ip"
        assert to_snake_case("already_snake") == "already_snake"
        assert to_snake_case("nochange") == "nochange"


class TestGetVendorShort:
    def test_known_vendors(self):
        assert get_vendor_short("purestorage") == "pure"
        assert get_vendor_short("hitachi") == "hitachi"
        assert get_vendor_short("dell-emc") == "dell"

    def test_fallback(self):
        assert get_vendor_short("unknown-vendor") == "unknown"
        assert get_vendor_short("newvendor") == "newvendor"


class TestDetectTypeOverridesLegacy:
    """Tests for legacy heuristic mode (no type_overrides section in spec)."""

    def test_secret_field(self):
        options = [{"name": "pure-api-token", "type": "secret", "secret_key": "token"}]
        result = detect_type_overrides(options)
        assert "pure-api-token" in result["overrides"]
        assert result["overrides"]["pure-api-token"]["type"] == "secret"
        assert result["overrides"]["pure-api-token"]["secret_key"] == "token"

    def test_vendor_prefixed_enum(self):
        options = [
            {"name": "pure-host-personality", "type": "string", "enum": ["aix", "esxi"], "enum_class": "Personality"}
        ]
        result = detect_type_overrides(options)
        assert "pure-host-personality" in result["overrides"]
        assert result["overrides"]["pure-host-personality"]["type"] == "enum"
        assert len(result["enums"]) == 1
        assert result["enums"][0]["name"] == "Personality"

    def test_non_vendor_prefixed_enum_not_overridden(self):
        options = [{"name": "protocol", "type": "string", "enum": ["iscsi", "fc"]}]
        result = detect_type_overrides(options)
        assert "protocol" not in result["overrides"]

    def test_vendor_prefixed_cidr(self):
        options = [{"name": "pure-iscsi-cidr", "type": "string", "validation": "ip_network"}]
        result = detect_type_overrides(options)
        assert "pure-iscsi-cidr" in result["overrides"]
        assert result["overrides"]["pure-iscsi-cidr"]["type"] == "ip_network"

    def test_vendor_prefixed_cidr_list(self):
        options = [{"name": "pure-nvme-cidr-list", "type": "string", "validation": "ip_network_list"}]
        result = detect_type_overrides(options)
        assert "pure-nvme-cidr-list" in result["overrides"]
        assert result["overrides"]["pure-nvme-cidr-list"]["type"] == "ip_network_list"

    def test_non_vendor_ip_not_overridden(self):
        options = [{"name": "san-ip", "type": "string", "validation": "ip_address"}]
        result = detect_type_overrides(options)
        assert "san-ip" not in result["overrides"]

    def test_empty_options(self):
        result = detect_type_overrides([])
        assert result == {"overrides": {}, "enums": []}


class TestDetectTypeOverridesSpecDriven:
    """Tests for spec-driven mode (type_overrides section present)."""

    def test_secret_override(self):
        spec = {
            "type_overrides": [
                {"name": "san-password", "type": "secret", "secret_key": "san-password", "required": True},
            ],
            "config_options": [{"name": "san-password", "type": "secret"}],
        }
        result = detect_type_overrides(spec["config_options"], spec=spec)
        assert result["overrides"]["san-password"]["type"] == "secret"
        assert result["overrides"]["san-password"]["secret_key"] == "san-password"
        assert result["overrides"]["san-password"]["required"] is True

    def test_required_override(self):
        spec = {
            "type_overrides": [
                {"name": "dell-sc-ssn", "type": "required", "python_type": "int"},
            ],
            "config_options": [{"name": "dell-sc-ssn", "type": "int"}],
        }
        result = detect_type_overrides(spec["config_options"], spec=spec)
        assert result["overrides"]["dell-sc-ssn"]["type"] == "required"
        assert result["overrides"]["dell-sc-ssn"]["python_type"] == "int"

    def test_literal_override(self):
        spec = {
            "type_overrides": [
                {"name": "protocol", "type": "literal", "values": ["fc", "iscsi"], "required": True},
            ],
            "config_options": [{"name": "protocol", "type": "string", "enum": ["fc", "iscsi"]}],
        }
        result = detect_type_overrides(spec["config_options"], spec=spec)
        assert result["overrides"]["protocol"]["type"] == "literal"
        assert result["overrides"]["protocol"]["values"] == ["fc", "iscsi"]
        assert result["overrides"]["protocol"]["required"] is True

    def test_force_value_override(self):
        spec = {
            "type_overrides": [
                {"name": "enable-unsupported-driver", "type": "force_value", "value": True},
            ],
            "config_options": [],
        }
        result = detect_type_overrides(spec["config_options"], spec=spec)
        assert result["overrides"]["enable-unsupported-driver"]["type"] == "force_value"
        assert result["overrides"]["enable-unsupported-driver"]["value"] is True

    def test_required_group_override(self):
        spec = {
            "type_overrides": [
                {"name": "secondary-san-ip", "type": "required_group", "group": "secondary"},
            ],
            "config_options": [{"name": "secondary-san-ip", "type": "string"}],
        }
        result = detect_type_overrides(spec["config_options"], spec=spec)
        assert result["overrides"]["secondary-san-ip"]["type"] == "required_group"
        assert result["overrides"]["secondary-san-ip"]["group"] == "secondary"

    def test_secret_group_override(self):
        spec = {
            "type_overrides": [
                {"name": "secondary-san-password", "type": "secret_group", "secret_key": "secondary-san-password", "group": "secondary"},
            ],
            "config_options": [{"name": "secondary-san-password", "type": "secret"}],
        }
        result = detect_type_overrides(spec["config_options"], spec=spec)
        ov = result["overrides"]["secondary-san-password"]
        assert ov["type"] == "secret_group"
        assert ov["secret_key"] == "secondary-san-password"
        assert ov["group"] == "secondary"

    def test_remove_base_config(self):
        spec = {
            "type_overrides": [],
            "remove_base_config": ["driver-ssl-cert"],
            "config_options": [],
        }
        result = detect_type_overrides(spec["config_options"], spec=spec)
        assert result["remove_base_config"] == ["driver-ssl-cert"]

    def test_unsupported_driver(self):
        spec = {
            "type_overrides": [],
            "unsupported_driver": True,
            "config_options": [],
        }
        result = detect_type_overrides(spec["config_options"], spec=spec)
        assert result["unsupported_driver"] is True

    def test_enum_override(self):
        spec = {
            "type_overrides": [
                {"name": "pure-host-personality", "type": "enum", "enum_class": "Personality"},
            ],
            "config_options": [
                {"name": "pure-host-personality", "type": "string", "enum": ["aix", "esxi"], "enum_class": "Personality"},
            ],
        }
        result = detect_type_overrides(spec["config_options"], spec=spec)
        assert result["overrides"]["pure-host-personality"]["type"] == "enum"
        assert result["enums"][0]["name"] == "Personality"

    def test_dellsc_spec_full(self):
        """Test with the actual Dell SC spec file."""
        spec_path = DRIVER_SPECS_DIR / "dellsc.yaml"
        if not spec_path.exists():
            pytest.skip("dellsc.yaml not found")
        spec = yaml.safe_load(spec_path.read_text())
        result = detect_type_overrides(spec["config_options"], spec=spec)
        assert "san-login" in result["overrides"]
        assert "san-password" in result["overrides"]
        assert "dell-sc-ssn" in result["overrides"]
        assert "protocol" in result["overrides"]
        assert "secondary-san-ip" in result["overrides"]
        assert result.get("remove_base_config") == ["driver-ssl-cert"]
        assert result.get("unsupported_driver") is True


class TestBaseClassOverrides:
    def test_contains_expected_fields(self):
        assert "san-ip" in BASE_CLASS_OVERRIDES
        assert "driver-ssl-cert" in BASE_CLASS_OVERRIDES
        assert "protocol" in BASE_CLASS_OVERRIDES
        assert "volume-backend-name" in BASE_CLASS_OVERRIDES
        assert "backend-availability-zone" in BASE_CLASS_OVERRIDES


class TestNormalizeConfigOptions:
    def test_auto_injects_common_options(self):
        result = _normalize_config_options([], {})
        names = [o["name"] for o in result]
        assert "volume-backend-name" in names
        assert "backend-availability-zone" in names
        assert "san-ip" in names
        assert "driver-ssl-cert" in names

    def test_skips_removed_base_config(self):
        result = _normalize_config_options([], {"remove_base_config": ["driver-ssl-cert"]})
        names = [o["name"] for o in result]
        assert "driver-ssl-cert" not in names
        assert "san-ip" in names

    def test_does_not_duplicate_existing(self):
        opts = [{"name": "san-ip", "type": "string", "description": "custom"}]
        result = _normalize_config_options(opts, {})
        san_entries = [o for o in result if o["name"] == "san-ip"]
        assert len(san_entries) == 1
        assert san_entries[0]["description"] == "custom"

    def test_applies_field_defaults(self):
        opts = [{"name": "my-field"}]
        result = _normalize_config_options(opts, {})
        my_field = next(o for o in result if o["name"] == "my-field")
        assert my_field["type"] == "string"
        assert my_field["default"] is None
        assert my_field["required"] is False
        assert my_field["cli_prompt"] is False
        assert my_field["description"] == ""

    def test_preserves_explicit_values(self):
        opts = [{"name": "x", "type": "int", "default": 42, "required": True, "cli_prompt": True, "description": "test"}]
        result = _normalize_config_options(opts, {})
        x = next(o for o in result if o["name"] == "x")
        assert x["type"] == "int"
        assert x["default"] == 42
        assert x["required"] is True
        assert x["cli_prompt"] is True

    def test_pure_spec_gets_common_options(self):
        spec_path = DRIVER_SPECS_DIR / "pure.yaml"
        spec = yaml.safe_load(spec_path.read_text())
        result = _normalize_config_options(spec["config_options"], spec)
        names = [o["name"] for o in result]
        assert "volume-backend-name" in names
        assert "driver-ssl-cert" in names

    def test_dellsc_spec_excludes_driver_ssl_cert(self):
        spec_path = DRIVER_SPECS_DIR / "dellsc.yaml"
        if not spec_path.exists():
            pytest.skip("dellsc.yaml not found")
        spec = yaml.safe_load(spec_path.read_text())
        result = _normalize_config_options(spec["config_options"], spec)
        names = [o["name"] for o in result]
        assert "driver-ssl-cert" not in names
        assert "volume-backend-name" in names


class TestSystemPrompt:
    def test_contains_reference_implementation(self):
        assert "REFERENCE IMPLEMENTATION" in SYSTEM_PROMPT
        assert "SPDX-FileCopyrightText" in SYSTEM_PROMPT

    def test_contains_secret_type_rule(self):
        assert "type: secret" in SYSTEM_PROMPT

    def test_contains_default_none_rule(self):
        assert "= None" in SYSTEM_PROMPT

    def test_contains_backend_py_rules(self):
        assert "StorageBackendConfig" in SYSTEM_PROMPT
        assert "StorageBackendBase" in SYSTEM_PROMPT

    def test_contains_charm_py_rules(self):
        assert "OSCinderVolumeDriverOperatorCharm" in SYSTEM_PROMPT
        assert "sunbeam_tracing" in SYSTEM_PROMPT

    def test_contains_test_template_with_secrets(self):
        assert "add_user_secret" in SYSTEM_PROMPT
        assert "grant_secret" in SYSTEM_PROMPT
        assert "update_config" in SYSTEM_PROMPT

    def test_contains_base_class_defaults_section(self):
        assert "BASE CLASS DEFAULTS" in SYSTEM_PROMPT
        assert "super()._configuration_type_overrides()" in SYSTEM_PROMPT
        assert "certificate_validator" in SYSTEM_PROMPT

    def test_contains_new_override_patterns(self):
        assert "Required field" in SYSTEM_PROMPT
        assert "Literal enum" in SYSTEM_PROMPT
        assert "Force value" in SYSTEM_PROMPT
        assert "Required group" in SYSTEM_PROMPT
        assert "Secret group" in SYSTEM_PROMPT
        assert "Config removal" in SYSTEM_PROMPT
        assert "Unsupported driver" in SYSTEM_PROMPT

    def test_contains_dell_sc_reference(self):
        assert "Dell SC" in SYSTEM_PROMPT
        assert "dell-sc-ssn" in SYSTEM_PROMPT
        assert "RequiredIfGroup" in SYSTEM_PROMPT


class TestBuildUserPrompt:
    @pytest.fixture
    def pure_spec(self):
        spec_path = DRIVER_SPECS_DIR / "pure.yaml"
        return yaml.safe_load(spec_path.read_text())

    @pytest.fixture
    def dellsc_spec(self):
        spec_path = DRIVER_SPECS_DIR / "dellsc.yaml"
        if not spec_path.exists():
            pytest.skip("dellsc.yaml not found")
        return yaml.safe_load(spec_path.read_text())

    def test_contains_naming(self, pure_spec):
        prompt = build_user_prompt(pure_spec)
        assert "cinder-volume-purestorage" in prompt
        assert "PureStorageBackend" in prompt
        assert "PureStorageConfig" in prompt
        assert "CinderVolumePureStorageOperatorCharm" in prompt

    def test_contains_all_config_fields(self, pure_spec):
        prompt = build_user_prompt(pure_spec)
        for opt in pure_spec["config_options"]:
            assert opt["name"] in prompt

    def test_contains_secret_fields_section(self, pure_spec):
        prompt = build_user_prompt(pure_spec)
        assert "Secret Fields" in prompt
        assert "pure-api-token" in prompt

    def test_contains_important_reminders(self, pure_spec):
        prompt = build_user_prompt(pure_spec)
        assert "type: secret" in prompt
        assert "volume-backend-name" in prompt
        assert "backend-availability-zone" in prompt

    def test_contains_super_reminder(self, pure_spec):
        prompt = build_user_prompt(pure_spec)
        assert "super()._configuration_type_overrides()" in prompt

    def test_dellsc_contains_special_instructions(self, dellsc_spec):
        prompt = build_user_prompt(dellsc_spec)
        assert "REMOVE base class configs" in prompt
        assert "driver-ssl-cert" in prompt
        assert "UNSUPPORTED" in prompt
        assert "enable-unsupported-driver" in prompt

    def test_dellsc_naming(self, dellsc_spec):
        prompt = build_user_prompt(dellsc_spec)
        assert "DellSCBackend" in prompt
        assert "DellSCConfig" in prompt
        assert "CinderVolumeDellSCOperatorCharm" in prompt


class TestAssemblePrompts:
    def test_returns_tuple(self):
        spec = {"vendor": "test", "config_options": []}
        system, user = assemble_prompts(spec)
        assert isinstance(system, str)
        assert isinstance(user, str)
        assert len(system) > 0
        assert len(user) > 0


class TestReferenceEmbeds:
    def test_reference_backend_has_spdx(self):
        assert "SPDX-FileCopyrightText" in REFERENCE_BACKEND_PY
        assert "SPDX-License-Identifier" in REFERENCE_BACKEND_PY

    def test_reference_charm_has_apache_license(self):
        assert "Apache License, Version 2.0" in REFERENCE_CHARM_PY

    def test_reference_backend_has_required_classes(self):
        assert "StorageBackendConfig" in REFERENCE_BACKEND_PY
        assert "StorageBackendBase" in REFERENCE_BACKEND_PY
        assert "PureStorageConfig" in REFERENCE_BACKEND_PY
        assert "PureStorageBackend" in REFERENCE_BACKEND_PY

    def test_reference_charm_has_required_classes(self):
        assert "CinderVolumePureStorageOperatorCharm" in REFERENCE_CHARM_PY
        assert "sunbeam_tracing" in REFERENCE_CHARM_PY

    def test_reference_backend_uses_none_defaults(self):
        assert "= None" in REFERENCE_BACKEND_PY
        # Config fields should NOT have explicit defaults like = "iscsi" or = 3600
        # (generally_available = True is a Backend class attribute, not a Config field)
        assert '= "iscsi"' not in REFERENCE_BACKEND_PY
        assert "= 3600" not in REFERENCE_BACKEND_PY
        assert '= "0.0.0.0/0"' not in REFERENCE_BACKEND_PY
