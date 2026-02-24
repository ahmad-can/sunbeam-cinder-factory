"""Tests for charm_generator.generator module."""

from pathlib import Path

import pytest

from charm_generator.generator import CharmGenerator, GenerationResult
from charm_generator.settings import DRIVER_SPECS_DIR


class TestGenerationResult:
    def test_defaults(self):
        result = GenerationResult(vendor="test")
        assert result.vendor == "test"
        assert result.success is False
        assert result.output_dir is None
        assert result.files_generated == []
        assert result.duration_seconds == 0.0
        assert result.tokens_used == 0
        assert result.error_message == ""


class TestCharmGenerator:
    def test_init_default_dirs(self):
        gen = CharmGenerator()
        assert gen.specs_dir == DRIVER_SPECS_DIR

    def test_init_custom_dirs(self, tmp_path):
        gen = CharmGenerator(specs_dir=tmp_path / "specs", output_dir=tmp_path / "output")
        assert gen.specs_dir == tmp_path / "specs"
        assert gen.output_dir == tmp_path / "output"

    def test_load_driver_spec(self):
        gen = CharmGenerator()
        spec = gen.load_driver_spec("pure.yaml")
        assert spec["vendor"] == "purestorage"
        assert "config_options" in spec

    def test_load_driver_spec_not_found(self, tmp_path):
        gen = CharmGenerator(specs_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            gen.load_driver_spec("nonexistent.yaml")

    def test_list_available_specs(self):
        gen = CharmGenerator()
        specs = gen.list_available_specs()
        assert len(specs) >= 2
        names = [s.name for s in specs]
        assert "pure.yaml" in names
        assert "hitachi.yaml" in names

    def test_generate_bad_spec(self, tmp_path):
        gen = CharmGenerator(specs_dir=tmp_path)
        result = gen.generate("nonexistent.yaml")
        assert result.success is False
        assert "Failed to load spec" in result.error_message


class TestSettings:
    def test_settings_import(self):
        from charm_generator.settings import (
            PROJECT_ROOT,
            DRIVER_SPECS_DIR,
            GENERATED_CHARMS_DIR,
            REFERENCE_DIR,
            REQUIRED_CHARM_FILES,
            get_settings_summary,
        )
        assert PROJECT_ROOT.exists()
        assert DRIVER_SPECS_DIR.exists()
        assert len(REQUIRED_CHARM_FILES) > 0

    def test_settings_summary(self):
        from charm_generator.settings import get_settings_summary
        summary = get_settings_summary()
        assert "openai_model" in summary
        assert "max_tokens" in summary
        assert "temperature" in summary
