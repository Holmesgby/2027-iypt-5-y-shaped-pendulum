# Bowditch (Y-shaped) pendulum — interactive simulator

An interactive, physically faithful simulator and demonstration of the **Bowditch
pendulum** (the "Y-shaped pendulum"), built for **IYPT 2027 Problem 5**.

The rig is two upper strings of length `l` hung from anchors separated by `2R`, joined
at a knot, with a lower string of length `L` carrying the bob. Released from a corner,
the bob does not swing in a straight line: it traces a slowly precessing Lissajous
figure. This program animates that motion in real time, draws the figure the bob
traces, and lets you change every geometric parameter with a slider and see what
happens to the pattern.

Nothing here is a canned animation: the two normal-mode frequencies, the
amplitude dependence, the coupling between the modes and the effect of the knot's mass
are all computed from the model described below.

## Contents

| File | What it is |
|---|---|
| `ypendulum_gui.py` | tkinter GUI: eight parameter sliders, side-view animation, 2-D Lissajous trace, envelope panel, rotatable 3-D view |
| `ypendulum_sim.py` | Physics engine and figure export; no GUI dependency, runs headless (`--selftest`, `--export`) |
| `verify_3d.py` | Numerical self-test of the 3-D projection mathematics; needs no display |
| `demo_three_states.py` | Builds the three-constraint comparison figure (matplotlib) |
| `capture_3d.py` | Optional helper that renders the 3-D view from four preset viewpoints to PNG through the GUI canvas. Converting PostScript to PNG needs Ghostscript; without it the script still writes the `.ps` files and exits cleanly |
| `模拟器使用说明.md` | Chinese user guide: interface tour, controls, suggested five-minute demonstration |
| `模拟实验报告.md` | Chinese report of the simulated measurement chain (virtual apparatus, estimator, error budget) |

## Physics of the model

### Two decoupled horizontal modes

The bob's horizontal motion separates into an in-plane component `x` (in the plane of
the two ceiling anchors) and an out-of-plane component `y`. In the main, tied-knot
configuration the two modes have different effective lengths, hence different
frequencies:

```
h     = sqrt(l^2 - R^2)                  knot depth below the ceiling
f_in  = (1/2*pi) * sqrt(g / L)           in-plane     (effective length L)
f_out = (1/2*pi) * sqrt(g / (L + h))     out-of-plane (effective length L + h)
f_r   = f_in / f_out = sqrt(1 + h / L)
```

`g = 9.79324 m/s^2` is used throughout, consistent with the rest of the project.

### Why the in-plane mode is exactly a length-`L` pendulum

For a tied knot the knot's constraint circle lies entirely in the plane `X = 0`, the
plane of the two anchors, so the knot has **no in-plane degree of freedom**. In-plane,
the lower string is therefore a simple pendulum of length `L`. Out of plane the knot
does move, and the small-oscillation mode has effective length `L + h`, where
`h = sqrt(l^2 - R^2)` is the knot's depth below the ceiling, fixed by the two upper
arms of length `l` anchored at `±R`.

### Amplitude-dependent correction

The exact pendulum slows down as its amplitude grows. The simulator uses the
elliptic-integral expansion

```
T(A)/T_0 = 1 + A^2/(16 l^2) + 11 A^4/(3072 l^4)
   <=>   f(A)/f_0 = 1 - A^2/(16 l^2) - 11 A^4/(3072 l^4)
```

