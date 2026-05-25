---
name: _template
version: 0
inputs:
  example_input: "string — describe what this is"
outputs:
  example_output: "string — describe what this is"
when_to_use: |
  Describe in 1-3 sentences when the LLM should call this skill.
  Be concrete — vague descriptions cause the LLM to over-call or skip the tool.

  Good: "Call when the user asks for the run command of a known product."
  Bad: "Call for product questions."
examples:
  - input: { example_input: "foo" }
    output: { example_output: "bar" }
---

# Template Skill

Replace this body with a longer explanation of the skill's behavior, edge cases,
and any gotchas. This body is NOT sent to the LLM — only the `when_to_use`
frontmatter is. Keep this body for humans/AI agents reading the code.
