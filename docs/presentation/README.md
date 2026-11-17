# The falling-step witness

The README figure plots the static transfer of one attaining resistor assignment
from `examples/six-bit-five-percent.certificate.json`. It does not combine
per-code minima from different assignments. Its right-hand panel is explicitly a
zoom of codes 28–35, with its own labeled voltage range. The full panel includes
zero and the 1 V reference range. Lines guide the eye between discrete codes;
this is not a settling-time waveform or a physical measurement.

## Recheck the evidence

With Python 3.11+ and no runtime dependencies:

```sh
PYTHONPATH=src python3 -m ladderproof verify examples/six-bit-five-percent.certificate.json
PYTHONPATH=src python3 -m ladderproof verify examples/six-bit-one-percent.certificate.json
```

Both commands were executed against source `HEAD` recorded below on November 17,
2026. They independently recomputed all 4,096 corners of each ideal model.
Captured complete outputs: [±5%](five-percent-verified.json) and
[±1%](one-percent-verified.json).

[All 64 exact code/voltage pairs](five-percent-witness.csv) and
[figure provenance](figure-provenance.json) retain the source hash, attaining
resistors and transformations. The SVG uses editable text with system fallback
fonts. [Desktop PNG](falling-step.png) and [phone PNG](falling-step-mobile.png)
provide fixed rendering alternatives.

## Rebuild the figure

Matplotlib is a presentation-only dependency, not an application requirement.
With an existing Matplotlib environment, run:

```sh
python3 scripts/presentation_figure.py
```

The recorded export used Matplotlib 3.10.8. Exact fractions remain in the data;
conversion to floating point is only for plot positions and display decimals.
No data are smoothed, fitted, sampled or excluded from the full view. The plot
uses the independent verifier's Thevenin reduction helpers to reconstruct the
single witness transfer, after separate complete CLI verification.

## Source identity

Repository: `nazeeh111/LadderProof`

Default-branch head: `ccb0d22ad1651390ae86283143f8b069bd7dc78b`

The presentation changes only documentation and its assets. This record does
not assert that an unpublished engineering successor is merged into the default.
