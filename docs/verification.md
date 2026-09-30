# Verification evidence

The admitted mathematics, core implementation and application failure paths received separate local reviews. The result is bounded to the ideal static unloaded R-2R model in [model.md](model.md); neither review nor numerical agreement establishes physical-device behavior.

## Executed checks for 0.1.0

- **Python 3.14.7 source suite:** all 22 tests passed with real loopback HTTP and spawned workers. The suite covers exact analytic and nonuniform ladders, six-bit positive/decreasing interval cases, same-assignment witnesses, complete independent verification, forged/missing/type-spoofed claims, strict bounded inputs, cancellation/deadlines, atomic CLI exports, strict JSON imports and the actual analyze/verify/compare service journey.
- **Node 24.14.0 frontend suite:** all 15 tests passed against production JavaScript. They exercise displayed bound/witness values, exact interval editing, stale and refused responses, delayed initialization/defaults/file imports, generation invalidation and duplicate-field preservation. These are asynchronous behavior tests with a small DOM adapter, rather than rendered-browser accessibility tests.
- **Fresh installed wheel outside the checkout:** Python 3.14.7 imported the installed distribution with isolated interpreter mode and no runtime dependencies. The six-bit create/edit/analyze/save/reopen/verify/tighten/compare journey passed. Its exact minima were −269227/7660721 V at independent ±5% and 186147971/34016602567 V at ±1%, for a 1 V reference.
- **Installed application service:** the installed CLI started the actual loopback server outside the checkout. HTML, JavaScript and CSS responses matched source bytes. A real spawned analysis and independent verification completed through HTTP; the owned server stopped afterward.
- **Artifact identity:** wheel runtime modules/assets and source-archive deliverable files were compared byte for byte against final source, including the README, screenshot, model/contracts/references, examples, tests, CI and installed-smoke script. Offline builds used existing bundled Python 3.12.14 and setuptools 84.0.0. No new local build dependency or remote service was needed.
- **Desktop browser:** edit/analyze/open/verify/compare interactions were observed on the actual 1280-pixel desktop browser surface. The [workbench screenshot](workbench.jpg) records an analyzed state. Browser export was requested, but the download event timed out and no saved file path or bytes were captured. The installed CLI export/reopen checks above provide separate artifact evidence.

The nodal solver uses exact Gaussian elimination. The verifier independently reconstructs the ladder using backward Thevenin reductions, then re-enumerates every admitted corner and computes every code/transition bound. They share only the declared-input contract and resource limits, so this is independent circuit/result reconstruction rather than wholly independent input policy. No ngspice or physical comparison was run.

## Reproduce

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
node --test tests/frontend.test.cjs
```

To test an installed wheel outside the checkout, use a fresh virtual environment at an external path, install with `pip install --no-index --no-deps path/to/ladderproof-0.1.0-py3-none-any.whl`, then run that environment's Python with `-I scripts/installed_smoke.py --source /absolute/path/to/checkout`. The script refuses an import from inside the source checkout and performs real CLI and served-asset/worker checks.

The [September 30, 2026 hosted run for release commit `67925bd`](https://github.com/nazeeh111/LadderProof/actions/runs/36784796139) completed successfully: Python 3.11/3.14 source tests, Node 24 frontend tests and the fresh installed-wheel journey. Python 3.11 was unavailable locally; its pass is hosted evidence. Actions are pinned to verified immutable official release commits, the token has only repository-content read permission, and checkout does not persist credentials. Weekly Dependabot updates cover Actions only.

## Remaining limits

Native viewport override was unavailable, so no synthetic narrow-screen browser pass is claimed. Screen-reader behavior, comprehensive WCAG conformance, a standalone offline HTML-file experience and physical hardware were not verified. The validated application uses its local server and bundled assets. File export/import and inspection evidence cover the admitted model, not arbitrary SPICE circuits, correlations, dynamic switching, yield or real-world measurement uncertainty.
