# AgentPort Progress

Last updated: 2026-05-21

## Current Status

AgentPort is implemented as a CLI-first MVP inside the GitAgent repo at:

`/Users/hafeez/Lyzr/gitagent/agentport`

The product currently ports framework-agent identity layers into GitAgent/Open GAP-style identity repos. It does not execute source repository code and does not claim full runtime equivalence.

## What Was Confirmed

The reference repo `/Users/hafeez/Lyzr/datawise-agent` is multi-agent in the GitAgent repo-native sense. It has:

- root `agent.yaml`
- sub-agents under `agents/`
- skills
- tools
- workflows
- memory

AgentPort mirrors that structure for its own multi-agent identity system.

## What Was Implemented

### CLI

Implemented:

- `python -m agentport.cli.main analyze --source <repo>`
- `python -m agentport.cli.main compatibility --source <repo>`
- `python -m agentport.cli.main explain --source <repo>`
- `python -m agentport.cli.main port --source <repo> --output <path>`
- `python -m agentport.cli.main doctor`
- `--validate`
- `--validator-command`
- `--pr-ready`
- `--json`
- `--no-learn`

There is also a Node wrapper at `cli/agentport.mjs`.

### Deterministic Scanner Layer

Implemented deterministic extraction before any LLM or agentic reasoning:

- repository file scanning
- ignored directory filtering
- framework detection
- Python AST parsing
- static Python string reference resolution for constants, simple static f-strings, and string concatenation
- YAML/JSON loading
- Markdown/instruction extraction
- static tool metadata extraction

Source repo code is never executed.

### Framework Detection

Currently detects:

- CrewAI
- LangGraph/LangChain-style Python repos
- Claude/Cursor instruction repos
- generic fallback when no strong markers are found

Detection returns:

- framework
- confidence
- evidence
- possible alternatives

### CrewAI Extraction

Implemented support for current documented CrewAI shapes:

- `agents.yaml`
- `tasks.yaml`
- `Agent(...)`
- `Task(...)`
- `Crew(...)`
- `@CrewBase`
- `@agent`
- `@task`
- `@crew`
- `role`
- `goal`
- `backstory`
- `description`
- `expected_output`
- string guardrails
- `llm`
- `manager_llm`
- `function_calling_llm`
- static tool references
- YAML tool references from `agents.yaml` and `tasks.yaml`
- YAML `knowledge_sources` as manual-review metadata
- YAML task `context` as manual-review metadata
- multiline YAML fields and YAML anchors/aliases when PyYAML is available
- decorated `@agent` / `@task` functions mapped to static YAML keys when the code uses patterns such as `config=self.agents_config["researcher"]`
- `Process.sequential` / `Process.hierarchical` as manual-review runtime markers
- `output_json` / `output_pydantic` as schema/runtime manual-review markers
- `context` and `async_execution` as manual-review runtime markers

Decorated CrewAI mapping now emits `crewai_config_mapping` identity fragments and hierarchy entries such as:

- `researcher -> config/agents.yaml:researcher`
- `research_task -> config/tasks.yaml:research_task`

Result-level dedupe now removes duplicate identity fragments, rules, model preferences, tool entries, manual-review items, and hierarchy entries.

### LangGraph/LangChain Extraction

Implemented support for current documented LangGraph shapes:

- `StateGraph` import detection
- prompt/instruction constants
- model constants
- `add_node`
- `add_edge`
- `add_conditional_edges`
- `.compile()`
- `Command`
- `Send`

Structured LangGraph topology is now emitted in `conversion_map.json` under `graph_topology`, including:

- source files
- state schemas, including `TypedDict` fields where statically visible
- node list
- edge list
- conditional edge list and literal path maps
- compile calls
- runtime markers for compile options, invoke/ainvoke, stream/astream, and state annotations

Graph topology is preserved as structured evidence, but graph runtime behavior remains manual review.

Implemented first-class LangChain static extraction:

- `initialize_agent`
- `AgentExecutor`
- `create_react_agent`
- `create_structured_chat_agent`
- `create_openai_tools_agent`
- `PromptTemplate.from_template`
- `ChatPromptTemplate.from_messages`
- `@tool` decorated functions
- `Tool` / `StructuredTool` metadata markers
- retriever/vectorstore markers as manual review

