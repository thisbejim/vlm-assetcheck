# Opportunity scorecard

Scores are 1–10, with 8 as the minimum for a build decision. They reflect the evidence in [research.md](research.md) and the product boundary in [product-spec.md](product-spec.md).

| Criterion | Score | Rationale |
| --- | ---: | --- |
| Pain severity | 9 | A missing byte can invalidate an upload or an entire training run. |
| Frequency | 8 | Every multimodal export crosses a manifest/media boundary. |
| Demand evidence | 9 | Provider docs plus repeated public path/format issues. |
| Frontier relevance | 9 | VLM fine-tuning and evaluation are growing workflows. |
| Improvement over status quo | 9 | Framework loaders are late; generic JSONL tools cannot inspect bytes. |
| Standalone feasibility | 10 | Standard-library parser and bounded header checks. |
| Local-first/privacy | 10 | No network, credentials, uploads, or media writes. |
| Deterministic testability | 10 | Synthetic headers and JSONL fixtures cover each rule. |
| Maintainability | 9 | Small modules, stable codes, no runtime dependencies. |
| Discoverability | 8 | `assetcheck` names the preflight job directly. |

No criterion is below 8, so the opportunity clears the hard gate.
