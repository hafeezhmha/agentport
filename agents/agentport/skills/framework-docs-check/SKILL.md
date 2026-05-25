# Framework Docs Check

Use this skill when AgentPort needs to confirm framework syntax, resolve old-versus-current APIs, or decide whether a source pattern should be parsed automatically or sent to manual review.

Workflow:

1. Identify the detected framework and compatibility profile.
2. Check `knowledge/framework-docs/framework-links.md`.
3. Prefer official docs, official GitHub repos, and versioned migration guides.
4. If the local link inventory is stale or insufficient, request live search/browsing before making a compatibility claim.
5. Return source-backed guidance for extractor/schema-writer updates.

Never claim a framework syntax is current without evidence from known docs or a fresh search.
