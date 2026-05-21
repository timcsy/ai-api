---
name: knowie-judge
description: Cross-check knowledge files for consistency, coherence, and project alignment
user-invocable: true
argument-hint: "[scope: file name, file pair, or event description]"
---

# Knowie Judge

Verify that the three knowledge files (principles, vision, experience) are internally sound, consistent with each other, and aligned with the actual project state.

## User Input

```text
$ARGUMENTS
```

## Governance Principles

These rules govern how you interact with knowledge files. Follow them in every check:

- **Principles are the highest authority.** If vision or experience conflicts with principles, the pressure is on vision/experience to change — unless the conflict reveals that a principle needs revision.
- **Vision evolves with understanding.** It should be updated after milestones, not frozen.
- **Experience is distilled, not accumulated.** Only patterns that influence future decisions belong here. Raw events go in history/.
- **Knowledge files are indexes, not encyclopedias.** Each should be short enough to read in one pass (~100-200 lines). Long content belongs in subdirectories.
- **Never modify files without explicit user confirmation.** Present findings and suggestions; let the user decide.

## Workflow

### 1. Read knowledge files

Read all three core files:
- `knowledge/principles.md`
- `knowledge/vision.md`
- `knowledge/experience.md`

Also scan `knowledge/research/`, `knowledge/design/`, `knowledge/history/` for additional context.

### 2. Read project context

To check alignment with the actual project, also examine:
- Project directory structure (what files and directories exist)
- `package.json`, `Cargo.toml`, or equivalent (tech stack, dependencies)
- Recent git log (what has actually been built recently)
- README or other top-level docs

### 3. Determine scope

Parse `$ARGUMENTS` to decide what to check:

- **No arguments**: full check (all 17 sections below)
- **Single file** (e.g., "experience"): that file's self-consistency, internal coherence, project alignment, and its cross-references with the other two files
- **File pair** (e.g., "principles vision"): the 2 directional cross-references for that pair
- **Event description** (e.g., "just finished the auth system"): impact analysis on all three files

### 4. Execute checks

#### A. Self-consistency (3 checks)

For each file, check its structural and logical integrity:

**Principles:**
- Does the root axiom exist and is it clearly stated?
- Does every derived principle trace back to the root axiom or another principle? Are there broken derivation chains?
- Are there principles that say the same thing in different words (redundancy)?
- Is the document organized from general to specific?

**Vision:**
- Does the problem statement clearly define who has the problem and why?
- Does the roadmap flow logically? Are prerequisites respected?
- Are milestones mutually exclusive or do they overlap?
- Are success criteria concrete and verifiable?

**Experience:**
- Does each lesson follow the pattern/event/takeaway format?
- Are there lessons that contradict each other without acknowledging the contradiction?
- Are lessons specific enough to be actionable?
- Are source references present and traceable?

#### B. Internal Coherence (3 checks)

For each file, check for contradictions in content:

- Are there statements that directly contradict each other?
- Are there implicit assumptions that conflict?
- Are there outdated entries that no longer reflect the project's reality?

#### C. Cross-references (6 directional checks)

Each direction asks a specific question:

| Direction | Core Question | Detailed Probes |
|-----------|--------------|-----------------|
| Principles → Vision | Can the vision be derived from the principles? | Does each roadmap item serve at least one principle? Are there vision items with no principled justification? |
| Vision → Principles | Does the vision require principles that aren't stated? | Are there implicit assumptions in the vision that should be made explicit as principles? |
| Principles → Experience | Do the principles predict the patterns observed? | Has experience validated the principles? Which principles lack empirical support? |
| Experience → Principles | Does any experience challenge or extend the principles? | Are there lessons that suggest a principle is wrong, incomplete, or needs nuance? |
| Vision → Experience | Does experience support the planned direction? | Are there known risks from experience that the vision doesn't address? Has the vision learned from past failures? |
| Experience → Vision | Are there lessons suggesting opportunities not yet in the vision? | Has experience revealed capabilities or patterns that could open new directions? |

#### D. Project Alignment (3 checks)

Check each file against the actual project state:

**Principles vs Project:**
- Do claimed technology choices match actual dependencies?
- Do architectural principles match the actual code structure?
- Are there principles about practices (e.g., "TDD") that aren't actually followed?

**Vision vs Project:**
- Does the roadmap status match what's actually implemented?
- Are "completed" milestones truly complete in the code?
- Are there significant implemented features not reflected in the vision?
- Does the tech stack in the vision match the actual project?

**Experience vs Project:**
- Are referenced files/features still present in the project?
- Have lessons been acted upon? (e.g., "always validate first" — is validation actually in place?)
- Are there stale lessons about problems that have been solved or code that was rewritten?

#### E. Overall (1 check)

Synthesize all findings:
- Where is the most pressure? Which file needs the most attention?
- Is the knowledge system generally healthy or in need of significant work?
- What is the single most impactful action the user could take?

#### F. Beyond Scope (1 check)

Look for content that doesn't belong:
- Lessons about a different project or domain
- Principles too generic to be useful (e.g., "write clean code")
- Vision items that belong in a separate project
- Content that should be in subdirectories instead of core files

### 5. Format output

