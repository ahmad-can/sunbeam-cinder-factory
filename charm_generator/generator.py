"""Main charm generation orchestrator."""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from charm_generator.settings import DRIVER_SPECS_DIR, GENERATED_CHARMS_DIR
from charm_generator.prompts import assemble_prompts
from charm_generator.file_writer import CharmFileWriter

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result of a charm generation operation."""
    vendor: str
    success: bool = False
    output_dir: Path | None = None
    files_generated: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    tokens_used: int = 0
    error_message: str = ""


class CharmGenerator:
    """Orchestrator for charm generation."""
    
    def __init__(
        self,
        specs_dir: Path | str | None = None,
        output_dir: Path | str | None = None,
    ):
        self.specs_dir = Path(specs_dir) if specs_dir else DRIVER_SPECS_DIR
        self.output_dir = Path(output_dir) if output_dir else GENERATED_CHARMS_DIR
        self.file_writer = CharmFileWriter(self.output_dir)
        self._api_client = None
    
    @property
    def api_client(self):
        """Lazy-load API client."""
        if self._api_client is None:
            from charm_generator.openai_client import CharmGeneratorClient
            self._api_client = CharmGeneratorClient()
        return self._api_client
    
    def load_driver_spec(self, spec_path: Path | str) -> dict[str, Any]:
        """Load a driver specification from YAML file."""
        spec_path = Path(spec_path)
        
        if not spec_path.exists() and not spec_path.is_absolute():
            spec_path = self.specs_dir / spec_path
        
        if not spec_path.exists():
            raise FileNotFoundError(f"Driver spec not found: {spec_path}")
        
        return yaml.safe_load(spec_path.read_text())
    
    def list_available_specs(self) -> list[Path]:
        """List all available driver specification files."""
        return sorted(self.specs_dir.glob("*.yaml"))
    
    def generate(
        self,
        spec_path: Path | str,
        overwrite: bool = True,
    ) -> GenerationResult:
        """Generate a charm from a driver specification."""
        start_time = time.time()
        
        try:
            spec = self.load_driver_spec(spec_path)
        except Exception as e:
            return GenerationResult(vendor="unknown", error_message=f"Failed to load spec: {e}")
        
        vendor = spec.get("vendor", "unknown")
        charm_name = spec.get("charm", {}).get("name", f"cinder-volume-{vendor}")
        result = GenerationResult(vendor=charm_name)
        
        try:
            system_prompt, user_prompt = assemble_prompts(spec)
            
            logger.info(f"Generating charm: {charm_name}")
            file_map, api_metrics = self.api_client.generate_charm_files(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                vendor=charm_name,
            )
            
            output_dir = self.file_writer.write_charm(
                vendor=charm_name,
                file_map=file_map,
                overwrite=overwrite,
            )
            
            result.success = True
            result.output_dir = output_dir
            result.files_generated = list(file_map.keys())
            result.duration_seconds = time.time() - start_time
            result.tokens_used = api_metrics.total_tokens
            
            logger.info(f"Generated {len(file_map)} files in {result.duration_seconds:.2f}s")
            
        except Exception as e:
            result.error_message = str(e)
            result.duration_seconds = time.time() - start_time
            logger.error(f"Generation failed: {e}")
        
        return result


def setup_logging(level: str = "INFO") -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
