from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceFile:
    path: Path
    rel_path: str
    suffix: str
    size: int


@dataclass
class FrameworkDetection:
    framework: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    possible_alternatives: list[str] = field(default_factory=list)


@dataclass
class CompatibilityProfile:
    framework: str
    profile: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    version_hints: list[str] = field(default_factory=list)
    deprecated_patterns: list[str] = field(default_factory=list)
    unknown_patterns: list[str] = field(default_factory=list)


@dataclass
class DocsEvidence:
    framework: str
    aliases: list[str] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    verification_recommended: bool = False
    reasons: list[str] = field(default_factory=list)


@dataclass
class IdentityFragment:
    kind: str
    name: str
    text: str
    source: str


@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]
    source: str
    manual_review: bool = False


@dataclass
class ExtractionResult:
    identity_fragments: list[IdentityFragment] = field(default_factory=list)
    rules: list[IdentityFragment] = field(default_factory=list)
    model_preferences: list[IdentityFragment] = field(default_factory=list)
    tools: list[ToolSchema] = field(default_factory=list)
    manual_review: list[str] = field(default_factory=list)
    hierarchy: list[dict[str, str]] = field(default_factory=list)
    crewai_runtime: dict[str, Any] = field(default_factory=dict)
    graph_topology: dict[str, Any] = field(default_factory=dict)
    langchain_runtime: dict[str, Any] = field(default_factory=dict)


@dataclass
class PortPlan:
    name: str
    framework: FrameworkDetection
    extraction: ExtractionResult
    source_path: Path
    output_path: Path
    compatibility: CompatibilityProfile | None = None
    docs_evidence: DocsEvidence | None = None


@dataclass
class ValidationResult:
    mode: str
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PortResult:
    output_path: Path
    generated_files: list[str]
    detection: FrameworkDetection
    validation: ValidationResult | None = None
