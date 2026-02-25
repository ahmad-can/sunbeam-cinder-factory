"""Charm structure and spec-based validation."""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from charm_generator.settings import (
    REFERENCE_DIR,
    GENERATED_CHARMS_DIR,
    DRIVER_SPECS_DIR,
    REQUIRED_CHARM_FILES,
)
from charm_generator.prompts import detect_type_overrides, to_pascal_case, _normalize_config_options

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """A validation issue."""
    severity: str  # error, warning, info
    category: str
    message: str
    file_path: str | None = None


@dataclass
class ValidationResult:
    """Result of charm validation."""
    vendor: str
    valid: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)
    
    def add_issue(self, severity: str, category: str, message: str, **kwargs) -> None:
        self.issues.append(ValidationIssue(severity=severity, category=category, message=message, **kwargs))
        if severity == "error":
            self.valid = False
    
    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")
    
    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "vendor": self.vendor,
            "valid": self.valid,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [{"severity": i.severity, "category": i.category, "message": i.message} for i in self.issues],
        }


class CharmValidator:
    """Validates generated charms against structure and YAML spec."""
    
    def __init__(self, reference_dir: Path | str | None = None, generated_dir: Path | str | None = None):
        self.reference_dir = Path(reference_dir) if reference_dir else REFERENCE_DIR
        self.generated_dir = Path(generated_dir) if generated_dir else GENERATED_CHARMS_DIR
    
    def validate(self, vendor: str, spec_path: Path | str | None = None) -> ValidationResult:
        """Validate a generated charm, optionally against a YAML spec."""
        result = ValidationResult(vendor=vendor)
        vendor_dir = self.generated_dir / vendor
        
        if not vendor_dir.exists():
            result.add_issue("error", "structure", f"Charm directory not found: {vendor_dir}")
            return result
        
        # Basic structure validation
        self._validate_required_files(vendor_dir, result)
        self._validate_charmcraft_yaml(vendor_dir, result)
        self._validate_charm_py(vendor_dir, result)
        self._validate_backend_py(vendor_dir, result)
        
        # Spec-based validation (if spec provided)
        if spec_path:
            spec = self._load_spec(spec_path)
            if spec:
                self._validate_against_spec(vendor_dir, spec, result)
        
        return result
    
    def _load_spec(self, spec_path: Path | str) -> dict | None:
        """Load a driver specification file."""
        path = Path(spec_path)
        if not path.exists():
            path = DRIVER_SPECS_DIR / spec_path
        if not path.exists():
            return None
        return yaml.safe_load(path.read_text())
    
    def _validate_required_files(self, vendor_dir: Path, result: ValidationResult) -> None:
        for file_path in REQUIRED_CHARM_FILES:
            if not (vendor_dir / file_path).exists():
                result.add_issue("error", "structure", f"Missing required file: {file_path}", file_path=file_path)
    
    def _validate_charmcraft_yaml(self, vendor_dir: Path, result: ValidationResult) -> None:
        path = vendor_dir / "charmcraft.yaml"
        if not path.exists():
            return
        
        try:
            content = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            result.add_issue("error", "yaml", f"Invalid YAML: {e}", file_path="charmcraft.yaml")
            return
        
        for fld in ["type", "name", "subordinate"]:
            if fld not in content:
                result.add_issue("error", "charmcraft", f"Missing field: {fld}", file_path="charmcraft.yaml")
        
        if content.get("type") != "charm":
            result.add_issue("error", "charmcraft", f"Invalid type: {content.get('type')}", file_path="charmcraft.yaml")
        
        if "requires" not in content or "cinder-volume" not in content.get("requires", {}):
            result.add_issue("error", "charmcraft", "Missing cinder-volume relation", file_path="charmcraft.yaml")
    
    def _validate_charm_py(self, vendor_dir: Path, result: ValidationResult) -> None:
        path = vendor_dir / "src" / "charm.py"
        if not path.exists():
            return
        
        content = path.read_text()
        
        if "ops_sunbeam" not in content:
            result.add_issue("warning", "charm", "Not using ops_sunbeam library", file_path="src/charm.py")
        
        if "class " not in content or "Charm" not in content:
            result.add_issue("error", "charm", "No charm class defined", file_path="src/charm.py")
        
        if "@sunbeam_tracing.trace_sunbeam_charm" not in content:
            result.add_issue("warning", "charm", "Missing tracing decorator", file_path="src/charm.py")
    
    def _validate_backend_py(self, vendor_dir: Path, result: ValidationResult) -> None:
        path = vendor_dir / "backend" / "backend.py"
        if not path.exists():
            return
        
        content = path.read_text()
        
        if "StorageBackendConfig" not in content:
            result.add_issue("error", "backend", "Missing StorageBackendConfig", file_path="backend/backend.py")
        
        if "StorageBackendBase" not in content:
            result.add_issue("error", "backend", "Missing StorageBackendBase", file_path="backend/backend.py")
        
        if "backend_type" not in content:
            result.add_issue("error", "backend", "Missing backend_type", file_path="backend/backend.py")
        
        if "SPDX-FileCopyrightText" not in content:
            result.add_issue("warning", "backend", "Missing SPDX-FileCopyrightText header", file_path="backend/backend.py")
        
        if "SPDX-License-Identifier" not in content:
            result.add_issue("warning", "backend", "Missing SPDX-License-Identifier header", file_path="backend/backend.py")
    
    # =========================================================================
    # Spec-Based Validation
    # =========================================================================
    
    def _validate_against_spec(self, vendor_dir: Path, spec: dict, result: ValidationResult) -> None:
        """Validate generated files against the YAML spec."""
        spec = dict(spec)
        user_option_names = {opt["name"] for opt in spec.get("config_options", [])}
        spec["config_options"] = _normalize_config_options(
            spec.get("config_options", []), spec
        )
        spec["_auto_injected"] = {
            opt["name"] for opt in spec["config_options"]
        } - user_option_names
        self._validate_config_options_in_charmcraft(vendor_dir, spec, result)
        self._validate_type_overrides_in_charm(vendor_dir, spec, result)
        self._validate_cli_fields_in_backend(vendor_dir, spec, result)
        self._validate_naming_conventions(vendor_dir, spec, result)
        self._validate_test_completeness(vendor_dir, spec, result)
        self._validate_backend_defaults(vendor_dir, spec, result)
    
    def _validate_config_options_in_charmcraft(self, vendor_dir: Path, spec: dict, result: ValidationResult) -> None:
        """Verify all config options from spec are in charmcraft.yaml."""
        path = vendor_dir / "charmcraft.yaml"
        if not path.exists():
            return
        
        try:
            charmcraft = yaml.safe_load(path.read_text())
        except yaml.YAMLError:
            return
        
        generated_options = charmcraft.get("config", {}).get("options", {})
        generated_option_names = set(generated_options.keys())
        spec_options = {opt["name"] for opt in spec.get("config_options", [])}
        spec_options_by_name = {opt["name"]: opt for opt in spec.get("config_options", [])}
        
        auto_injected = spec.get("_auto_injected", set())

        missing = spec_options - generated_option_names
        for opt in missing:
            if opt in auto_injected:
                result.add_issue("warning", "spec", f"Auto-injected config option missing from charmcraft.yaml: {opt}", file_path="charmcraft.yaml")
            else:
                result.add_issue("error", "spec", f"Config option missing from charmcraft.yaml: {opt}", file_path="charmcraft.yaml")
        
        expected_extras = {"volume-backend-name", "backend-availability-zone"}
        if spec.get("unsupported_driver"):
            expected_extras.add("enable-unsupported-driver")

        extra = generated_option_names - spec_options - expected_extras
        for opt in extra:
            result.add_issue("info", "spec", f"Extra config option in charmcraft.yaml: {opt}", file_path="charmcraft.yaml")
        
        # Check types match (especially secret vs string)
        for opt_name in spec_options & generated_option_names:
            spec_opt = spec_options_by_name[opt_name]
            gen_opt = generated_options[opt_name]
            spec_type = spec_opt.get("type", "string")
            gen_type = gen_opt.get("type", "string")
            if spec_type == "secret" and gen_type != "secret":
                result.add_issue(
                    "error", "spec",
                    f"Config option '{opt_name}' should be type: secret, got type: {gen_type}",
                    file_path="charmcraft.yaml",
                )
        
        # Check required fields don't have default: null
        for opt_name in spec_options & generated_option_names:
            spec_opt = spec_options_by_name[opt_name]
            gen_opt = generated_options[opt_name]
            if spec_opt.get("required") and "default" in gen_opt and gen_opt["default"] is None:
                result.add_issue(
                    "warning", "spec",
                    f"Required config option '{opt_name}' should not have default: null (omit default key)",
                    file_path="charmcraft.yaml",
                )
    
    def _validate_type_overrides_in_charm(self, vendor_dir: Path, spec: dict, result: ValidationResult) -> None:
        """Verify required type overrides are in charm.py."""
        path = vendor_dir / "src" / "charm.py"
        if not path.exists():
            return

        content = path.read_text()
        config_options = spec.get("config_options", [])
        override_info = detect_type_overrides(config_options, spec=spec)

        for opt_name, info in override_info["overrides"].items():
            if f'"{opt_name}"' not in content:
                result.add_issue(
                    "error", "spec",
                    f"Type override missing in charm.py: {opt_name}",
                    file_path="src/charm.py",
                )
                continue

            otype = info["type"]
            if otype in ("secret", "secret_group") and "secret_validator" not in content:
                result.add_issue(
                    "error", "spec",
                    f"Secret validator missing for: {opt_name}",
                    file_path="src/charm.py",
                )
            if otype == "required" and "sunbeam_storage.Required" not in content:
                result.add_issue(
                    "error", "spec",
                    f"sunbeam_storage.Required missing for required field: {opt_name}",
                    file_path="src/charm.py",
                )
            if otype == "literal" and "typing.Literal" not in content:
                result.add_issue(
                    "error", "spec",
                    f"typing.Literal missing for: {opt_name}",
                    file_path="src/charm.py",
                )
            if otype in ("required_group", "secret_group") and "RequiredIfGroup" not in content:
                result.add_issue(
                    "error", "spec",
                    f"RequiredIfGroup missing for group field: {opt_name}",
                    file_path="src/charm.py",
                )

        # Check enum classes are defined
        for enum_info in override_info["enums"]:
            enum_name = enum_info["name"]
            if f"class {enum_name}(StrEnum)" not in content:
                result.add_issue(
                    "error", "spec",
                    f"StrEnum class missing: {enum_name}",
                    file_path="src/charm.py",
                )

        # Check remove_base_config entries produce overrides.pop() calls
        for name in override_info.get("remove_base_config", []):
            if f'"{name}"' not in content:
                result.add_issue(
                    "warning", "spec",
                    f"Base class config '{name}' should be removed via overrides.pop()",
                    file_path="src/charm.py",
                )

        # Check unsupported_driver adds enable-unsupported-driver
        if override_info.get("unsupported_driver"):
            if '"enable-unsupported-driver"' not in content:
                result.add_issue(
                    "error", "spec",
                    "Missing enable-unsupported-driver override for unsupported driver",
                    file_path="src/charm.py",
                )
    
    def _validate_cli_fields_in_backend(self, vendor_dir: Path, spec: dict, result: ValidationResult) -> None:
        """Verify CLI-prompted fields are in backend.py."""
        path = vendor_dir / "backend" / "backend.py"
        if not path.exists():
            return
        
        content = path.read_text()
        cli_fields = [opt for opt in spec.get("config_options", []) if opt.get("cli_prompt")]
        
        for field in cli_fields:
            # Convert hyphenated name to snake_case for Python
            field_name = field["name"].replace("-", "_")
            if field_name not in content:
                result.add_issue("warning", "spec", f"CLI field may be missing in backend.py: {field['name']}", file_path="backend/backend.py")
        
        # Check for SecretDictField usage for secrets
        for field in cli_fields:
            if field.get("type") == "secret":
                secret_key = field.get("secret_key", "token")
                if f'SecretDictField(field="{secret_key}")' not in content:
                    result.add_issue("error", "spec", f"SecretDictField missing for: {field['name']}", file_path="backend/backend.py")
    
    def _validate_naming_conventions(self, vendor_dir: Path, spec: dict, result: ValidationResult) -> None:
        """Verify correct naming conventions are used."""
        vendor = spec.get("vendor", "")
        expected_pascal = to_pascal_case(vendor)
        charm_name = spec.get("charm", {}).get("name", f"cinder-volume-{vendor.lower()}")
        
        # Check charm.py class name
        charm_path = vendor_dir / "src" / "charm.py"
        if charm_path.exists():
            content = charm_path.read_text()
            expected_class = f"CinderVolume{expected_pascal}OperatorCharm"
            if expected_class not in content:
                result.add_issue("error", "naming", f"Expected class name: {expected_class}", file_path="src/charm.py")
        
        # Check backend.py class names
        backend_path = vendor_dir / "backend" / "backend.py"
        if backend_path.exists():
            content = backend_path.read_text()
            if f"{expected_pascal}Config" not in content:
                result.add_issue("error", "naming", f"Expected config class: {expected_pascal}Config", file_path="backend/backend.py")
            if f"{expected_pascal}Backend" not in content:
                result.add_issue("error", "naming", f"Expected backend class: {expected_pascal}Backend", file_path="backend/backend.py")
        
        # Check charmcraft.yaml name
        charmcraft_path = vendor_dir / "charmcraft.yaml"
        if charmcraft_path.exists():
            try:
                charmcraft = yaml.safe_load(charmcraft_path.read_text())
                if charmcraft.get("name") != charm_name:
                    result.add_issue("error", "naming", f"Expected charm name: {charm_name}", file_path="charmcraft.yaml")
            except yaml.YAMLError:
                pass


    def _validate_test_completeness(self, vendor_dir: Path, spec: dict, result: ValidationResult) -> None:
        """Verify the test file includes proper setup logic."""
        path = vendor_dir / "tests" / "unit" / "test_charm.py"
        if not path.exists():
            result.add_issue("warning", "test", "Missing test file: tests/unit/test_charm.py", file_path="tests/unit/test_charm.py")
            return
        
        content = path.read_text()
        
        has_secrets = any(opt.get("type") == "secret" for opt in spec.get("config_options", []))
        
        if has_secrets:
            if "add_user_secret" not in content:
                result.add_issue("warning", "test", "Test missing add_user_secret() for secret handling", file_path="tests/unit/test_charm.py")
            if "grant_secret" not in content:
                result.add_issue("warning", "test", "Test missing grant_secret() for secret handling", file_path="tests/unit/test_charm.py")
        
        if "add_complete_cinder_volume_relation" not in content and "add_relation" not in content:
            result.add_issue("warning", "test", "Test missing cinder-volume relation setup", file_path="tests/unit/test_charm.py")
        
        if "update_config" not in content:
            result.add_issue("warning", "test", "Test missing update_config() with required fields", file_path="tests/unit/test_charm.py")
    
    def _validate_backend_defaults(self, vendor_dir: Path, spec: dict, result: ValidationResult) -> None:
        """Verify backend.py optional fields use None defaults, not explicit values."""
        path = vendor_dir / "backend" / "backend.py"
        if not path.exists():
            return
        
        content = path.read_text()
        
        base_class_fields = {"volume_backend_name", "backend_availability_zone"}
        for field_name in base_class_fields:
            if re.search(rf'\b{field_name}\s*:', content):
                result.add_issue(
                    "warning", "spec",
                    f"Field '{field_name}' should not be in vendor Config class (inherited from base)",
                    file_path="backend/backend.py",
                )


def validate_against_spec(vendor: str, spec_path: str) -> ValidationResult:
    """Convenience function to validate a charm against a spec."""
    validator = CharmValidator()
    return validator.validate(vendor, spec_path)


def compare_charms(vendor1: str, vendor2: str) -> dict[str, Any]:
    """Compare two generated charms."""
    dir1 = GENERATED_CHARMS_DIR / vendor1
    dir2 = GENERATED_CHARMS_DIR / vendor2
    
    if not dir1.exists():
        return {"error": f"Vendor not found: {vendor1}"}
    if not dir2.exists():
        return {"error": f"Vendor not found: {vendor2}"}
    
    def get_files(d: Path) -> set[str]:
        return {str(p.relative_to(d)) for p in d.rglob("*") if p.is_file()}
    
    files1, files2 = get_files(dir1), get_files(dir2)
    
    return {
        "vendor1": vendor1,
        "vendor2": vendor2,
        "vendor1_file_count": len(files1),
        "vendor2_file_count": len(files2),
        "common_files": sorted(files1 & files2),
        "only_in_vendor1": sorted(files1 - files2),
        "only_in_vendor2": sorted(files2 - files1),
    }
