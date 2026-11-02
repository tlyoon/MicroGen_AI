# PR249 — source-bounded symbolic dimensional QA beyond single tree-height example

## Problem addressed

PR246 checks a specifically typed numerical tangent-height calculation, but it does not generalize to source-grounded algebraic formulas. PR248 demonstrated original Serway §1.3 Dimensional Analysis on seven privately authored slides. This PR adds an **opt-in, section-independent mathematical consistency checker** for typed relations with dimensions of **length (L), mass (M), and time (T)**.

The new `microgen_portable_source_dimensional_relations.py` safely parses typed mathematical expressions with Python `ast` as DATA (never executes them). Supported operators: multiplication, division, bounded integer powers, numeric dimensionless factors, unary signs, and addition/subtraction only between terms with identical dimensions. It rejects function calls, attribute access, subscripts, unknown variables, bad dimensional arithmetic, division by zero, oversized expressions, excessive powers and unsafe AST syntax. Its dimensional results are bounded integer vectors `[L,M,T]`.

A manifest may optionally include `source_dimension_claims`:

```json
{
  "source_dimension_claims": [{
    "slide": 5,
    "source_page": 2,
    "source_passage_ids": ["<verified-original-PDF-passage-id>"],
    "source_anchor": "<short-literal-source-anchor>",
    "required_source_terms": ["speed", "acceleration", "time"],
    "variables": {"v": "L/T", "a": "L/T**2", "t": "T"},
    "lhs": "v",
    "rhs": "a*t"
  }]
}
```

Every claim requires original PDF SHA equality, real source passage ID/page and source-anchor proof independently rebuilt using PR244/PR248, and two or more original source terms. The narrated slide must point to the same physical source page. An invalid or ambiguous claim fails closed before any slide PDF is created. Old manifests without these annotations retain identical behavior, reporting **zero independently checked dimensional relations**. Per-slide figure, source equation, typed numerical QA and new dimension records coexist in the existing slide and final media receipts.

## Real new subsection, original Serway §1.3

Private original three-page PDF SHA `181f0f361809d90daf72fce1bf50bcf2b88fbf37fc59ed181411266b53cb5ae8` unchanged. The seven-topic original candidate from PR248 was copied into a fresh private stage with **three** separately source-cited dimensional checks:

- A position equation with acceleration and time squared: `x` and `a*t**2` both have dimension `L`.
- Speed versus acceleration times time: `v` and `a*t` both have dimension `L/T`; adding another factor of time is rejected.
- Circular-motion acceleration versus squared speed divided by radius: `a` and `v**2/r` both have dimension `L/T**2`.

The original source passages are explicitly cited in the private manifest, and the technical PDF receipt reports **3** successful checks on slides 3, 5 and 6. Fresh seven-slide private PDF SHA `37b9a9e53d7c25552fa41317c95e47eb7867a5a18c30fb6eec8a0937d872f936` at `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR249_SERWAY13_THREE_DIMENSIONAL_RELATIONS_SLIDES`; complete private stage `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR249_SERWAY13_THREE_DIMENSIONAL_RELATIONS_STAGE`.

Synthetic tests `tests/test_microgen_portable_source_dimensional_relations.py` and previous typed source math tests yield **44 focused passed**, including malicious expressions, dimensional inconsistency, forged source anchor/page, bad original PDF source SHA, repeated slide, excessively complex variables and old-backward-compatible no-claims case. Root HP regressions and four hosted CI jobs required on exact PR head.

## Scope and remaining uncertainty

This checker proves **necessary dimensional algebra** and precise source-page/anchor identity, not physical derivation, whether a variable has been assigned the physically appropriate dimension, exact textbook symbol parsing, missing dimensionless coefficients, full scientific entailment, correct equations in all lecture slides, or publication rights. A dimensional match can still describe an incorrect physical law. It does not replace semantic QA or authorize the textbook/video/experimental Piper voice for release. All `publication_allowed=false`, `formal_voice_authorized=false`. No outside model, paid service or unauthorized device is used.