Structured LangChain evidence is emitted in `conversion_map.json` under `langchain_runtime`.

### Claude/Cursor Extraction

Implemented support for:

- `CLAUDE.md`
- `.claude/CLAUDE.md`
- `CLAUDE.local.md`
- `CLAUDE.md` `@path` imports
- `.cursorrules`
- `.cursor/rules/*.mdc`
- Cursor MDC frontmatter metadata

### GitAgent Output Generation

Generated output repos include:

- `agent.yaml`
- `SOUL.md`
- `RULES.md`
- `DUTIES.md`
- `skills/ported-identity/SKILL.md`
- `tools/*.yaml` when tools are detected
- `workflows/ported-identity-review.yaml`
- `knowledge/source-framework.md`
- `memory/MEMORY.md`
- `conversion_map.json`
- `TODO_MANUAL_REVIEW.md`
- `migration_report.md`
- `validation_report.json`
- `framework_compatibility_report.md`
- `registry_readiness_report.md`
- `PULL_REQUEST.md` when `--pr-ready` is used

Generated `agent.yaml`, `tools/*.yaml`, and `skills/*/SKILL.md` have been adjusted to pass the currently available `@open-gitagent/gitagent` validator when invoked through `--validator-command`.

### Validation

Implemented:

- Try external `gapman validate --compliance` if available.
- Try external `gitagent validate --compliance` if available.
- Fall back to internal schema validation when neither exists.

The local GitAgent repo at `/Users/hafeez/Lyzr/gitagent` still does not expose a real `validate` command, so current verification uses the internal schema fallback there.
The `datawise-agent` repo at `/Users/hafeez/Lyzr/datawise-agent` does expose a working `gitagent validate` path through `@open-gitagent/gitagent`, and `npm run validate` passes there.

Internal schema validation now checks:

- required generated files
- `agent.yaml` required fields and field types
- `model.preferred`
- tool references resolve to `tools/*.yaml`
- tool YAML contains required fields and object `input_schema`
- skill references resolve to `skills/*/SKILL.md`
- `knowledge.paths` resolve
- `memory.path` resolves
- required generated workflow YAML exists
- workflow YAML parses as a mapping with required `name`, `description`, and non-empty `steps`
- workflow step references to declared agents, skills, and tools resolve when present
- workflow SOD ordering blocks validation auditors before schema writers and PR writers before validation auditors
- declared `compliance.sod_policy` paths resolve
- SOD policy text includes schema-writer, validation, PR-writer, and validation-bypass boundaries
- `conversion_map.json` required fields and types
- conversion boundary states that this is an identity-layer port

Machine-readable validation errors use prefixes such as:

- `missing_file`
- `missing_field`
- `invalid_type`
- `broken_reference`
- `invalid_boundary`

Validation mode is now reported as `internal-schema-fallback`.

### Registry Readiness

Implemented readiness assessment using schema validation results.

`registry_readiness_report.md` now includes:

- readiness score
- `Safe to publish: yes/no`
- schema validation gate
- hard blocker gate
- manual review gate
- runtime equivalence gate
- hard blockers copied from validation errors
- warnings for low framework/profile confidence and open manual review items

Validation failures now block publish readiness. Open manual-review items prevent a generated repo from being marked publish-ready, even when schema validation passes.

### Learning Memory

Implemented basic learning memory updates:

- validation warnings/failures append entries to `agents/agentport/memory/migration-patterns.md`

This is currently simple append-only Markdown memory, not a sophisticated pattern database.

### Multi-Agent Identity System

Created AgentPort's own GitAgent-style multi-agent repo under:

`agentport/agents/agentport`

Includes:

- root orchestrator agent
- `framework-detector`
- `framework-docs-advisor`
- `identity-extractor`
- `tool-schema-extractor`
- `sod-mapper`
- `schema-writer`
- `validation-auditor`
- `pr-writer`
- `learning-agent`
- skills
- tools
- workflow
- memory
- knowledge
- hooks
- SOD compliance policy

### Framework Docs Advisor

Implemented a dedicated `framework-docs-advisor` agent under:

`agents/agentport/agents/framework-docs-advisor`

Purpose:

