"""File writer for charm generation output."""

import logging
import shutil
from pathlib import Path

from charm_generator.settings import GENERATED_CHARMS_DIR

logger = logging.getLogger(__name__)


class CharmFileWriter:
    """Handles writing generated charm files to disk."""
    
    def __init__(self, output_dir: Path | str | None = None):
        self.output_dir = Path(output_dir) if output_dir else GENERATED_CHARMS_DIR
    
    def write_charm(
        self,
        vendor: str,
        file_map: dict[str, str],
        overwrite: bool = True,
    ) -> Path:
        """Write all generated charm files for a vendor."""
        vendor_dir = self.output_dir / vendor
        vendor_dir.mkdir(parents=True, exist_ok=True)
        
        for file_path, content in file_map.items():
            full_path = vendor_dir / file_path
            
            if full_path.exists() and not overwrite:
                logger.warning(f"Skipping existing file: {file_path}")
                continue
            
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
        
        logger.info(f"Wrote {len(file_map)} files to {vendor_dir}")
        return vendor_dir
    
    def list_generated_vendors(self) -> list[str]:
        """List all vendors with generated charms."""
        if not self.output_dir.exists():
            return []
        return sorted(d.name for d in self.output_dir.iterdir() if d.is_dir() and not d.name.startswith("."))
    
    def get_charm_files(self, vendor: str) -> list[str]:
        """Get all files in a vendor's charm directory."""
        vendor_dir = self.output_dir / vendor
        if not vendor_dir.exists():
            return []
        return [str(p.relative_to(vendor_dir)) for p in vendor_dir.rglob("*") if p.is_file()]
    
    def delete_charm(self, vendor: str) -> bool:
        """Delete a vendor's charm directory."""
        vendor_dir = self.output_dir / vendor
        if not vendor_dir.exists():
            return False
        shutil.rmtree(vendor_dir)
        return True
