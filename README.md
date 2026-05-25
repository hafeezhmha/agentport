# AgentPort

AgentPort is a CLI-first multi-agent GitAgent porting system. It ports the portable identity layer of existing framework agents into GitAgent/Open GAP-style repos.

It does not execute untrusted source repository code. The MVP uses deterministic scanners before any LLM or agent reasoning.

## Supported MVP Sources

- CrewAI-style Python repos
- LangGraph/LangChain-style Python repos
- Claude/Cursor instruction repos

## Usage

```bash
cd agentport
python -m agentport.cli.main analyze --source ../examples/crewai-demo-agent
python -m agentport.cli.main port --source ../examples/crewai-demo-agent --output ./generated/crewai-demo-gitagent --validate --pr-ready
python -m agentport.cli.main docs check --framework crewai
python -m agentport.cli.main docs check --source ../examples/crewai-demo-agent
```

## Validation

`--validate` honors `--validator-command` first, then `AGENTPORT_VALIDATOR_COMMAND` when set. Use `{path}` as a placeholder for the generated repo path; if no placeholder is present, AgentPort appends the path.

```bash
python -m agentport.cli.main port --source tests/fixtures/crewai_schema_current --output /tmp/agentport-out --validate \
  --validator-command "gitagent validate {path}"

AGENTPORT_VALIDATOR_COMMAND="gitagent validate {path}" \
  python -m agentport.cli.main port --source tests/fixtures/crewai_schema_current --output /tmp/agentport-out --validate
```

When no override or external `gapman`/`gitagent` binary is available, AgentPort uses its internal schema fallback.

## Outputs

- `agent.yaml`
- `SOUL.md`
- `RULES.md`
- `DUTIES.md`
- `skills/`
- `tools/`
- `workflows/`
- `knowledge/`
- `memory/`
- `conversion_map.json`
- `migration_report.md`
- `TODO_MANUAL_REVIEW.md`
- `validation_report.json`
- `framework_compatibility_report.md`
- `registry_readiness_report.md`
- `PULL_REQUEST.md` when `--pr-ready` is used

## Boundary

This migration ports the agent identity layer, not the full runtime implementation. Runtime orchestration, async loops, memory I/O, callbacks, deployment wiring, vector DB connections, and secrets are flagged for manual review.

## Compatibility Coverage

The MVP includes schema-focused fixtures and tests for current documented framework shapes:

- CrewAI `agents.yaml`, `tasks.yaml`, direct `Agent(...)` / `Task(...)`, `@CrewBase`, `@agent`, `@task`, `@crew`, tools, guardrails, `output_json`, `output_pydantic`, and hierarchical process markers.
- LangGraph `StateGraph`, prompt/model constants, `add_node`, `add_edge`, `add_conditional_edges`, `Command`, and `Send` markers.
- Claude/Cursor `CLAUDE.md`, `.claude/CLAUDE.md`, `CLAUDE.local.md`, Claude `@path` imports, `.cursorrules`, and `.cursor/rules/*.mdc` frontmatter.

Runtime behavior remains manual review by design.

AgentPort also emits a compatibility profile in `analyze`, `conversion_map.json`, `migration_report.md`, and `framework_compatibility_report.md`.

Current profiles include:

- `crewai-modern-yaml`
- `crewai-legacy-code-only`
- `crewai-yaml-with-custom-loader`
- `langgraph-v1`
- `langgraph-v0-or-legacy`
- `langchain-agentexecutor`
- `cursor-mdc-rules`
- `cursor-legacy-cursorrules`
- `cursor-mdc-plus-legacy-cursorrules`
- `claude-project-memory`
- `generic-static-identity`

## Documentation Evidence

AgentPort loads preseeded framework documentation links from `agents/agentport/knowledge/framework-docs/framework-links.md`.

Use:

```bash
python -m agentport.cli.main docs check --framework adk --json
python -m agentport.cli.main docs check --source tests/fixtures/langchain_agentexecutor_legacy --json
```

Generated ports include docs evidence and verification recommendations in `conversion_map.json`, `migration_report.md`, `framework_compatibility_report.md`, and PR-ready output.