- act as AgentPort's syntax/documentation advisor
- use preloaded docs links for current and legacy framework APIs
- distinguish current syntax from deprecated or legacy syntax
- recommend parser updates when syntax is unsupported
- request live search/browsing when documentation may have changed or confidence is low

Added:

- `skills/framework-docs-check/SKILL.md`
- `tools/framework-docs-search.yaml`
- `knowledge/framework-docs/framework-links.md`

The link inventory includes CrewAI, LangGraph, LangChain, DeepAgents, Google ADK, Claude Code/Claude SDK, Cursor, OpenAI Agents SDK, AutoGen, Semantic Kernel, Haystack, LlamaIndex, NVIDIA NeMo/AIQ, and a placeholder for Hermes-style repos.

Runtime integration now exists for local/preloaded docs evidence:

- `agentport docs check --framework <name>`
- `agentport docs check --source <repo>`
- `agentport compatibility --source <repo>`
- `agentport explain --source <repo>`
- `agentport doctor`
- docs evidence in `analyze`
- docs evidence in generated `conversion_map.json`
- docs evidence in `migration_report.md`
- docs evidence in `framework_compatibility_report.md`
- docs verification recommendation in PR-ready output

Current limitation: the deterministic CLI uses preloaded links only. It does not yet call live web search automatically. A future implementation should wire the advisor into an actual search/browser adapter or offline docs cache.

### Test Coverage

Current tests:

- framework detection
- CrewAI mapping
- CrewAI static Python reference resolution
- LangGraph detection and structured topology extraction
- LangChain runtime extraction
- GitAgent generation
- internal schema validation fallback
- registry readiness gating
- CLI commands for `doctor`, `compatibility`, `explain`, and end-to-end `analyze` plus `port --validate --json`
- structured golden output assertions for `conversion_map.json`
- normalized Markdown section assertions for `framework_compatibility_report.md`
- structured golden output assertions for generated `agent.yaml`
- normalized line-aware assertions for generated `TODO_MANUAL_REVIEW.md`
- CrewAI YAML hardening for multiline fields, anchors/aliases, YAML tool references, knowledge sources, and task context
- CrewAI decorated function-to-YAML key mapping
- schema compatibility for current CrewAI
- schema compatibility for current LangGraph
- schema compatibility for current LangChain fixtures
- fixture-backed LangChain coverage for `create_structured_chat_agent`, `create_openai_tools_agent`, and legacy `ZeroShotAgent`
- schema compatibility for current Claude/Cursor

Verified command:

```bash
cd /Users/hafeez/Lyzr/gitagent/agentport
python -m unittest discover -s tests
```

Latest result:

```txt
Ran 75 tests
OK
```

## Current Behavior With Old Or Non-Updated Source Repos

AgentPort is tolerant but conservative.

If a source repo uses old framework syntax, deprecated paths, or custom conventions, AgentPort will:

1. Scan the repo statically.
2. Detect whatever known markers are still present.
3. Extract portable identity fields it recognizes.
4. Preserve unknown or runtime-specific items in `TODO_MANUAL_REVIEW.md` and `conversion_map.json`.
5. Generate a GitAgent identity repo if minimum identity evidence exists or fall back to a generic repo if detection is weak.
6. Lower confidence or use `generic` when framework detection is uncertain.
7. Avoid executing the source repo, even if execution might reveal more structure.

This means old repos should not crash the converter just because they use outdated syntax. They may produce a partial migration with more manual-review items.

AgentPort now emits compatibility profiles from source patterns and dependency/version hints. These profiles are precise enough to distinguish modern CrewAI YAML repos from legacy direct-code CrewAI repos, LangGraph v1-style graphs from older graph shapes, legacy LangChain AgentExecutor repos, modern Cursor MDC rules, legacy `.cursorrules`, and Claude project memory.

AgentPort also distinguishes modern LangChain agent factory repos with profile `langchain-modern-agent-factory`.

Important limitation: AgentPort still does not have exact framework-version compatibility matrices. It detects dependency hints and source profiles, but it does not yet interpret every version range semantically.

## What Is Left

### Standalone Repository Split

AgentPort currently lives inside:

`/Users/hafeez/Lyzr/gitagent/agentport`

This was useful for fast MVP development because AgentPort targets GitAgent/Open GAP repo structure and could be built directly beside the GitAgent codebase.

Long term, AgentPort should likely become its own repo/package, for example:

