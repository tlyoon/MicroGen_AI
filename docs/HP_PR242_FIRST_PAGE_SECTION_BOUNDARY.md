# PR242 — First-page section boundary isolation

The portable section auditor previously checked whether a target section heading existed on the first physical source PDF page, but matched topics against the **entire** page. For a real textbook whose section begins mid-page, a prior section's material could be falsely accepted as a source anchor.

The correction searches for the supplied, SHA-bound `start_marker`, then trims the first page's normalized audit text to the **last occurrence** of that marker. The last occurrence is necessary because printed running headers can repeat the exact section name before the actual heading (confirmed in the original Serway 1.1 source: two occurrences on physical page one). This conservative strategy may refuse some legitimate topics whose evidence precedes the last matching marker, which is preferable to silently borrowing prior-section evidence. The academic report now records `preceding_first_page_characters_excluded` for auditability.

Regression-first evidence: the synthetic adversarial preceding-section anchor test failed before the change because the auditor incorrectly accepted an anchor from earlier than section B.2. After correction it is rejected; an additional independent test covers a duplicated header before the true heading. No substantive source or media is rewritten.

Real independent HP no-write probes:
- Serway §1.1 original source, original 14-slide private narration/visual manifest, all exact source and input hashes: existing 14/14 declared topic contract continues to pass with a duplicate heading on its first source page.
- Serway §1.2 original five-page textbook PDF SHA `814ce3e174b730271b04bbec4284bb4a15930d5026a2fcbb5148e0cf5ec018cb`, first actual heading after approximately 1165 normalized first-page characters (belonging to Section 1.1), Section 1.3 start on final page. Source files remain unchanged. The next full-source lecture is *not* generated yet.

This remains a **declared-topic** audit; it does not independently prove the curriculum is complete, equations are scientifically correct, figure semantics are right, or pronunciation/release rights. No external provider calls, publication, other-device work, or Google Drive writes.