and back-solves it into the Duffing coefficients of the engine's acceleration law
(`a = 1/(6 l^2)`, `b = (16/5) * 11/(3072 l^4)`, evaluated with each mode's effective
length). Both modes slow down with amplitude, the in-plane one more than the
out-of-plane one, so the beat period lengthens. `--selftest` reproduces this law to
about `7e-7` relative at `A = 50 mm` (the test's own threshold is `5e-4`).

### Knot mass

With `mu = m_K / m` and `a = h / (L + h)`, the knot mass enters asymmetrically:

* `f_in` is **exactly independent of `mu`** — the knot has no in-plane freedom, so its
  inertia cannot load the in-plane mode;
* `f_out` **rises** as `sqrt((1 + mu*a) / (1 + mu*a^2))`.

At the reference geometry, `mu = 0.01` lowers `f_r` by about 0.12% (to `1.3433`), which
is why the knot mass has to be calibrated rather than ignored.

### Slack threshold

`x_c = R * L / h` is the release amplitude above which one upper arm goes slack and
the model stops applying (it is `0.0742 m` at the reference geometry). The GUI warns
when the release amplitude exceeds it.

### Inter-mode coupling

The engine adds an `x^2 y^2` coupling term whose coefficient (`0.420`) was calibrated
against a direct numerical integration of the complete nonlinear dynamics: an
equal-amplitude release must reproduce beat periods of `4.291994`, `4.305508` and
`4.327382 s` at `A` = 20, 40 and 60 mm. `--selftest` re-derives `T_beat` from the model
and checks it against all three values.

## Reference values

At the project's reference geometry `l = 0.250 m`, `R = 0.060 m`, `L = 0.300 m`, with a
massless knot:

| Quantity | Value |
|---|---|
| `h = sqrt(l^2 - R^2)` | `0.242693 m` |
| `f_in = (1/2*pi) * sqrt(g/L)` | `0.909332 Hz` |
| `f_out = (1/2*pi) * sqrt(g/(L+h))` | `0.676093 Hz` |
| `f_r = f_in / f_out = sqrt(1 + h/L)` | `1.344982` |
| `x_c = R * L / h` | `0.0742 m` |

With the interface's default knot mass of `0.2 g` (`mu = 0.002`) the same geometry
gives `f_out = 0.676260 Hz` and `f_r = 1.344650`.

Changing only the mechanical constraint at the knot changes the pattern completely:

| Knot constraint | `f_r` at the reference geometry | Behaviour |
|---|---|---|
| tied knot (main rig) | `1.344982` (massless), `1.344650` at `0.2 g` | the figure precesses; beat period about 4.3 s |
| sliding ring | `1.013574` | the two modes are nearly degenerate; precession takes of order 100 s |
| 3-string tripod | exactly `1.000000` | strictly degenerate; the figure never precesses |

## Features

**Two tabs.**

* **Tab 1 — animation and 2-D trace on one page.** Three synchronised panels share one
  simulation state: the top-view Lissajous trace (the largest panel), an envelope panel
  showing `|x(t)|` and `|y(t)|` and therefore the beat, and the side-view animation of
  the real rig (two upper arms, knot, lower arm, bob with an afterglow trail). The
  panels are laid out with grid weights, so they keep their proportions when the window
  is resized.
* **Tab 2 — rotatable 3-D view.** Drag with the left button to orbit (azimuth free,
  elevation clamped to `±88°`), wheel to zoom (`1.15x` per notch, clamped to
  `0.2x`–`8.0x`), double-click to reset to azimuth `38°` / elevation `24°`. Optional
  slow auto-rotation, and an optional trace in 3-D.

**Eight parameter sliders:** upper arm `l` (0.100–0.800 m), half spacing `R`
(0.005–0.300 m), lower arm `L` (0.050–0.900 m), knot mass `m_K` (0–5.0 g), release
amplitude `A` (0.002–0.150 m), release azimuth `psi_0` (0–90°), damping `b`
(0–0.200 1/s), and a time rate (0.1–3.0x) that scales playback only, never the physics.
Four presets (reference geometry, 1:1 degeneracy, wide V, short lower arm), plus
play/pause, re-release, clear trace and save-trace-PNG.

**Three knot-constraint modes:** tied knot, sliding ring, 3-string tripod — see the
table above.

**Bilingual interface (Chinese / English).** The `Language` row at the top of the
control panel switches every label, button, tab title and on-canvas caption at runtime —
including the canvases that are not currently visible. The default follows the system
locale (Chinese locale → Chinese, otherwise English); `--lang zh` / `--lang en` forces a
choice at startup. All UI strings live in `i18n.py`, so adding a language means adding one
column to one dictionary, and `python i18n.py` checks that both languages define exactly
the same keys with matching `%`-format placeholders.

**Zoom with auto-fit.** Fit-to-device (default), fit-to-trace, or manual (0.25x–4x);
each view derives its own scale from its own canvas aspect ratio, so neither panel is
cropped when the other is tight. The `+` / `−` buttons step by 1.25. In the automatic
modes the readout shows the effective scale of each view in px/m.

**Live readouts:** `h`, `f_in`, `f_out`, `f_r`, `T_beat`, `x_c`, elapsed time and the
current `|x|`, `|y|`, all updated as the sliders move, plus warnings for a release
beyond the slack threshold, for strict or near degeneracy of the modes, and for beat
periods long enough that a higher time rate is worth using.

## Install and run

Requirements: **Python 3.8 or newer with tkinter**, which ships with the official
Python installer for Windows and macOS; on many Linux distributions it is a separate
package (for example `python3-tk`). The GUI itself needs **no third-party packages**.

matplotlib is needed only by the figure-export and demo scripts; the GUI's `make_figure()`
prefers matplotlib and falls back to Pillow when matplotlib is unavailable, so PNG export
needs at least one of the two installed.

```
python ypendulum_gui.py            # start the simulator
python ypendulum_gui.py --lang en  # start in English (also: --lang zh)
python ypendulum_gui.py --smoke    # GUI self-test (needs a display); exits by itself
```

Optional dependency, only for the export scripts:

```
pip install -r requirements.txt    # matplotlib>=3.5
```

## Self-tests

Four commands; all are headless except the last. All four pass on the current
sources (Python 3.12.14, matplotlib 3.11.2): `I18N: PASS`, `SELFTEST: PASS`,
`VERIFY 3D: PASS`, `SMOKE OK`.

```
python i18n.py
```

The i18n table: both languages must define exactly the same keys and the same
`%`-format placeholders, so a half-translated string is a test failure rather than a
runtime crash. Prints `I18N: PASS` or `FAIL`.

```
python ypendulum_sim.py --selftest
```

Physics. Checks the reference-geometry analytics, the three knot-constraint states
(tripod degeneracy to `1e-9`, sliding within `2e-3` of the reference value, tied within
`2e-5` for a massless knot), the two knot-mass predictions (`f_in` unchanged, `f_out`
rising), energy conservation of the RK4 integration over 60 s (threshold `1e-3`
relative drift), the integrated frequency against its analytic value (threshold
`2e-4`), the amplitude shift against the elliptic-integral law (threshold `5e-4`), and
the amplitude dependence of `T_beat` against the three calibrated values (threshold
`2e-3`). Prints `SELFTEST: PASS` or `SELFTEST: FAIL`.

```
python verify_3d.py
```

3-D projection mathematics, no display required. Checks that the camera basis is
orthonormal and right-handed (maximum deviation below `1e-12` over four viewpoints);
that the projection agrees point by point with an **independently written** analytic
perspective formula (5 viewpoints x 27 points; maximum deviation `0` px in the current
run); that the projection is isotropic at the centre (numerical-Jacobian singular-value
ratio `1.0000`; the test requires at least `0.95`); that the rig is never clipped across
**56 viewpoints** (7 azimuths x 8 elevations, filling 20%–85% of the frame height, with
at least 40% required for elevations of 20° and above); that depth ordering and the
`1/depth` scale law hold; that extreme viewpoints (`±89.99°`) stay finite; and that all
three knot states project. It also reads `ypendulum_gui.py` to confirm that it is
checking the constants the GUI actually uses. Prints `VERIFY 3D: PASS` or `FAIL`.

```
python ypendulum_gui.py --smoke
```

GUI, needs a display. Builds the window, draws every tab and checks that each canvas
really produced items (on tab 1 the side view, the trace and the envelope must all be
drawn at once), exercises the parameter/slider path, and then checks interaction: drag,
wheel and reset on the 3-D view, and the zoom system — the `+` / `−` buttons change the
factor by exactly 1.25, manual zoom scales the px/m factor linearly (`1.00x` to `2.00x`
exactly doubles it), and in both automatic modes the content stays inside the canvas
for five very different geometries (reference, wide V, short lower arm, long lower arm,
large amplitude). Prints `SMOKE OK` or `SMOKE FAIL: ...`. On a machine with no display
it reports that it cannot create a window and exits non-zero.

## Exporting figures

```
python ypendulum_sim.py --export traj.png     # 30 s run, 2-D trace to PNG
python demo_three_states.py [outdir]          # the three knot constraints side by side (default: figs/)
```

The GUI's "save trace PNG" button writes `lissajous_export.png` next to the sources.
Figure labels are in English because matplotlib's bundled fonts carry no CJK glyphs; the
tkinter interface itself is in Chinese and renders it without trouble.

## Known limitations

1. The animation is an **effective-length model**, not a per-string constraint solve. It
   reproduces the two normal-mode frequencies, the amplitude nonlinearity, the inter-mode
   coupling and the knot-mass effect, but **not** string elasticity, the knot's fast
   internal vibration (about 13.6 Hz), or stick-slip friction.
2. The **sliding-ring mode is anchored, not derived**: its in-plane frequency has no
   analytic relation to the geometry in this model, so the code anchors it to the
   project's reference value (`f_r = 1.013574`) and scales it with `1/sqrt(L)`. Treat that
   mode as a qualitative demonstration of near-degeneracy.
3. **Above the slack threshold `x_c = R*L/h` the model does not apply**: one upper arm goes
   slack. The program warns and keeps running for demonstration purposes; do not draw
   conclusions from data taken in that range.
4. The **interface is bilingual**: Chinese and English, switchable at runtime from the `Language` row at the top of the control panel, or forced at startup with `--lang zh` / `--lang en`. The default follows the system locale. Only the exported figures are English-only, because matplotlib's bundled fonts carry no CJK glyphs.
5. The side view projects three-dimensional motion onto a plane, so out-of-plane
   displacement appears slightly smaller than it really is.

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgements and related work

Built for **IYPT 2027 Problem 5, "Y-shaped pendulum"** — the Bowditch pendulum. The
geometry, the two-mode decomposition and the tied-knot constraint argument follow the
project's own theory notes, and the inter-mode coupling coefficient was calibrated
against its full nonlinear integration. The Chinese user guide and simulated-experiment
report shipped in this repository document the apparatus, the virtual measurement chain
and the falsifiable predictions that come out of the model (beat period lengthening with
amplitude, `f_in` independent of the knot mass, `f_r` independent of the bob mass).