`/Users/hafeez/Lyzr/agentport`

Reason:

- AgentPort is a product above GitAgent, not core GitAgent itself.
- It has its own CLI, tests, fixtures, docs, agents, and generated outputs.
- It should depend on GitAgent/Open GAP primitives instead of living inside the GitAgent repo.
- Independent versioning, packaging, release, and CI will be cleaner.
- It avoids polluting the GitAgent repo with migration fixtures and generated output.

Recommended timing:

- Do not split immediately if active parser/validator work is still moving quickly.
- Split after the deterministic parser/validator MVP is stable enough to run end-to-end.
- A reasonable split point is now approaching because structured LangGraph topology, LangGraph workflow preservation, first-class LangChain extraction, internal schema validation, workflow/SOD validation, CLI preflight/doctor checks, golden output tests, YAML hardening, and CrewAI decorated function-to-YAML mapping are in place. Broader LangChain fixtures should still be completed first.

Migration tasks:

- Move `/Users/hafeez/Lyzr/gitagent/agentport` to `/Users/hafeez/Lyzr/agentport`.
- Update import/test paths.
- Add standalone `.gitignore`.
- Add standalone package metadata.
- Decide how AgentPort finds GitAgent:
  - local path config
  - environment variable
  - CLI path discovery
  - package dependency
  - submodule only if necessary
- Remove or ignore generated demo outputs from version control.
- Add CI for AgentPort tests.
- Keep GitAgent/Open GAP validation integration configurable, not hardcoded to sibling paths.

### Version-Aware Framework Support

Implemented:

- CrewAI version profile detection from `pyproject.toml`, `requirements.txt`, `poetry.lock`, `uv.lock`, and imports.
- LangGraph/LangChain version profile detection.
- Claude/Cursor config version/profile detection where possible.
- Pyproject optional dependency and grouped dependency version hints from `[project.optional-dependencies]`, `[dependency-groups]`, and `[tool.poetry.group.*.dependencies]`.
- Structured `uv.lock` and `poetry.lock` package-block version hints for tracked agent frameworks.
- Compatibility mode labels such as:
  - `crewai-modern-yaml`
  - `crewai-legacy-code-only`
  - `crewai-yaml-with-custom-loader`
  - `langgraph-v1`
  - `langgraph-v0-or-legacy`
  - `langchain-agentexecutor`
  - `langchain-modern-agent-factory`
  - `cursor-mdc-rules`
  - `cursor-legacy-cursorrules`
  - `cursor-mdc-plus-legacy-cursorrules`
  - `claude-project-memory`
  - `generic-static-identity`

Still needed:

- richer semantic version parsing
- version range interpretation
- exact framework-version compatibility matrices
- richer lockfile parser hardening for dependency groups, extras, and nonstandard lock metadata

### Legacy Syntax Fixtures

Implemented fixtures for:

- older CrewAI code-only examples using direct `Agent`, `Task`, `Crew`, no `CrewBase`
- LangChain `initialize_agent`
- LangChain `AgentExecutor`
- LangChain `create_react_agent`
- LangChain `create_structured_chat_agent`
- LangChain `create_openai_tools_agent`
- LangChain `ZeroShotAgent`
- older LangGraph examples without `START` / `END`
- old Cursor `.cursorrules` only
- Claude project memory only

Still needed:

- older CrewAI community examples with nonstandard config paths
- mixed Claude/Cursor repos with multiple instruction files

### Golden Output Tests

Implemented:

- structured JSON assertions for `conversion_map.json`
- normalized Markdown section assertions for `framework_compatibility_report.md`
- fixture-backed coverage for CrewAI and LangGraph output shape
- structured assertions for generated `agent.yaml`
- normalized line-aware assertions for generated `TODO_MANUAL_REVIEW.md`

Avoid brittle full-file snapshots at first. Prefer structured JSON assertions and normalized Markdown section assertions.

### Better YAML Support

Current YAML support uses PyYAML when available and a minimal fallback parser otherwise.

Implemented:

