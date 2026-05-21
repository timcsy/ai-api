---
name: knowie-update
description: Check knowledge file structure completeness and suggest improvements
user-invocable: true
argument-hint: "[specific file or area to check]"
---

# Knowie Update

Review existing knowledge files against the latest templates, governance principles, and actual project state. Suggest structural improvements.

## User Input

```text
$ARGUMENTS
```

## Governance Principles

- **Principles are the highest authority.** If the structure check reveals that principles are weak or missing derivation chains, this is the highest priority fix.
- **Vision evolves with understanding.** Suggest updates when the project has moved forward but vision hasn't caught up.
- **Experience is distilled, not accumulated.** If experience.md is growing too long, suggest distilling. If history/ has entries that should be promoted, flag them.
- **Knowledge files are indexes, not encyclopedias.** If any core file exceeds ~200 lines, suggest moving detail to subdirectories.
- **Never modify files without explicit user confirmation.**

## Workflow

### 1. Read current state

- Read `knowledge/principles.md`, `knowledge/vision.md`, `knowledge/experience.md`
- Read `knowledge/.templates/` for the latest recommended structure
- Scan `knowledge/research/`, `knowledge/design/`, `knowledge/history/` for existing files
- Read project structure and recent git log for context

### 2. Structural check

Compare each core file against its template. Look for:

- **Missing sections**: template suggests a section that the file doesn't have
- **Empty sections**: section header exists but no content below it
- **Orphaned content**: content that doesn't fit any recommended section
- **Overgrown files**: core files exceeding ~200 lines (should move detail to subdirectories)
- **Weak derivations**: principles without clear derivation chains
- **Vague milestones**: vision roadmap items without success criteria
- **Undistilled lessons**: experience entries that are raw events rather than patterns

### 3. Cross-file check

- Do principles reference concepts that aren't in the vision?
- Does experience mention lessons that should update the vision?
- Are there subdirectory files mature enough to distill into core files?
- Is the three-file system coherent as a whole?

### 4. Project alignment check

- Has the project evolved since the knowledge files were last updated?
- Are there new features, dependencies, or architectural changes not reflected?
- Does the git log show recent work that should generate experience entries?

### 5. Report

Present findings organized by priority:

```
## Structure Check

### principles.md
🟢 Root Axiom — present and clearly stated.
🟡 Derived Principles — only 1 principle listed, template suggests at least 2-3.
🔴 Derivation chains — missing. Principles don't trace back to root axiom.
   → Add "Derived from: [root axiom]" to each principle.

### vision.md
🟢 Problem Statement — present and specific.
🟢 Current State — honest and up-to-date.
🟡 Roadmap — has milestones but no success criteria.
   → Add concrete success criteria to each milestone.

### experience.md
🟢 Structure follows template format.
🟡 Lesson "caching strategy" (line 23) reads like a raw event, not a distilled pattern.
   → Rewrite using: Theory said X → Actually Y → Solved by Z → Lesson: W

### Subdirectories
🟡 design/auth-system.md looks mature — consider distilling key decisions into vision.md.
🟡 history/ has 3 new entries since last experience.md update — review for distillation.

### Project Alignment
🟡 git log shows 12 commits since last vision update. Phase 2 may be complete.
   → Verify and update roadmap status.

## Suggested Actions (by priority)
1. [High] Add derivation chains to principles.md
2. [Medium] Add success criteria to roadmap milestones
3. [Medium] Distill recent history/ entries into experience.md
4. [Low] Review design/auth-system.md for vision.md update
```

### 6. Reorganization offer

When structural problems are severe enough to warrant reorganization, offer proactively:

- **Overgrown core file** (>200 lines): Propose extracting detail to subdirectories.
  - principles.md → move research/exploration to research/
  - vision.md → move detailed designs to design/
  - experience.md → move raw events to history/, keep only distilled lessons
- **Wrong format**: Propose reformatting entries to match template structure.
  - experience lessons not in four-part format (Theory said → Actually → Resolved by → Lesson)
  - principles without derivation chains
  - roadmap milestones without success criteria
- **Stale content**: Propose removing or archiving outdated entries.
- **Mature subdirectory content**: Propose distilling into core files.

Format:

```markdown
## Reorganization Suggested

experience.md has grown to 280 lines (recommended: ~200).
- 5 lessons appear to be raw events → move to history/, distill patterns
- 3 lessons reference rewritten code → update or archive

Would you like me to help reorganize?
```

If the user agrees, proceed step by step (one file at a time, show diff, wait for confirmation).

### 7. Assist with changes

- If the user wants to act on any suggestion, help them make the change
- Before writing, verify the change is consistent with other knowledge files
- Show diffs before writing
- After writing, offer a focused re-check on the changed area

## Guidelines

- **Language**: Read `knowledge/.knowie.json` → `language` field (e.g., `"zh-TW"`). Use that language for ALL output — section headers, descriptions, suggestions, everything. If `knowledge/.knowie.json` is missing or has no language field, detect from conversation context or default to English.
- Be constructive, not critical — the goal is to help, not to grade
- Prioritize by impact: what would help the AI (and the team) most?
- Don't suggest adding content the user may not have yet — only structural improvements
- For project alignment, actually read project files — don't guess
- If you notice the knowledge files are getting stale, say so directly
