# Provider-neutral voice input handoff for validated portable sections

Use `microgen_portable_voice_input_handoff.py` after the independent
source-bound authoring gate and `microgen_portable_slide_render.py`.
It accepts a private stage and its immutable rendered slide candidate:

```text
python microgen_portable_voice_input_handoff.py \
  --private-stage PRIVATE_STAGE \
  --private-slides PRIVATE_SLIDES \
  --new-private-output NEW_LOCAL_PRIVATE_HANDOFF.json
```

The private JSON contains one exact narration request per rendered slide,
source identity, topic/page alignment, hashes and output requirements. A
matching result does **not** synthesize speech, select a voice, change the
configured production provider, mark publication approved or remove the
need for scientific/acoustic review. Requests must remain on the authorized
private host; their narration text is not suitable for GitHub CI logs.

This generalizes a portable stage handoff to source-bound lessons with
2-20 slides. The earlier specialized eight-slide
`microgen_formal_voice_handoff.py` remains unchanged, with its own stronger
diagnostic-video preconditions. Neither pathway grants production approval.

Existing source PDFs, previously accepted audio/video, private figures, and
existing verification receipts should not be regenerated as part of this handoff.
It needs no local LLM, offline TTS model, cloud API or added paid service.
