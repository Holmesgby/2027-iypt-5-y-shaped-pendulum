"""
生成演示图：三种结点状态下的同步二维轨迹（用模拟器同一套物理）。

输出：figs/fig_sim_three_states.png —— 三幅并排的 Lissajous 图案，
      用来直观展示"只改一个机械细节，图案完全不同"。

用法： python demo_three_states.py [输出目录]
"""
import os
import sys
import math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ypendulum_sim import Params, YYSim, derived          # noqa: E402

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.size": 10, "figure.dpi": 150, "savefig.dpi": 150})

G = 9.79324


def run(mode, seconds, A=0.020, damping=0.010, psi=45.0):
    p = Params(mode=mode, A=A, damping=damping, psi_deg=psi)
    sim = YYSim(p=p)
    dt = 2.0e-3
    for _ in range(int(seconds / dt)):
        sim.step(dt)
        sim.push_trace()
    return sim, derived(p)


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    # All figure labels are in English: matplotlib's bundled fonts carry no CJK glyphs and would
    # render Chinese as empty boxes.  The slides and the GUI stay in Chinese.
    cases = [("tied", 30.0, "dev A: tied knot (main)"),
             ("sliding", 300.0, "dev B: sliding ring"),
             ("tripod", 30.0, "dev C: 3-string tripod")]
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.6))
    for ax, (mode, secs, name) in zip(axes, cases):
        sim, d = run(mode, secs)
        xs = [q[0] * 1e3 for q in sim.trace]
        ys = [q[1] * 1e3 for q in sim.trace]
        ax.plot(xs, ys, lw=0.7, color="#c0392b")
        lim = 30.0
        ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
        ax.set_aspect("equal")
        ax.axhline(0, color="#999", lw=0.6); ax.axvline(0, color="#999", lw=0.6)
        ax.grid(alpha=0.25)
        tb = d["T_beat"]
        sub = ("$f_r$ = %.4f   $T_{beat}$ = %s" %
               (d["f_r"], ("%.2f s" % tb) if math.isfinite(tb) else "inf"))
        ax.set_title("%s\n%s   (%.0f s record)" % (name, sub, secs), fontsize=10)
        ax.set_xlabel("in-plane x (mm)")
        if ax is axes[0]:
            ax.set_ylabel("out-of-plane y (mm)")
    fig.suptitle("Same rig, same release, only the knot constraint changes -> three different Lissajous patterns",
                 fontsize=10.5)
    fig.tight_layout(rect=(0, 0.06, 1, 0.93))
    out = os.path.join(outdir, "fig_sim_three_states.png")
    fig.savefig(out)
    plt.close(fig)
    print("wrote", out)
    return out


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "figs"))
