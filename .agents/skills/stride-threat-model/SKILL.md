---
name: stride-threat-model
description: Performs a STRIDE threat model assessment for new features or architectural changes. Use this skill when evaluating security risks or proposing system expansions.
---

# STRIDE Threat Modeling Skill

## Goal
Systematically identify and mitigate security threats in the Study Coach Agent application using the STRIDE methodology before new features are implemented.

## Instructions
When asked to perform a threat model or security review, evaluate the proposed changes across the 6 STRIDE categories:

1. **Spoofing** (Identity)
   - Can an attacker pretend to be another student?
   - Are MCP Server requests authenticated or isolated by session?

2. **Tampering** (Integrity)
   - Can uploaded study notes be maliciously altered?
   - Is `progress.json` protected from unauthorized writes?

3. **Repudiation** (Non-repudiation)
   - Are interactions and quiz evaluations properly logged for audits?

4. **Information Disclosure** (Confidentiality)
   - Is PII (names, emails) leaking to the LLM?
   - Can prompt injection trick the agent into revealing other users' data?

5. **Denial of Service** (Availability)
   - Can a massive uploaded `.docx` file crash the `ingest_notes` memory or ChromaDB?

6. **Elevation of Privilege** (Authorization)
   - Can the agent execute arbitrary code? (Zero Ambient Authority should prevent this).
   - Are Path Traversal attacks possible in the MCP server?

## Output Format
Produce a structured Threat Assessment report detailing:
- The Feature being modeled
- Potential threats mapped to the STRIDE categories
- Recommended mitigations for each threat
