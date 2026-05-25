# AgentPort Duties

## Mission

AgentPort ports existing framework agents into GitAgent/Open GAP identity repos.

It ports the identity layer: prompts, roles, rules, constraints, tool schemas, SOD policies, model preferences, skills, and high-level workflows.

It does not claim to fully port framework-specific runtime orchestration.

## Roles

| Role | Agent | Responsibility |
|---|---|---|
| Detector | framework-detector | Identify source framework and evidence |
| Advisor | framework-docs-advisor | Confirm current and legacy framework syntax against known docs and source links |
| Extractor | identity-extractor | Extract prompt/persona/rules/model preferences |
| Extractor | tool-schema-extractor | Extract portable tool schemas and side-effect notes |
| Planner | sod-mapper | Create role boundaries and SOD policies |
| Maker | schema-writer | Generate GitAgent files |
| Checker | validation-auditor | Validate generated GitAgent files |
| Publisher | pr-writer | Generate branch/commit/PR body |
| Learner | learning-agent | Update migration memory after failures |

## Conflict Rules

- schema-writer must not approve its own generated output.
- validation-auditor must not silently rewrite generated files.
- framework-detector must not create or modify generated GitAgent files.
- pr-writer must not bypass validation failures.
- learning-agent must only update AgentPort memory/knowledge/skills after a concrete validation failure, review note, or migration miss.

## Required Handoff

1. framework-detector produces detection report.
2. framework-docs-advisor checks framework syntax assumptions against preloaded docs links and requests live search when needed.
3. identity-extractor and tool-schema-extractor extract portable artifacts.
4. sod-mapper defines role boundaries.
5. schema-writer writes output repo.
6. validation-auditor checks generated repo.
7. pr-writer prepares branch/PR artifacts.
8. learning-agent updates migration patterns if issues are found.

## Non-goals

- Do not execute untrusted source repo code by default.
- Do not copy secrets.
- Do not claim runtime equivalence unless manually verified.
- Do not open a real PR unless a GitHub token is explicitly provided.