- PyYAML is now a normal package dependency, while the loader keeps JSON/minimal YAML fallbacks
- multiline YAML field coverage in fixtures
- YAML anchors/aliases coverage when PyYAML is available
- CrewAI tool references from YAML lists
- CrewAI `knowledge_sources` as manual-review metadata
- CrewAI task `context` as manual-review metadata
- YAML `llm` captured as model preference
- cleanup to avoid treating anchor/default-only entries as real source agents
- source line numbers for top-level CrewAI YAML fields in manual-review items where statically visible
- CrewAI `knowledge_sources` promoted into high-level `knowledge_source` identity evidence while retaining manual-review warnings
- CrewAI task `context` promoted into high-level `task_context` workflow evidence and generated review workflow prompts while retaining manual-review warnings

Needed:

- parse richer CrewAI knowledge source object shapes beyond static string/path/name/source references
- parse richer task context object shapes beyond static string/task/name/id references

### Better Python AST Extraction

Implemented:

- resolve simple static string references, for example `role=RESEARCHER_ROLE`
- resolve static f-string templates when all formatted values resolve to static strings
- resolve simple string concatenation
- capture class attributes like `agents_config = "config/agents.yaml"`
- map decorated `@agent` functions to YAML keys for static `self.agents_config["key"]` patterns
- map decorated `@task` functions to YAML keys for static `self.tasks_config["key"]` patterns
- dedupe repeated extraction and manual-review evidence
- capture CrewAI runtime metadata such as `allow_delegation`, `max_iter`, `max_execution_time`, `max_rpm`, `respect_context_window`, `memory`, `process`, and manager/model runtime options as structured `crewai_runtime` evidence
- parse statically visible CrewAI `output_json` / `output_pydantic` Pydantic schemas into structured `crewai_runtime.output_schemas` evidence and portable `output_schema` identity notes
- broaden decorated config mapping beyond direct static subscript patterns, including `.get("key")`, module constants, class-level key constants, and local aliases such as `cfg = self.agents_config["researcher"]`

Needed:

- broaden decorated config mapping for more complex dynamic loader/helper function patterns

### LangGraph Topology Extraction

Implemented:

- structured topology object in `conversion_map.json`
- node list
- edge list
- conditional edge list
- state schema summary
- runtime markers for checkpointers, stores, interrupts, streaming, invoke/ainvoke, and state annotations
- graph topology preservation in generated `workflows/ported-identity-review.yaml` as high-level review workflow evidence
- workflow review prompts for LangGraph source files, state schemas, nodes, edges, conditional edges, static route maps, compile calls, and runtime markers
- explicit workflow boundary language that preserved topology evidence is not runtime conversion

Still needed:

- detect LangGraph v0 vs v1 docs/API patterns
- broaden generated workflow shape once the official GitAgent workflow schema is available

### LangChain Agent Support

Implemented first-class static extraction for:

- `initialize_agent`
- `AgentExecutor`
- `create_react_agent`
- `create_structured_chat_agent`
- `create_openai_tools_agent`
- `ZeroShotAgent`
- compatibility profile `langchain-zeroshot-legacy`
- compatibility profile `langchain-tool-args-schema`
- `ChatPromptTemplate`
- `PromptTemplate`
- tool decorators from `langchain.tools`
- decorated LangChain tool function argument schemas from Python signatures, including parameter names, basic type annotations, and required fields
- explicit `Tool(...)` / `StructuredTool.from_function(...)` `args_schema` extraction from statically visible Pydantic `BaseModel` classes
- Pydantic field names, basic field types, required fields, and `Field(..., description=...)` descriptions in generated `tools/*.yaml` input schemas
- unresolved LangChain `args_schema` references as manual-review items
- retriever/vectorstore detection as manual review
- compatibility profiler fallback labels now preserve LangChain vs LangGraph framework names instead of reporting LangChain unknowns as `langgraph-unclassified`

Still needed:

- deeper `Tool` / `StructuredTool` schema extraction for imported models and more complex Pydantic validators/default factories

### OpenAI Agents SDK Support

Stretch support only. Not currently implemented beyond weak marker detection.

Needed:

- official fixtures
- `Agent(...)`
- instructions
- tools
- handoffs
- guardrails
- model settings
- runner/runtime boundary

### Google ADK Support

Stretch support only. Not implemented.

Needed:

- official fixtures
- agent definitions
- tools
- instruction fields
- sub-agent structure
- runtime/session/service fields as manual review

### NVIDIA AIQ/NeMo/Hermes Support

Stretch support only. Not implemented.

