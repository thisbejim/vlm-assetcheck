# Demand and competitive research

Multimodal training formats repeatedly separate annotation JSONL from media files. Hugging Face’s image-dataset guide documents `metadata.jsonl` records whose `file_name` values point to image files: <https://huggingface.co/docs/datasets/en/image_dataset>. The repository has recurring reports of imagefolder metadata/path placement failures, including <https://github.com/huggingface/datasets/issues/7005> and <https://github.com/huggingface/datasets/issues/7337>.

Provider training formats add another failure boundary. OpenAI describes JSONL image inputs for vision fine-tuning in its announcement: <https://openai.com/index/introducing-vision-to-the-fine-tuning-api/>. Microsoft’s current vision fine-tuning guide calls out image-specific JSONL structure and upload validation: <https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/fine-tuning-vision>. An OpenAI developer thread records a file-format failure in an otherwise familiar vision-fine-tuning feed: <https://community.openai.com/t/vision-finetuning-job-failed-due-to-a-file-format-error-on-previously-working-file-official-cookbook-example/1371326>.

Open-weight stacks expose the same contract in different shapes. LLaVA’s training code accepts an `image` field: <https://github.com/LLaVA-VL/LLaVA-NeXT/blob/main/llava/train/train.py>. SenseNova’s preparation guide enumerates annotation JSONL directories alongside required media directories: <https://github.com/OpenSenseNova/SenseNova-Vision/blob/master/docs/train_data_prepare.md>.

## Alternatives checked

- `datasetvision` is a broad computer-vision auditor with heavier image-processing dependencies, not a focused JSONL-reference gate: <https://github.com/nibir-ai/datasetvision>.
- `img2dataset` is a downloader/resizer for web-scale datasets, not a no-network preflight: <https://github.com/rom1504/img2dataset>.
- Dataset editors and general fine-tuning linters can validate row shape, but do not prove that every referenced local byte is safe and readable. `assetcheck` intentionally complements them rather than becoming another provider schema implementation.

The differentiator is the narrow contract: local-only, dependency-free, line/pointer diagnostics, safe path policy, bounded header inspection, and CI-native output. No direct dedicated cross-provider JSONL media-reference validator with that contract was found in the public search.
