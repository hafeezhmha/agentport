from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict

from agentport.models import LLMReviewResult, PortPlan, ValidationResult

DEFAULT_BASE_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4.1-mini"
REPORT_PATH = "LLM_REVIEW.md"


def write_llm_review(plan: PortPlan, validation: ValidationResult | None) -> LLMReviewResult:
    output_path = plan.output_path / REPORT_PATH
    api_key = os.environ.get("AGENTPORT_LLM_API_KEY", "").strip()
    base_url = os.environ.get("AGENTPORT_LLM_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    model = os.environ.get("AGENTPORT_LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

    if not api_key:
        output_path.write_text(_skipped_report(model), encoding="utf-8")
        return LLMReviewResult(status="skipped", model=model, report_path=REPORT_PATH, error="AGENTPORT_LLM_API_KEY is not set.")

    prompt = _review_prompt(plan, validation)
    try:
        content = _chat_completion(base_url, api_key, model, prompt)
    except Exception as exc:
        output_path.write_text(_failed_report(model, exc), encoding="utf-8")
        return LLMReviewResult(status="failed", model=model, report_path=REPORT_PATH, error=str(exc))

    output_path.write_text(_completed_report(model, content), encoding="utf-8")
    return LLMReviewResult(status="completed", model=model, report_path=REPORT_PATH)


def _chat_completion(base_url: str, api_key: str, model: str, prompt: str) -> str:
    body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are AgentPort's migration reviewer. Use only the provided deterministic evidence. "
                    "Do not claim runtime equivalence. Be concise, concrete, and action oriented."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        base_url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM request failed with HTTP {exc.code}: {detail}") from exc

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("LLM response did not include choices.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM response did not include message content.")
    return content.strip()


def _review_prompt(plan: PortPlan, validation: ValidationResult | None) -> str:
    evidence = {
        "source": str(plan.source_path),
        "output": str(plan.output_path),
        "framework": asdict(plan.framework),
        "compatibility": asdict(plan.compatibility) if plan.compatibility else None,
        "docs_evidence": asdict(plan.docs_evidence) if plan.docs_evidence else None,
        "identity_fragments": [asdict(item) for item in plan.extraction.identity_fragments[:20]],
        "rules": [asdict(item) for item in plan.extraction.rules[:20]],
        "model_preferences": [asdict(item) for item in plan.extraction.model_preferences[:10]],
        "tools": [asdict(item) for item in plan.extraction.tools[:20]],
        "manual_review": plan.extraction.manual_review[:40],
        "hierarchy": plan.extraction.hierarchy[:40],
        "crewai_runtime": plan.extraction.crewai_runtime,
        "graph_topology": plan.extraction.graph_topology,
        "langchain_runtime": plan.extraction.langchain_runtime,
        "validation": asdict(validation) if validation else None,
    }
    return "\n".join(
        [
            "Review this AgentPort migration using only the deterministic evidence below.",
            "",
            "Write Markdown with these sections:",
            "- Summary",
            "- Ambiguous Mappings",
            "- Identity File Improvements",
            "- Validation And Manual Fixes",
            "- Demo Talking Points",
            "",
            "Rules:",
            "- Do not invent source behavior.",
            "- Do not claim full runtime conversion.",
            "- Tie recommendations to the evidence.",
            "- Keep the output short enough for a migration reviewer.",
            "",
            "Evidence JSON:",
            json.dumps(evidence, indent=2),
        ]
    )


def _skipped_report(model: str) -> str:
    return "\n".join(
        [
            "# LLM Review",
            "",
            "Status: skipped",
            "",
            "The deterministic scanner, generator, and validator still completed normally. No LLM review was requested from a provider because `AGENTPORT_LLM_API_KEY` is not set.",
            "",
            "To enable the optional reviewer layer:",
            "",
            "```bash",
            "export AGENTPORT_LLM_API_KEY=...",
            f"export AGENTPORT_LLM_MODEL={model}",
            "python -m agentport.cli.main port --source <repo> --output <out> --validate --llm-review",
            "```",
            "",
            "Boundary: the LLM reviewer is advisory only. Deterministic extraction and validation remain the source of truth.",
        ]
    )


def _failed_report(model: str, exc: Exception) -> str:
    return "\n".join(
        [
            "# LLM Review",
            "",
            "Status: failed",
            "",
            f"Model: `{model}`",
            f"Error: `{exc}`",
            "",
            "The port was not failed because the LLM reviewer is advisory only. Deterministic extraction and validation remain the source of truth.",
        ]
    )


def _completed_report(model: str, content: str) -> str:
    return "\n".join(
        [
            "# LLM Review",
            "",
            "Status: completed",
            "",
            f"Model: `{model}`",
            "",
            "Boundary: this review is advisory only. Deterministic extraction and validation remain the source of truth.",
            "",
            content,
        ]
    )
