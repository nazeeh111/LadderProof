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

## Finite tolerance catalog

`search(request, budget=Budget(), max_designs=128, max_corner_solves=1048576)`
accepts `ladderproof.catalog.v1`, one existing design, an ordered `catalog` entry
for every resistor, and exactly one `minimum_step_volts` or `minimum_dnl_lsb`.
Each entry has only `id` and one to four `options`; each option has exact-string
`tolerance` in [0,1) and nonnegative `cost` at most 1e12 user-defined units.
The nominal values, topology and reference come from the supplied design.
Options replace its independent min/max intervals with nominal*(1±tolerance).
The original intervals remain in the request as baseline context, not constraints
on the replacement catalog. This is not matched/correlated manufacturing yield.

There are at most 4096 combinations. Enumeration sorts exact additive cost, then
original zero-based option indices lexicographically in resistor order. Each
admitted candidate is completely analyzed and independently verified. The first
verified candidate whose exact minimum step meets the inclusive threshold proves
minimum cost within this catalog; no global continuous/physical optimum is claimed.
The DNL threshold is converted exactly by `(DNL+1)*Vref/2^bits`. Negative/zero
minimum steps retain their existing static meaning.

`ladderproof.catalog-result.v1` contains the canonical request, `status`,
`optimal`, reason, work counts and optional selection (indices, exact cost,
complete existing-format certificate). `optimal` status means a feasible minimum
cost selection; `infeasible` means every finite catalog combination was checked.
`unfinished` means work/deadline/cancellation stopped the search, with no selection
and no infeasibility/optimality claim. Cost ordering finds the optimum at the first
feasible result, so no earlier feasible incumbent needs to be discarded.

`max_designs` is 1–4096; `max_corner_solves` is 1–2097152 and reserves twice each
candidate's corner count before starting, for producer and independent verifier.
Counts reserve whole attempts, including an interrupted attempt. Nominal/witness
recomputations are bounded additional work (four circuit evaluations per attempted
design); they are not corner-enumeration counts. The shared cooperative operation
budget remains at most 120 seconds; HTTP retains its existing process limit.

`chosen_certificate(result, budget=Budget())` bounds and detaches the imported
record, recomputes selected option ranges/cost and independently verifies its
complete certificate and threshold. It exports the existing certificate format
for `verify`, `compare` and browser import. It checks selection feasibility and
request binding, not an untrusted saved global optimality claim. Re-run `search`
on the report's request to re-establish catalog optimality.

CLI `catalog request.json --output selection.json` writes the report. It exits 0
for proven feasible optimum or exhausted infeasibility; an unfinished search
writes an explicitly unfinished report and exits 3. An unfinished search cannot
replace any existing output, including with `--force`. `choose selection.json
--output chosen.json` independently checks and exports only a complete feasible
certificate. Default atomic/non-clobber publication and strict bounded JSON apply.

HTTP `/api/jobs` also accepts `operation: "catalog"`, `request` and optional
`max_designs` / `max_corner_solves`, or `operation: "choose"` and `selection`.
Job `state: "complete"` means the operation returned: inspect the catalog result's
own status for search completion. A killed/cancelled process never returns a
selection. There is no new browser control; existing certificate import accepts
the exported chosen certificate.
