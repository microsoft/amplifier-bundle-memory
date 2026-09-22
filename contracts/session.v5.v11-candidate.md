# Save wording and human evidence (DRAFT)

The 2026-09-22 isolated native save gate exposed a model call carrying derived
note wording, a valid separate human quotation, and the contradictory label
`writer: human`. The save adapter replaced that quotation with generated text,
and the library correctly refused attribution. No memory was saved. The edit
adapter already handles this shape by preserving the quotation and labeling the
wording assistant-authored.

Apply that same rule to save: only when `writer` is `human`, the supplied quote
is nonempty, and it differs from the raw untrimmed text, treat the wording as
assistant-authored and pass the original quote to library verification. Classify
raw input before trimming. This adds no authority: an unsupported quotation is
still refused, and a missing quotation cannot approve generated wording.

Literal `/remember` text retains human authorship and its existing quotation
rules. There is no store layout, personal policy, read/write announcement,
subagent-write, session-origin, approval, or frozen-contract change.

Evidence: real temporary-store save failure; module regressions check committed
writer/quote metadata and fresh reads, literal raw equality, boundary whitespace,
and forged/missing evidence refusal without store or HEAD mutation. A bounded
native save and separate fresh load establish the runtime gate after this fix.