Needed:

- framework marker detection
- Jinja template extraction
- memory/skills extraction
- multi-agent hierarchy mapping

### Framework Docs Advisor Runtime

Partially implemented.

Implemented:

- CLI command `agentport docs check --framework <name>`
- CLI command `agentport docs check --source <repo>`
- deterministic docs-link lookup from `knowledge/framework-docs/framework-links.md`
- docs evidence in compatibility and migration reports
- docs evidence in `conversion_map.json`
- warning reasons for legacy/unimplemented/generic profiles, missing version hints, unknown patterns, deprecated patterns, and low detection confidence

Needed:

- optional live search/browser confirmation for current syntax
- cache fetched docs snapshots with date/source metadata
- fail or warn when profile assumptions are unsupported by docs evidence
- support local/offline docs bundles for reproducible CI

### Real GitAgent Validation

Current validation is internal schema fallback when external `gapman` or `gitagent` validation is unavailable. The cloned GitAgent repo does not expose a working `validate` CLI, but `datawise-agent` does through its npm dependency on `@open-gitagent/gitagent`.

Implemented:

- `--validator-command` and `AGENTPORT_VALIDATOR_COMMAND` overrides for real local validator commands. `{path}` is replaced with the generated repo path; without `{path}`, the path is appended. The CLI flag takes precedence over the environment variable.
- confirmed generated CrewAI hardening output passes the real `@open-gitagent/gitagent` validator via `/Users/hafeez/Lyzr/datawise-agent/node_modules/.bin/gitagent validate --dir {path}`
- confirmed cloned open-source CrewAI example `/Users/hafeez/Lyzr/crewAI-examples/crews/screenplay_writer` ports to `/private/tmp/agentport-screenplay-writer-gitagent` and passes the real validator with `--validator-command`
- confirmed cloned open-source LangGraph template `/Users/hafeez/Lyzr/react-agent` ports to `/private/tmp/agentport-react-agent-gitagent` and passes the real validator with `--validator-command`
- confirmed batch ports for 12 additional cloned CrewAI examples under `/Users/hafeez/Lyzr/crewAI-examples/crews` all pass the real validator with `--validator-command`: `job-posting`, `recruitment`, `surprise_trip`, `game-builder-crew`, `marketing_strategy`, `markdown_validator`, `stock_analysis`, `landing_page_generator`, `meta_quest_knowledge`, `trip_planner`, `match_profile_to_positions`, and `instagram_post`
- generated `agent.yaml` now uses official-schema-safe agent names and avoids unsupported `knowledge`/`memory` manifest properties
- generated tool YAML now avoids unsupported extra fields and uses official allowed cost values
- generated `SKILL.md` includes required YAML frontmatter
- required file checks
- `agent.yaml` field/type checks
- tool, skill, knowledge, and memory reference checks
- tool schema checks
- `conversion_map.json` field/type/boundary checks
- machine-readable error prefixes
- confirmed local validator path in `datawise-agent` via `npm run validate`

Needed:

- define required schema precisely
- broaden workflow validation once the official workflow schema exists
- broaden SOD policy validation once the official SOD schema exists
- support exact official schema once available
- teach AgentPort to auto-discover local validator package paths where appropriate

### PR / GitOps

Current `--pr-ready` writes `PULL_REQUEST.md`.

Needed:

- optional branch creation
- optional commit creation
- real GitHub PR support when `GITHUB_TOKEN` is explicitly provided
- branch naming tests
- no network by default

### CLI UX

Implemented:

- `agentport doctor`
- `agentport compatibility --source <repo>`
- `agentport explain --source <repo>`
- `agentport fixtures list`
- `agentport fixtures list --json`
- `--strict` for `analyze`, `compatibility`, `explain`, and `port`
- `--allow-partial` for `port`; permissive identity-layer ports remain the default
- clear CLI exit code `0` for success or allowed partial/manual-review output
- clear CLI exit code `1` for unexpected CLI/runtime errors
- clear CLI exit code `2` for validation failure
- clear CLI exit code `3` for strict-mode preflight failure
- package-local `.gitignore` for generated output, bytecode, caches, build artifacts, and `node_modules`
- Node wrapper honors `PYTHON` when set and otherwise keeps the default `python` behavior
- generated file reporting now dedupes repeated tool slugs instead of listing overwritten tool YAML paths twice
- end-to-end CLI smoke coverage for `analyze --json` and `port --validate --json`
- CLI validator command override coverage, including flag precedence over `AGENTPORT_VALIDATOR_COMMAND`

