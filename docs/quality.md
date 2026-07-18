# Quality report

Every completed VectorForge job includes an explainable `quality` report. It
describes observable output health; it is not a guarantee of artistic fidelity
or a model-accuracy score.

| Field | Meaning |
| --- | --- |
| `score` | A 0–100 heuristic assembled from the indicators below. |
| `level` | `good`, `review`, or `unsupported`. `review` means inspect before production use; `unsupported` means the input resembles content outside VectorForge’s intended scope. |
| `warnings` | Plain-language reasons a user should inspect the result. |
| `foreground_coverage` | Fraction of the processing canvas classified as artwork. |
| `path_count` | Number of editable SVG fill paths emitted. |
| `retained_color_count` | Flat colour layers retained after quantization/filtering. |
| `removed_component_count` | Tiny connected components rejected by the selected minimum-area threshold. |
| `visual_similarity` | A deterministic 0–1 preview comparison indicator. It is not a perceptual-quality guarantee. |
| `svg_complexity` | Drawing-command and path-data counts plus a low/medium/high complexity level. |
| `model_metadata` | Whether optional segmentation was requested, the actual provider, checkpoint architecture/digest when used, and a safe fallback reason when applicable. |
| `input_kind` | A deterministic assessment such as `line-art`, `flat-artwork`, `complex-artwork`, `photo`, `document-or-spreadsheet`, or `screenshot-or-interface`. |

## Interpretation

- **Good**: the result meets the current heuristic’s supported-artwork checks.
- **Review**: VectorForge created an SVG but has identified a reason to check it
  before publication, printing, or use in a design system.
- **Unsupported**: the image looks more like a photograph, document, screenshot,
  or dense text than a logo, icon, sketch, or flat illustration. The service
  surfaces this as an explicit warning rather than silently claiming a useful
  conversion.

An empty path set is never a completed result. It fails with a safe actionable
error and no SVG download link.

## Model provenance

`model_used` identifies the foreground-mask source. `model_metadata` adds the
architecture and pinned checkpoint digest when TorchVision is used, or a safe
fallback reason when it is not. Values beginning with `opencv-fallback:` mean
the optional pretrained TorchVision model was requested but unavailable or
unusable, so the deterministic OpenCV fallback completed the job. This behavior
is intentional: no model weights are downloaded during an API request or worker
inference.
