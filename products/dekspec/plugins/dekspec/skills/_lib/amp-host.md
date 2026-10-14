# Amp skill metadata

ADR-074 defines the Amp header projection. This note and the projection are
ready for the Amp installer still to come; they do not establish Amp support.
Skill bodies remain byte-identical to their canonical source.

## Header fields

Amp receives `name`, `description`, `argument-hint`, `related_skills` and
`interaction` when present. It does not receive `mode`, `model`,
`reasoning_effort`, `allowed-tools` or `disable-model-invocation`.
Skill header fields are hints to the host, not security enforcement.

## Explicit-request-only skills

- `dekspec:ingest-docs`

On Amp this rule lives in the description's final sentence:
"Run only when the engineer explicitly asks for this skill by name."
The projected description, including that sentence, must fit within 1,024
characters. Projection refuses a longer description; it never truncates it.

## Discovery and invocation

Amp shows a plugin skill as `dekspec:<name>` while its header `name` stays
`<name>`. Ask for that qualified name explicitly. Claude's `/dekspec:<name>`
slash syntax and Codex's `$<name>` do not carry over.

`amp skills list` shows discovered skills. The `reload_skills` tool reloads
them in the current session; listing skills in another shell does not reload
that session. See [Amp's skills documentation](https://ampcode.com/docs/customize/skills).

## Tool vocabulary — unverified

This mapping is unverified until INT-198 brief 6 qualifies it live. These are
candidate equivalents for the tool names used in shared skill instructions,
not a claim that a DekSpec workflow has been qualified on Amp.

| Shared instruction | Amp tool |
| --- | --- |
| Read | `Read` |
| Write | `create_file` |
| Edit | `edit_file` |
| Glob | `glob` |
| Grep | `Grep` |
| Bash | `Bash` |
| WebFetch | `read_web_page` |
| WebSearch | `web_search` |

Names follow [Amp's CLI guide](https://github.com/ampcode/amp-examples-and-guides/blob/main/guides/cli/README.md).
[Amp's tools documentation](https://ampcode.com/docs/tools) describes inspecting
the available tools with `amp tools list`.
