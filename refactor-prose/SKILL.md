---
name: refactor-prose
description: Iteratively refactor existing prose — privacy policies, marketing copy, web content, docs — based on user requirements or feedback. Reads surrounding pages for voice, asks clarifying questions before drafting, edits in place, and expects multi-turn revision. Use when the user says "update the privacy policy", "reword this page", "extend this copy with keywords X", "rewrite this section", or invokes /refactor-prose.
---

# Refactor Prose

You're editing prose someone already wrote, not generating a blank page. The original exists for a reason — preserve the parts that are working.

## Step 1 — Read before drafting

- Read the target file in full.
- Read 1–2 sibling pages (other policy pages, other marketing sections) to anchor on the **existing voice, register, and structural conventions**. Don't invent a new tone.
- Note constraints visible in the page: required legal phrases, brand names, links, structural markers (h2/h3 hierarchy), CTAs.

## Step 2 — Ask before writing

Most prose refactors fail because the AI guesses the user's intent. Before drafting, ask the small number of questions whose answers actually change the output. Examples that come up repeatedly:

- Who is the audience now vs. before? (Sometimes the whole point of the rewrite.)
- Is this a *replacement* of existing sections, an *extension*, or a *reframing*?
- Are there sections to delete entirely, or keep verbatim?
- For legal/policy text: which claims are facts to preserve, which are flexible?
- For SEO/keyword work: must-include terms, target keyword density, banned terms.

Use `AskUserQuestion` with 1–3 questions max. Don't ask things you can infer from the file. If the user gave a complete brief upfront, skip this step — don't ask just to look thorough.

## Step 3 — Draft

- **Edit in place** with `Edit`. Prose lives in a real file with a real surrounding context; don't rewrite the whole document if only two sections change.
- Match the surrounding voice. If the existing copy uses contractions, you use contractions. If it's formal, stay formal.
- Don't invent facts. If the rewrite needs a claim you can't verify from the file or the user's brief (a regulation citation, a stat, a product capability) **flag it inline** with a clear marker like `[VERIFY: ...]` rather than fabricating.
- For legal/policy text: don't add compliance language the user didn't ask for. "GDPR-compliant" is a claim, not a sentence opener.
- Preserve structural markers (headings, anchors, frontmatter) unless explicitly changing them.

## Step 4 — Iterate

Expect 2–4 revision rounds. The first draft is a proposal, not a delivery. When the user says "remove all newsletter references" or "extend with keywords X, Y, Z", treat it as a focused diff — don't take the opportunity to rewrite unrelated paragraphs.

When iterating:
- Apply only what was asked. No drive-by polish of sections the user didn't mention.
- If your change has knock-on effects elsewhere on the page (broken cross-reference, dangling pronoun), flag it briefly — don't silently fix it in a way the user has to hunt for.
- Surface anything still flagged `[VERIFY: ...]` at the end so it doesn't ship by accident.

## Don'ts

- Don't write a new file when the task is editing an existing one.
- Don't invent legal, regulatory, or factual claims to make the prose sound complete.
- Don't reformat or restructure unrelated sections "while you're in there".
- Don't ask more than 3 clarifying questions in a single turn.
- Don't add emojis unless the existing copy uses them.
- Don't strip the user's voice and replace it with generic marketing register.
