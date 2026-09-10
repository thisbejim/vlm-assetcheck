# Skeptical review

## What could make this low value?

A framework-specific loader may already fail fast for one provider. That is not enough for teams moving between OpenAI-style feeds, Hugging Face imagefolder layouts, and open-weight VLM trainers: each loader reports different locations and often only after upload or job startup. The checker earns its place by proving local bytes before that boundary and by staying provider-neutral.

## What it intentionally does not claim

Header recognition is not full codec validation, and a readable image can still be mislabeled or semantically useless. Remote URLs are not verified. Those limitations are explicit in the README; model-based quality inspection and provider schema validation remain separate tools.

## Main risks and mitigations

- **False discovery:** use an allowlist of media-like keys and JSON Pointer locations rather than scanning every string.
- **Path disclosure:** reports omit payloads and only include the path needed to fix a row; SARIF can be kept as a local artifact.
- **Resource exhaustion:** reject unsafe path forms, cap bytes/pixels, read only bounded headers for recognition, and avoid decoders.
- **Format drift:** keep the diagnostic contract stable and add one focused recognizer plus fixtures for each new container.
