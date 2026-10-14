# Artifact purpose

Before writing content, read the entry named by the skill with
`dekspec resource purpose <type>`. This installed record is the canonical
purpose and routing vocabulary; templates and skill examples apply its stable
item IDs. Consumer files and `--at` cannot override it.

Use `holds` to locate content and `does_not_hold` to select its destination.
For an Architecture Element destination, retain the item's subtype. Reference
the destination's canonical content instead of copying it. Kept classifiers
and examples illustrate these items; they do not define a second policy.

Template routing lines carry `<!-- purpose: <item-id> -->` on the same line.
Keep those comments and the initial purpose pointer when copying a template.
An item ID remains stable after release even when its wording is clarified.
