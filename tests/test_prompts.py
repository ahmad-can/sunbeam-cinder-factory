"""Tests for charm_generator.prompts module."""

import json

import pytest
import yaml

from charm_generator.prompts import (
    SYSTEM_PROMPT,
    REFERENCE_BACKEND_PY,
    REFERENCE_CHARM_PY,
    VENDOR_PASCAL_NAMES,
    VENDOR_SHORT_PREFIXES,
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


class TestDetectTypeOverrides:
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


class TestBuildUserPrompt:
    @pytest.fixture
    def pure_spec(self):
        spec_path = DRIVER_SPECS_DIR / "pure.yaml"
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
