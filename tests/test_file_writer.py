"""Tests for charm_generator.file_writer module."""

from pathlib import Path

import pytest

from charm_generator.file_writer import CharmFileWriter


@pytest.fixture
def writer(tmp_path):
    return CharmFileWriter(output_dir=tmp_path)


class TestCharmFileWriter:
    def test_write_charm(self, writer, tmp_path):
        file_map = {
            "charmcraft.yaml": "type: charm\nname: test\n",
            "src/charm.py": "# charm code\n",
            "backend/backend.py": "# backend code\n",
            "backend/__init__.py": "",
        }
        output = writer.write_charm("test-vendor", file_map)
        assert output == tmp_path / "test-vendor"
        assert (tmp_path / "test-vendor" / "charmcraft.yaml").exists()
        assert (tmp_path / "test-vendor" / "src" / "charm.py").exists()
        assert (tmp_path / "test-vendor" / "backend" / "backend.py").exists()
        assert (tmp_path / "test-vendor" / "backend" / "__init__.py").exists()

    def test_write_charm_creates_directories(self, writer, tmp_path):
        file_map = {"nested/deep/file.txt": "content"}
        writer.write_charm("test-vendor", file_map)
        assert (tmp_path / "test-vendor" / "nested" / "deep" / "file.txt").exists()

    def test_write_charm_no_overwrite(self, writer, tmp_path):
        file_map = {"test.txt": "original"}
        writer.write_charm("test-vendor", file_map)
        file_map = {"test.txt": "overwritten"}
        writer.write_charm("test-vendor", file_map, overwrite=False)
        content = (tmp_path / "test-vendor" / "test.txt").read_text()
        assert content == "original"

    def test_write_charm_overwrite(self, writer, tmp_path):
        file_map = {"test.txt": "original"}
        writer.write_charm("test-vendor", file_map)
        file_map = {"test.txt": "overwritten"}
        writer.write_charm("test-vendor", file_map, overwrite=True)
        content = (tmp_path / "test-vendor" / "test.txt").read_text()
        assert content == "overwritten"

    def test_list_generated_vendors(self, writer, tmp_path):
        (tmp_path / "vendor-a").mkdir()
        (tmp_path / "vendor-b").mkdir()
        (tmp_path / ".hidden").mkdir()
        vendors = writer.list_generated_vendors()
        assert "vendor-a" in vendors
        assert "vendor-b" in vendors
        assert ".hidden" not in vendors

    def test_list_generated_vendors_empty(self, tmp_path):
        empty_writer = CharmFileWriter(output_dir=tmp_path / "nonexistent")
        assert empty_writer.list_generated_vendors() == []

    def test_get_charm_files(self, writer, tmp_path):
        vendor_dir = tmp_path / "test-vendor"
        vendor_dir.mkdir()
        (vendor_dir / "file1.txt").write_text("a")
        sub = vendor_dir / "sub"
        sub.mkdir()
        (sub / "file2.txt").write_text("b")
        files = writer.get_charm_files("test-vendor")
        assert len(files) == 2

    def test_get_charm_files_nonexistent(self, writer):
        assert writer.get_charm_files("nonexistent") == []

    def test_delete_charm(self, writer, tmp_path):
        vendor_dir = tmp_path / "test-vendor"
        vendor_dir.mkdir()
        (vendor_dir / "file.txt").write_text("content")
        assert writer.delete_charm("test-vendor") is True
        assert not vendor_dir.exists()

    def test_delete_charm_nonexistent(self, writer):
        assert writer.delete_charm("nonexistent") is False
