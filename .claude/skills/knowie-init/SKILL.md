---
name: knowie-init
description: AI-guided creation of project knowledge files (knowledge/)
user-invocable: true
argument-hint: "[topic or file to focus on]"
---

# Knowie Init

Help the user create or populate their project knowledge files through layered, progressive conversation.

## User Input

```text
$ARGUMENTS
```

## Governance Principles

- **Principles are the highest authority.** When helping write principles, push the user to find the *root* — the one belief everything else derives from. Don't settle for surface-level rules.
- **Vision evolves with understanding.** It's OK if vision is incomplete at first. Help the user capture what they know now.
- **Experience is distilled, not accumulated.** Guide the user to extract patterns, not dump event logs.
- **Knowledge files are indexes, not encyclopedias.** Keep core files short. Point to subdirectories for details.
- **Never write files without explicit user confirmation.** Always show the draft first.
- **Low-pressure entry.** Beginners worry about "am I doing it right?" Remind them they can fill just one item, skip a section, or come back later. An incomplete `knowledge/` is still more useful than an empty one. Proactively surface this reassurance when the user seems hesitant.

## Workflow

### 1. Read current state

- Read `knowledge/principles.md`, `knowledge/vision.md`, `knowledge/experience.md`
- Read `knowledge/.templates/` to understand suggested structure
- Read project structure, package.json/Cargo.toml/etc. to understand the tech context
- Identify which files are empty or still contain only template comments

### 2. Determine scope

- If `$ARGUMENTS` specifies a file (e.g., "principles"): focus on that file
- If `$ARGUMENTS` specifies a subdirectory file (e.g., "design/auth-system"): help create that file
- If `$ARGUMENTS` is empty: assess all three core files and start with whichever needs the most work

### 3. Choose guidance style (route)

Before asking the deep questions, ask the user once which style suits them:

> "Before we start, which would you prefer?
> (a) I give you common examples and patterns as prompts, and you react/extend from there — less blank-page pressure.
> (b) You describe your project in your own words first, and I only offer examples if you get stuck."

- **Example-first mode (a)** — default to this for users who seem new, hesitant, or when files are completely empty. Lead every Layer 1 question with concrete options/examples (see below).
- **Free-form mode (b)** — skip the example prompts and go straight to the open-ended Layer 1 questions. Offer examples only if the user explicitly stalls.

Remember the chosen mode for the rest of the conversation.

### 4. Progressive conversation

Use layered questioning — start broad, then drill deeper. Don't ask all questions at once.

**For principles.md — Layer by layer:**

Layer 1 — Example-first mode (start here for hesitant users):