Needed:

- optional future `--no-allow-partial` gate if unresolved manual-review items should fail a port

### Reports

Implemented:

- stronger `framework_compatibility_report.md`
- `registry_readiness_report.md` safe-to-publish gate
- validation-derived hard blockers in readiness report
- compatibility profile name in generated reports
- deprecated/legacy pattern sections from compatibility profiling

Still needed:

- include recognized fields vs missed/unknown fields
- source locations with line numbers consistently across all artifacts
- confidence per extracted artifact
- richer old-syntax/deprecated-syntax warnings tied to source locations

### Learning System

Current learning memory is append-only.

Needed:

- structured pattern store
- failure fingerprinting
- no duplicate memory spam
- learning update tests
- separate generated-port output from AgentPort self-learning commits

### LLM Intelligence Layer

LLM intelligence should be added after the deterministic extraction and validation layers are stronger.

Recommended prerequisites:

1. Better Python AST extraction.
2. Better YAML support.
3. Structured LangGraph topology output. Done.
4. First-class LangChain mapper. Done.
5. Internal schema validation. Done; real external GitAgent/Open GAP validation still needed.
6. Golden output tests. Initial structured/normalized coverage done; broaden as parser surface grows.

Recommended timing:

- Add LLM intelligence after the deterministic system reliably produces structured `conversion_map.json`, `framework_compatibility_report.md`, docs evidence, and validation errors.
- Practical target: after the core parser/validator hardening phase, not before.

Use LLMs as a judgment and writing layer over evidence.

Good LLM responsibilities:

- explain ambiguous mappings
- draft better `SOUL.md`, `RULES.md`, and `DUTIES.md`
- summarize migration reports
- classify unclear source fragments when deterministic confidence is low
- propose manual-review recommendations
- compare source identity evidence against generated GitAgent identity
- suggest parser improvements when validation fails
- use docs-advisor links/search results to recommend syntax updates

Do not rely on LLMs alone for:

- framework detection
- source file discovery
- schema validation
- secrets detection
- tool permission classification
- runtime equivalence claims
- generated repo pass/fail status

Preferred architecture:

```txt
deterministic scan
  -> structured extraction
  -> compatibility/profile/docs evidence
  -> generated GitAgent files
  -> validator results
  -> LLM reasoning layer
  -> improved narrative, mapping explanation, remediation suggestions
```

The LLM should be an expert reviewer and writer over structured evidence, not the source of truth for parsing or validation.

## What Is Vague Or Generic Right Now

### "GitAgent/Open GAP Schema"

The target schema is still inferred from the current GitAgent repo shape and the PRD. There is now a stricter internal schema fallback validator, but no official GitAgent/Open GAP schema validator is available locally.

Needs specification:

- exact `agent.yaml` schema
- valid model field shape
- valid tools field shape
- valid sub-agent field shape
- valid workflow YAML schema
- valid memory/knowledge conventions
- required vs optional files

### "Tool Schema Extraction"

Current tool extraction is intentionally conservative. It captures static references and flags implementation code.

Needs specification:

- what GitAgent expects for tool `input_schema`
- whether JSON Schema or YAML schema is canonical
- how MCP-compatible metadata should be represented
- how risky side effects should be encoded
- whether tool implementation scripts should ever be copied

### "Multi-Agent Mapping"

CrewAI and LangGraph hierarchies are partially captured as evidence, not fully translated into runnable GitAgent sub-agents.

Needs specification:

- when a source agent becomes a GitAgent sub-agent
- how tasks become duties vs workflows
- how CrewAI manager/hierarchical mode maps to SOD
- how LangGraph nodes map to duties/workflows

### "Runtime Equivalence"

AgentPort currently does not claim runtime equivalence.

Needs specification:

- whether runtime conversion is ever in scope
- what proof would be required to claim runtime equivalence
- how to handle source repo tests without executing untrusted code by default

### "Registry Readiness"

Readiness now has explicit hard blockers and a safe-to-publish gate, but the score is still heuristic.

Needs specification:

