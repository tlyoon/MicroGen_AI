# PR246 — typed source-grounded quantitative equation checks

## Scope

A reproducible, **limited** mathematical QA improvement for the original MicroGen_AI portable source-to-lecture pipeline. Prior PR241 embedded original vector equations without retypesetting; PR245 proved original figure crop pixels and nearby captions. Neither verified even simple numerical calculations. The new `microgen_portable_source_math_claims.py` independently computes explicitly declared **right-triangle tangent height** claims, checks the measured values inside the source figure text, and checks the printed numerical answer inside the original source vector-equation region. This is bounded evidence, not a claim of general mathematical reasoning.

Optional per-source section manifest `source_math_claims` example:

```json
{
  "slide": 7,
  "figure_slide": 6,
  "source_page": 2,
  "formula": "right_triangle_tangent_height",
  "horizontal_distance_m": 50.0,
  "elevation_degrees": 25.0,
  "claimed_height_m": 23.3,
  "precision_decimals": 1,
  "source_figure_text_terms": ["50.0 m", "25.0"],
  "source_equation_answer_text": "23.3 m"
}
```

The claim is accepted only when:
- The same source PDF page has already passed immutable original-figure PNG raster and caption checks, and an original vector-equation crop is validated for the stated teaching slide.
- Both literal source measurement tokens appear in the corresponding original diagram region, and the **declared numeric distance and angle themselves** match original diagram values with explicit metres and degrees. An alternate fabricated distance/angle pair giving the same result fails closed. The stated numerical answer must also appear in the original vector equation region.
- (h=d\tan(\theta)) in degree mode independently recomputes to the textbook's stated height at the provided display precision.
- The type and units match this narrowly supported use case. Wrong/missing provenance, altered source numeric values, incorrect answer, unsupported formula and unsafe precision fail closed.

Old manifests without `source_math_claims` render identically and have **zero independently checked typed numerical claims**. Technical slide and video receipts report this count, with `mathematical_equation_semantics_proven=false` and all publication and voice-authorization flags remaining false.

## Actual authorized HP, original Serway §1.2 validation

The five-page source PDF remains SHA-256 `814ce3e174b730271b04bbec4284bb4a15930d5026a2fcbb5148e0cf5ec018cb`. Independent computation:

[
  h=(50.0\,\mathrm{m})\tan(25.0^\circ)
   =23.315382907\ldots\,\mathrm{m}
   \approx23.3\,\mathrm{m}.
]

The geometry region includes selectable source tokens `25.0` and `50.0 m`; the original source vector equation region includes `23.3 m`. All 4 original textbook figures remain geometrically verified. Fresh private source manifest with typed claim and 16-slide output at `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR246_SERWAY12_MATH_GROUNDED_STAGE` and `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR246_SERWAY12_MATH_GROUNDED_16_PDF`. Actual fresh rendered teaching PDF SHA `a771207425df8dd43244303b564a0a6884da789c54799f3a4c6213e7b03a0ba9`. Private receipt `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR246_REAL_TYPED_MATH_PRIVATE_QA.json`.

Synthetic automated tests `tests/test_microgen_portable_source_math_claims.py` exercise positive source-anchored computation, wrong triangle values, wrong source printed answer, missing figure/equation links, unsafe types and unsupported formula. Other existing tests continue to guard source slide/figure/pipeline alignment. No protected source, original diagrams, neural voice weights or media enter GitHub.

This improves a narrow math class only. It does **not** establish the pedagogical assumptions of geometry, full symbolic derivation correctness, all physics formulas, all textbook curriculum, accessibility, full phonetic voice correctness or distribution rights. A generic mathematical-reasoning QA service remains future work; do not turn source-text OCR errors into repeated stalls.
