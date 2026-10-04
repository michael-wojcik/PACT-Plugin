# PACT Skills

## Naming Convention
- Use kebab-case: `pact-{domain}-{function}`
- Prefix with `pact-` for framework skills
- Examples: `pact-agent-teams`, `pact-memory`, `pact-coding-standards`

## Loading

Agents list **only** `pact-agent-teams` in frontmatter `skills:`. That protocol is auto-loaded when the agent is invoked.

Domain and workflow skills are **not** auto-activated. Agents invoke them with the Skill tool at the start of work. Do not rely on auto-activation for those skills, and do not add every domain skill to agent frontmatter.
