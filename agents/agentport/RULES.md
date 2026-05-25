# AgentPort Rules

- Do not execute untrusted source repository code by default.
- Use deterministic extraction before LLM or agent reasoning.
- Port the identity layer, not runtime equivalence.
- Flag framework-specific orchestration and side-effectful code for manual review.
- Do not copy secrets, tokens, private keys, or deployment credentials.
- The schema-writer must not approve its own output.
- The validation-auditor must not silently rewrite generated files.
- The PR writer must not bypass failed validation.
- Learning updates must be based on concrete validation failures, review notes, or migration misses.
