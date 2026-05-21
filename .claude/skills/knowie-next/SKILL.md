---
name: knowie-next
description: Plan the next step based on project knowledge
user-invocable: true
argument-hint: "[direction or feature area to explore]"
---

# Knowie Next

Help the user decide and plan what to work on next, grounded in the project's principles, vision, and experience.

## User Input

```text
$ARGUMENTS
```

## Governance Principles

- **Principles are the highest authority.** Every recommendation must be traceable to a principle. If it isn't, flag it as a pragmatic choice.
- **Vision is the roadmap.** Follow the established order unless experience provides compelling reason to deviate.
- **Experience is the guardrail.** Always check for relevant lessons before recommending an approach.
- **Never auto-invoke other skills.** Only suggest them.

## Workflow

### 1. Read knowledge files

Read all three core files:
- `knowledge/principles.md`
- `knowledge/vision.md`
- `knowledge/experience.md`

Also check:
- `knowledge/design/` for relevant design documents
- Project structure and recent git log for actual state

### 2. Determine direction

**If `$ARGUMENTS` provides a direction** (e.g., "error handling", "mobile support"):
- Locate it in the vision roadmap
- Check prerequisites — are prior milestones actually complete? (check code, not just what vision says)
- Find relevant experience entries (lessons, pitfalls, patterns)
- Find relevant design documents
- Check if principles constrain the approach

**If `$ARGUMENTS` is empty**:
- Look at the vision roadmap for the next incomplete milestone
- Cross-reference with actual project state (what's really done?)
- Consider experience lessons that might affect priority
- Suggest the most logical next step with justification

### 3. Converge

Through conversation with the user, converge on all of these items:

- **Feature name**: short, descriptive
- **One-line description**: what it delivers to the user/system
- **Roadmap position**: which phase/milestone it belongs to
- **Prerequisites**: what must be done first (check if actually done)
- **Scope**:
  - What's included (explicit list)
  - What's explicitly excluded (prevent scope creep)
- **Grounded in principles**: which principle(s) this serves, and how. Show the derivation chain.
- **Informed by experience**: relevant lesson(s) and how to apply them. Quote the specific lesson.
- **Risks**: based on experience, what could go wrong? What mitigation is available?
- **Success criteria**: how do we know this is done? Make it concrete and verifiable.

### 4. Output

Present a concise feature brief:

```markdown
## Next: [Feature Name]

**Description**: [One-line description]

**Roadmap**: [Phase/milestone reference]

**Prerequisites**:
- [x] [Completed prerequisite]
- [ ] [Missing prerequisite — must be addressed first]

**Scope**:
- ✅ [Included]
- ✅ [Included]
- ❌ [Explicitly excluded]

**Grounded in principles**:
- Principle: "[quoted principle]"
- How this feature serves it: [explanation]

**Informed by experience**:
- Lesson: "[quoted lesson from experience.md]"
- How to apply: [specific guidance for this feature]

**Risks**:
- [Known risk from experience] → Mitigation: [approach]

**Success criteria**:
- [ ] [Concrete, verifiable criterion]
- [ ] [Concrete, verifiable criterion]
```

### 5. Suggest next action

After presenting the feature brief, scan the project for spec/planning tools:

- Check `.claude/skills/` for spec-related skills (e.g., `speckit-specify`, `speckit-plan`)
- Check `.specify/` for Speckit
- Check `openspec/` for OpenSpec
- Check `.kiro/specs/` for Kiro Specs

**If a spec tool is found**: suggest the specific command.
  Example: "You can now use `/speckit-specify` to create a detailed specification for this feature."

**If no spec tool is found**: give a generic prompt.
  "You can now use your preferred specification tool to flesh out the details, or start implementing directly."

## Guidelines

- **Language**: Read `knowledge/.knowie.json` → `language` field (e.g., `"zh-TW"`). Use that language for ALL output — section headers, descriptions, suggestions, everything. If `knowledge/.knowie.json` is missing or has no language field, detect from conversation context or default to English.
- Keep the feature brief concise — it's a starting point, not a full spec
- **Every recommendation must reference knowledge files.** Don't invent principles or cite non-existent experience. If there's no relevant principle, say so explicitly.
- Verify project state before claiming prerequisites are met — check actual code, not just what vision says
- If the user's direction conflicts with principles or experience, flag it clearly with the specific conflict, but let them decide
- If the roadmap is empty or unclear, help the user think through priorities rather than guessing
- Never auto-invoke other skills — only suggest them