*Step 1: pick a category.*
> "Most projects' principles fall into these categories:
> ① Technical trade-offs (language, framework, dependency choices)
> ② Design / UX orientation (for whom, what experience)
> ③ Collaboration & process (how the team works)
> ④ Quality bar (what you won't ship below)
>
> Which one do you want to start with? Or is there another angle?"

*Step 2: show what a "root axiom" looks like — a complete worked example.*
> "A more advanced move is to find a *root axiom* — one core concept, and all other principles are its projections.
>
> **Example:** 'One concept, many projections' can itself be a root axiom — from that single idea you derive:
> - **Data structures:** chosen so the core concept is naturally expressible
> - **API design:** expose projections, not internal structure
> - **When to refactor:** when the projections grow so numerous that the core concept gets obscured
>
> One axiom, many specific rules — all traceable back.
>
> Does your project have a core concept that everything else could radiate from? If nothing comes to mind, that's fine — write down a few concrete rules first, and we can look for their common root afterwards."

Layer 1 — Free-form mode (for users who want to speak first):
- "What problem does this project exist to solve?"
- "If you could only keep one rule about how this project works, what would it be?"
- "What would you *never* compromise on, even under deadline pressure?"

Layer 2 (Derive):
- "Why is that true? What deeper belief makes you hold that rule?"
- "If that's your root axiom, what follows from it? What rules does it imply?"
- "Can you think of a time this principle was tested? What happened?"

Layer 3 (Structure):
- "Let's trace the derivation chain: [root axiom] → [principle 1] → [specific rule]. Does this chain make sense?"
- "Are there principles that reinforce each other? How do they connect?"
- "Is there anything you believe that *doesn't* derive from your root axiom? That might be a second axiom, or it might derive from the first in a way we haven't found yet."

**For vision.md — Layer by layer:**

Layer 1 — Example-first mode (fill-in-the-blank structure):
> "Let's fill this in one slot at a time — you don't need to have the whole picture:
> ① **Ultimate goal** — in one sentence, what does success look like?
> ② **Current progress** — where are we now? (one paragraph is enough)
> ③ **Next 2-3 milestones** — what are the next deliverables?
> ④ **Checklist per milestone** — what specific items must be done?
>
> Let's start with ①. What's the one-sentence version of where you want this project to end up?"

Then walk through ② → ③ → ④ one at a time, letting the user answer each slot in isolation. Skipping a slot is fine — note it as "TBD" and move on.

Layer 1 — Free-form mode:
- "Who has the problem this project solves? What do they do today without your project?"
- "What's the core idea — in one or two sentences?"

Layer 2 (State):
- "What works right now? What's broken or missing?"
- "What are the key technical decisions you've made, and why?"

Layer 3 (Direction):
- "What are the next 2-3 milestones? What does each one deliver?"
- "For each milestone: what must be done before it? How will you know it's done?"
- "Is there anything in the roadmap you're uncertain about? Let's mark that explicitly."

**For experience.md — Layer by layer:**

Layer 1 — Example-first mode (trigger recall with concrete lessons):
> "Here are some lessons other developers commonly record. See if any resonate with something you've been through:
> ① **Debug with print before reasoning** — when something breaks, locate the actual failure point with print statements before trying to deduce the cause
> ② **Use compiler errors as refactoring guides** — for large refactors, let the type-checker/compiler tell you every place that needs updating
> ③ **Performance usually comes from the data model** — not from micro-optimizations; the right data structure carries enough information to make operations cheap
> ④ **Wrong → understand → fix beats think-it-through-perfectly first** — iteration uncovers truths that upfront thinking misses
> ⑤ **Don't skip TDD** — 'I'll add tests later' almost always means 'I'll debug for three times as long'
>
> Have you hit anything similar? Or do you have your own version of these?"

After the user responds, help them convert it into the four-part format (Theory → Actual → Resolved → Lesson).

Layer 1 — Free-form mode:
- "What surprised you during development?"
- "What took longer than expected? Why?"
- "What would you warn your past self about?"

Layer 2 (Pattern):
- "Is there a pattern behind those surprises? Something that might happen again?"
- "What did you expect would happen vs what actually happened?"
- "How did you solve it? Would you solve it the same way again?"

Layer 3 (Distill):
- "Let's turn that into a lesson: what's the one-sentence pattern?"
- "What theory or assumption was wrong? What's the corrected understanding?"
- "Where in the codebase can we see the evidence of this lesson?"

**For subdirectory files (research/, design/, history/):**
- Read existing core files for context
- Ask about the specific topic
- Suggest a filename following the directory's purpose
- After creating: suggest how the content might eventually distill into the parent core file

### 4. Draft content

Based on the conversation:
- Draft the content in the user's language
- Follow the structure from the templates but use real content
- For principles: show explicit derivation chains (Root Axiom → Principle → What it means in practice)
- For vision: be concrete about current state, include success criteria for milestones
- For experience: use the four-part format (Theory said X → Actually happened Y → We solved it by Z → Lesson: W)

### 5. Self-check before proposing

Before showing the draft to the user, verify:
- **Self-consistency**: Does the draft contradict itself?
- **Cross-consistency**: Does the draft conflict with the other two knowledge files?
- **Project alignment**: Does the draft match the actual project state?

If you find issues, revise the draft or flag them to the user.

### 6. Confirm and write

- Present the draft to the user
- Highlight any concerns from the self-check
- Ask for feedback and iterate if needed
- Only write to files after explicit user confirmation
- Never overwrite existing content without showing a diff of what will change

## Guidelines

- **Language**: Read `knowledge/.knowie.json` → `language` field (e.g., `"zh-TW"`). Use that language for ALL output — questions, drafts, suggestions, everything. If `knowledge/.knowie.json` is missing or has no language field, detect from conversation context or default to English.
- **Layer your questions** — don't dump all questions at once. Ask 2-3, listen, then go deeper.
- **Default to example-first mode** for hesitant users or when all three knowledge files are still template-only. Offer the routing question (Step 3) clearly, but if the user doesn't state a preference, lean toward example-first — beginners benefit more from concrete starting points than from open prompts.
- Keep language practical and clear — avoid academic jargon
- Reference existing content in other knowledge files when relevant
- Translate the example options (categories, root-axiom example, lesson list) into the user's language — don't leave them in English when the user writes in another language
- For subdirectory files, suggest how content might eventually be distilled into core files
- Push for specificity — "write clean code" is not a principle; "every function has exactly one responsibility because [root axiom]" is
- Proactively reassure hesitant users: "only filling one bullet is fine", "you can come back and add more later", "an incomplete file is still more useful than an empty one"
