"""Typed, offline configuration for templates and governance."""
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class BudgetConfig(BaseModel):
    target_words: int = Field(default=500, ge=1)
    target_pages: float | None = Field(default=None, gt=0)
    tolerance: float = Field(default=0.10, ge=0, lt=1)


class GovernanceConfig(BaseModel):
    semantic_green: float = Field(default=0.75, ge=0, le=1)
    semantic_red: float = Field(default=0.50, ge=0, le=1)
    fillers: tuple[str, ...] = ()


class TemplateGovernanceConfig(BaseModel):
    template: str = "Sección experimental"
    phases: tuple[str, ...] = (
        "PARAMETRIZATION", "CURATION", "DRAFTING", "ASSEMBLY"
    )
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    governance: GovernanceConfig = Field(default_factory=GovernanceConfig)


def load_governance_config(path: str | Path | None = None) -> TemplateGovernanceConfig:
    """Load optional YAML without making network calls or requiring PyYAML."""
    if path is None:
        return TemplateGovernanceConfig()
    source = Path(path)
    if not source.exists():
        return TemplateGovernanceConfig()
    try:
        import yaml  # type: ignore
    except ImportError:
        # Keep the common scalar subset usable in minimal offline installs.
        values: dict[str, Any] = {}
        section = None
        for line in source.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].rstrip()
            if not line or ":" not in line:
                continue
            key, value = line.strip().split(":", 1)
            if line.startswith(" "):
                section_name = section or "governance"
                if not isinstance(values.get(section_name), dict):
                    values[section_name] = {}
                values[section_name][key] = value.strip()
            else:
                section = key
                values[key] = value.strip()
        raw = values
    else:
        raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    return TemplateGovernanceConfig.model_validate(raw)
