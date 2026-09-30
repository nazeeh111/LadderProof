# Design, certificate and command contract

A design has `format: "ladderproof.design.v1"`, `model: "ideal-static-r2r-voltage"`, integer `bits` from 2 through 6, positive exact-string `vref`, optional `title`, and ordered `resistors`. Each resistor has only `id`, `nominal`, `min`, `max` fields. The required identities are B0 through B(n−1), S0 through S(n−2), then T. Values are in ohms; reference/output values are in volts. Unknown fields, arbitrary topology and correlation fields are refused.

An exact number is an integer, a decimal with at most 12 decimal places, or a fraction string. Scientific notation, JSON floating-point numbers, NaN and infinity are refused. Reduced numerator and denominator must each fit 64 bits. Resistance values satisfy 1e-9 ≤ min ≤ nominal ≤ max ≤ 1e12 ohms; reference satisfies 1e-9 ≤ Vref ≤ 1e6 volts. These broad finite bounds and the 2–6 bit limit make individual exact corner work bounded. Titles are at most 120 characters without control characters. CLI JSON is at most 1 MiB, duplicate keys are refused, and verifier record structure is bounded before computation.

Public library API:

```python
from ladderproof import Budget, make_design, parse_design, analyze, verify, compare

design = parse_design(make_design(6, "1/100", "1"))
certificate = analyze(design, budget=Budget(seconds=30, cancel=lambda: False))
verification = verify(certificate, budget=Budget(seconds=30))
comparison = compare(previous_certificate, certificate, budget=Budget(seconds=60))
```

Only a completed analysis returns `ladderproof.certificate.v1`, `algorithm: "exact-corners-v1"`, `status: "complete"`, its canonical design and its `corner_count`. Results contain nominal code voltages; per-code min/max values and masks; per-adjacent-transition min/max values and masks; the adverse transition with exact resistor assignment and both code voltages; and `nondecreasing`. DNL is `(actual step)/(Vref/2^n) − 1` in ideal least-significant-bit units. Masks index only uncertain resistors, in design order; bit zero corresponds to the first uncertain resistor. Zero selects min, one selects max. Ties prefer the lowest mask; worst transition ties prefer the lowest code.

The verifier independently reconstructs the circuit and completely re-enumerates its box. It compares every declared result, type and field. Changing an input, omitting a code, faking the count, forging a witness or declaring partial results invalidates the record. Verification is not a hash check and does not trust the producer's bounds. Shared schema validation intentionally enforces the same admitted model; solving and result aggregation are separate implementations.

`Budget` uses a monotonic deadline and optional cancellation callback. Seconds must be finite, greater than zero and at most 120. A callback returning true raises `Refused`. Checks occur before/after validation and between bounded corner solves. Native Ctrl-C remains available. A deadline is cooperative rather than a hard operating-system kill; the browser service runs its work in a separately bounded child process. No incomplete computation returns a certificate.

CLI exits:

| Exit | Meaning |
|---:|---|
| 0 | Created, analyzed, independently verified, or verified comparison |
| 1 | Malformed/incomplete/mismatching certificate |
| 2 | Invalid design or JSON, unsupported input, I/O failure, protected existing destination |
| 3 | Operation deadline/resource refusal |
| 130 | Native keyboard interrupt |

Input-data and operation error details are JSON on stderr; command-line syntax errors use the standard argument-parser message. Successful data is JSON on stdout or an explicit output path. Default writes are atomic and non-clobbering. `--force` authorizes replacement only after the entire operation succeeds. Temporary data is cleaned up on handled failure. An interrupted computation preserves an existing result. If interruption happens during atomic publication, check the destination: the complete new result may already have replaced the previous result, and the CLI reports that uncertainty. A killed process may leave an incomplete temporary file named `.ladderproof-*`; it never becomes the output destination.