```markdown
## Knowledge Health Check

### Self-consistency
🟢 Principles — root axiom present, derivation chains intact.
🟡 Vision — Phase 3 and Phase 5 overlap in scope.
   Phase 3 (line 45): "Implement caching layer"
   Phase 5 (line 67): "Add performance optimization including caching"
   → Clarify the boundary or merge these phases.
🟢 Experience — all lessons follow consistent format.

### Internal Coherence
🟢 Principles — no contradictions.
🟡 Vision — current state section says "auth is complete" (line 28)
   but roadmap still lists auth as pending (line 52).
   → Update one or the other.
🟢 Experience — consistent.

### Cross-references
🟢 Principles → Vision — vision is derivable from principles.
🟡 Vision → Principles — vision mentions "progressive disclosure"
   but principles don't include a related principle.
   → Add a principle, or document this as a tactical choice in vision.
🟢 Principles → Experience — principles predict observed patterns.
🟢 Experience → Principles — no challenges to existing principles.
🔴 Vision → Experience — vision plans to use SSR, but experience
   recorded SSR hydration issues.
   Vision line 34: "Phase 2: migrate to SSR"
   Experience line 12: "SSR hydration caused 3-day debug cycle"
   → Address this known risk in vision, or explain why context differs.
🟢 Experience → Vision — no missed opportunities.

### Project Alignment
🟢 Principles — tech choices match project reality.
🟡 Vision — roadmap says Phase 1 complete, but tests/ directory
   is empty. Success criteria mentions "90% test coverage."
   → Either update success criteria or add tests.
🟢 Experience — all referenced code still exists.

### Overall
🟡 Generally healthy. Main pressure on vision.md — one conflict
   with experience, one internal inconsistency, and one alignment
   gap with project state.

### Beyond Scope
🟢 All content is relevant to this project.

## Suggested Actions
1. [High] Resolve SSR conflict between vision and experience
2. [Medium] Fix auth status inconsistency in vision
3. [Medium] Clarify Phase 3/5 overlap in vision
4. [Low] Consider adding progressive disclosure principle

---
Would you like me to help fix any of these issues? I can propose specific edits for you to review.
```

### 6. Event-based analysis (when $ARGUMENTS describes an event)

```markdown
## Post-feature Check: [Event]

### Impact on Experience
🟡 Worth distilling — [specific observation].
   → Suggest adding a lesson to experience.md

### Impact on Vision
🟢 Milestone completed as planned.
   → Mark as complete in roadmap.

### Impact on Principles
🟢 No challenge to existing principles.

### Project Alignment
🟡 Feature is implemented but vision hasn't been updated.

### Suggested Actions
1. Add lesson to experience.md: [specific lesson]
2. Update vision.md: mark [milestone] as complete

---
Would you like me to help fix any of these issues? I can propose specific edits for you to review.
```

### 7. Reorganization offer

If checks reveal that files are too disorganized to assess clearly, offer to help reorganize. Common triggers:

- **Overgrown core file** (>200 lines): Propose moving detail to subdirectories, keeping only distilled content in core.
- **Raw events in experience.md**: Propose moving them to history/ and distilling into patterns.
- **Stale content**: Propose removing or updating entries that reference deleted code, completed milestones, or resolved problems.
- **Broken structure**: Propose reordering sections to match template structure (root → derived, general → specific).
- **Mature subdirectory content**: Propose distilling key insights from research/design/history into the appropriate core file.

Format the offer clearly:

```markdown
## Reorganization Suggested

experience.md has grown to 280 lines (recommended: ~200).
- 5 lessons appear to be raw events rather than distilled patterns
- 3 lessons reference code that has been rewritten

Would you like me to help reorganize?
- Move raw events to history/
- Distill remaining lessons into four-part format
- Remove or update stale references
```

If the user agrees:
1. Show proposed changes as diffs for each file, one at a time
2. Wait for user confirmation before each write
3. After all changes, run a focused re-check on modified files

### 8. Recursive verification

After the user makes changes based on your suggestions:

1. Re-read the modified files
2. Run a focused check on the changed areas only
3. Confirm the changes resolved the issues without introducing new ones
4. If new issues are found, report them (one recursion only — don't loop)

## Display Rules

- 🟢 **Healthy**: one line, no details needed
- 🟡 **Tension**: expand with specific quotes (file + line reference), explain the tension, suggest resolution
- 🔴 **Conflict**: expand with specific quotes, explain the conflict, suggest concrete action with priority
- Always quote the specific text from knowledge files that supports your finding
- End with a numbered list of suggested actions, ordered by priority ([High] / [Medium] / [Low])
- **Always end with a fix offer**: After the suggested actions list, add a separator (`---`) and ask the user if they'd like help fixing any of the issues. Example: "Would you like me to help fix any of these issues? I can propose specific edits for you to review."

## Guidelines

- **Language**: Read `knowledge/.knowie.json` → `language` field (e.g., `"zh-TW"`). Use that language for ALL output — section headers, descriptions, suggestions, everything. If `knowledge/.knowie.json` is missing or has no language field, detect from conversation context or default to English.
- Be specific — always quote relevant text from knowledge files
- Distinguish between true contradictions (🔴) and tensions worth watching (🟡)
- Don't flag stylistic differences as inconsistencies
- For Project Alignment checks, actually read project files — don't guess
- Focus on substance: does the knowledge system help the team make good decisions?
- Never modify files automatically — only suggest changes
- After user makes changes, offer to re-check (recursive verification, once)
