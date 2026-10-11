# Contributing

Thanks for looking at the Y-shaped (Bowditch) pendulum simulator. This is a small,
self-contained teaching tool: four Python files, no runtime dependencies beyond the
standard library. Keep changes in that spirit.

## Run the self-tests before you open a pull request

All three must pass. The first two need no display; the third needs a graphical
environment.

```
python ypendulum_sim.py --selftest     # physics engine
python verify_3d.py                    # 3-D projection mathematics
python ypendulum_gui.py --smoke        # GUI: window, redraws, interaction, zoom
```

Expected output ends with `SELFTEST: PASS`, `VERIFY 3D: PASS` and `SMOKE OK`.

**Physics changes must keep `--selftest` passing.** That self-test is the contract
between the animation and the analysis: the reference-geometry frequencies, the three
knot-constraint states, the two knot-mass predictions, energy conservation, the
amplitude shift against the elliptic-integral law, and the beat periods calibrated
against the full nonlinear integration are all asserted there. If a change makes one of
those assertions fail, either the model is wrong or the reference values have moved --
in the second case change both the model and the documented values in the same pull
request, and say why in the description.

If you touch the 3-D projection, keep `verify_3d.py` in step. It cross-checks the
projection against an independently written analytic perspective formula, so a real
change of the camera model means updating the analytic formula too, not just the
tolerances. The script also reads `ypendulum_gui.py` to confirm the constants it tests
(`d_cam = 2.6 * Ltot`, the focal-length fit factor `0.85`, the depth floor `0.02 * Ltot`,
and the `d_cam + q[2]` depth term) are the ones the GUI actually uses.

## Code style

* PEP 8, four-space indentation, no tabs. Keep the existing module layout: a short module
  docstring that states what the file is, a command-line usage block where one exists,
  then the sections in their current order.
* Google-style docstrings: one-line summary, then arguments/returns/raises where they are
  not obvious. Public functions and methods get a docstring; helpers may have a short one.
* Comments may be in Chinese or English -- both are already present in the sources --
  but **keep each file internally consistent**. Do not translate half a file.
* Figure labels stay in English (matplotlib's bundled fonts carry no CJK glyphs, so
  Chinese would render as empty boxes); the tkinter interface stays in Chinese.
* Type hints are used in the engine (`from __future__ import annotations`); keep them
  where they already are.
* Physics constants that are shared across files (for example `g = 9.79324`) must not be
  duplicated with different values. If you need one in a new place, import it.

## Scope

* Do not add a runtime dependency to the GUI. matplotlib stays optional, used only by the
  export and demo scripts.
* The GUI is a demonstration of the idealised model, not a measurement chain. Numerical
  experiment code (estimator, error budget, virtual apparatus) lives outside this
  repository's simulator sources; keep it that way.

## Reporting a problem

Include the output of all three self-tests, your OS, your Python version, and -- for GUI
problems -- what you did with the mouse and which tab you were on. A screenshot helps.
