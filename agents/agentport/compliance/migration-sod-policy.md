# Migration Separation Of Duties Policy

- Detectors can report evidence but cannot write generated repos.
- Extractors can identify portable artifacts but cannot approve final output.
- Schema writers can generate files but cannot validate or publish them.
- Validation auditors can approve or reject generated files but cannot silently rewrite them.
- PR writers can prepare publication artifacts but cannot bypass failed validation.
- Learning agents can update memory only after concrete evidence of a miss.