- exact scoring rubric
- warning thresholds
- publish/registry acceptance criteria

## Key Files For Next Agent

Start here:

- `README.md`
- `progress.md`
- `agentport/cli/main.py`
- `agentport/orchestrator.py`
- `agentport/models.py`
- `agentport/core/scanner/framework_detector.py`
- `agents/agentport/agents/framework-docs-advisor/`
- `agents/agentport/knowledge/framework-docs/framework-links.md`
- `agents/agentport/skills/framework-docs-check/SKILL.md`
- `agentport/core/scanner/repository_extractor.py`
- `agentport/core/scanner/python_ast_extractor.py`
- `agentport/core/scanner/prompt_extractor.py`
- `agentport/core/generation/gitagent_writer.py`
- `agentport/core/generation/report_writer.py`
- `agentport/core/validation/gapman_runner.py`
- `agentport/core/validation/readiness_score.py`
- `tests/test_cli_commands.py`
- `tests/test_crewai_mapping.py`
- `tests/test_golden_outputs.py`
- `tests/test_langchain_mapping.py`
- `tests/test_readiness_score.py`
- `tests/test_schema_compatibility.py`
- `tests/fixtures/`

## Recommended Next Build Order

1. Clean up repository state for commit/review:
   - keep generated outputs and `__pycache__` unstaged/ignored
   - review staged AgentPort files
   - decide whether AgentPort remains inside `gitagent/agentport` for now or moves to a standalone repo
2. Add a repeatable open-source batch smoke command or test harness:
   - run selected cloned repos under `/Users/hafeez/Lyzr/crewAI-examples/crews`
   - run `/Users/hafeez/Lyzr/react-agent`
   - write a compact pass/fail report with source, output path, detected framework/profile, validation mode, and first failure
3. Improve official-validator alignment:
   - parse detailed validator output instead of only summary lines
   - add a fixture/golden assertion that generated output remains compatible with the currently available `@open-gitagent/gitagent` schema
   - consider auto-discovering `/Users/hafeez/Lyzr/datawise-agent/node_modules/.bin/gitagent` or other local validator binaries when safe
4. Broaden real-source coverage:
   - add more LangGraph/LangChain open-source repos beyond `react-agent`
   - add mixed Claude/Cursor repos with multiple instruction files
   - keep runtime-specific behavior in manual review, not converted runtime claims
5. Continue deterministic parser hardening:
   - richer semantic version parsing and version range interpretation
   - richer CrewAI knowledge source/context object shapes
   - deeper LangChain `Tool` / `StructuredTool` schema extraction for imported models
6. Add LLM intelligence as an evidence-grounded reviewer/writer layer after deterministic parser and validator output remain stable across broader real-source batches.

## Known Good Verification Commands

```bash
cd /Users/hafeez/Lyzr/gitagent/agentport
python -m unittest discover -s tests
python -m agentport.cli.main doctor
python -m agentport.cli.main fixtures list
python -m agentport.cli.main fixtures list --json
python -m agentport.cli.main analyze --source examples/crewai-demo-agent --json
python -m agentport.cli.main compatibility --source tests/fixtures/langgraph_schema_current --strict
python -m agentport.cli.main compatibility --source tests/fixtures/crewai_yaml_hardening
python -m agentport.cli.main explain --source tests/fixtures/crewai_yaml_hardening
python -m agentport.cli.main port --source tests/fixtures/crewai_schema_current --output /private/tmp/agentport-crewai-check --validate --pr-ready
python -m agentport.cli.main port --source tests/fixtures/crewai_yaml_hardening --output /private/tmp/agentport-crewai-hardening-check --validate --pr-ready --no-learn
python -m agentport.cli.main port --source tests/fixtures/langgraph_schema_current --output /private/tmp/agentport-langgraph-check --validate
python -m agentport.cli.main port --source tests/fixtures/langchain_args_schema_current --output /private/tmp/agentport-args-schema-check --validate --no-learn
python -m agentport.cli.main port --source tests/fixtures/langchain_react_current --output /private/tmp/agentport-langchain-check --validate
python -m agentport.cli.main port --source tests/fixtures/claude_cursor_schema_current --output /private/tmp/agentport-claude-check --validate
```

```bash
cd /Users/hafeez/Lyzr/datawise-agent
npm run validate
```
