---
name: wait-what
description: Stop. That last message did not land — re-pitch it.
short_description: Re-pitch the last message with context, in Simplified Technical English.
invocation: user
disable-model-invocation: true
harnesses: [claude, codex]
---

# Wait What

Wait — I don't understand where you've got to here. Re-pitch that: give me a little bit of context, talk in ASD-STE100 Simplified Technical English, and use the ubiquitous language from `CONTEXT.md`.

## What a re-pitch is

The previous message failed. Do not defend it, do not apologise for it, and do not
repeat it in the same words. Say the same thing again from a lower altitude.

Start with the context the reader is missing. Name the thing you are talking about
and where it sits, before you say anything about it.

## Simplified Technical English

ASD-STE100 is a controlled English standard written so that a reader who does not
speak English as a first language can read technical text without ambiguity. Apply
these rules:

- Write one instruction in one sentence. Keep procedural sentences to 20 words or
  fewer, and descriptive sentences to 25 words or fewer.
- Use the active voice. Write "the task resets the status", not "the status is
  reset".
- Use one word for one meaning, and keep that word for the whole message.
- Use simple present or simple past tense. Avoid the perfect tenses and avoid
  conditional constructions where a plain statement will do.
- Do not use noun clusters of more than three words.
- Do not use slang, idiom, metaphor, or any word whose meaning depends on a
  region.
- Spell out an abbreviation on its first use.

## Ubiquitous language

Read `CONTEXT.md` from the working directory and use its terms exactly as it
defines them. That file is the shared vocabulary for this project, so a term it
defines must not be paraphrased or replaced with a synonym.

If `CONTEXT.md` does not exist, say so in one line and continue with the rest of
the re-pitch. Do not search the repository for a substitute and do not stall.
