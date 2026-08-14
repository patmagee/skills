# Wait What

A one-keystroke way to say that the last message did not land, and to get the same
content back in plainer language.

## When to use it

Type `/wait-what` when a reply is dense, jargon-heavy, or has jumped ahead of you.
The skill does not answer a new question. It re-pitches the previous message from a
lower altitude.

The skill is user-invoked only. It never fires on its own, because a re-pitch is
worth having only when the reader says the first pitch failed.

## What it does

The re-pitch has three constraints:

1. **Context first.** The reply opens with what the reader is missing, naming the
   subject and where it sits, before saying anything about it.
2. **Simplified Technical English.** The reply follows ASD-STE100, a controlled
   English standard written so a reader who does not speak English as a first
   language can read technical text without ambiguity. That means one instruction
   per sentence, active voice, simple tenses, one word for one meaning, and no
   idiom.
3. **Project vocabulary.** The reply uses the terms defined in `CONTEXT.md` in the
   working directory, exactly as that file defines them. If `CONTEXT.md` is absent,
   the reply says so in one line and continues.

## Harnesses

Claude and Codex only. Both can express a skill that the model is not allowed to
invoke on its own. A Cursor rule has no user-only mode, so shipping it there would
let the agent attach the skill by itself, which is the one thing this skill must
not do.
