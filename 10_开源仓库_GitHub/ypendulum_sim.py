"""
Y 形摆（Bowditch pendulum）模拟器 —— 物理与绘图核心（无界面依赖）

这个模块提供两件事：
  1. YYSim：与 IYPT 2027 第 5 题模型一致的实时动力学引擎
     · 两个水平方向精确解耦，有效摆长分别为 L（面内）与 L+h（面外），h = sqrt(l²-R²)
     · 振幅非线性用 4 阶 Duffing 展开，系数取自精确单摆的椭圆积分展开：
           f(A)/f0 = 1 + A²/(16 l²) + 11 A⁴/(3072 l⁴)
       => x'' = -w²(x + a x³ + b x⁵) 给出同样的 f(A)，这里 a、b 由上式反解
     · 模间 x²y² 耦合的系数 C 由"完整非线性动力学直接积分"标定
       （theory-modeler 的 nonlinear_check.py：等振幅释放 T_beat = 4.291994 / 4.305508 /
       4.327382 s @ A = 20/40/60 mm），使动画与实验报告用的是同一套物理
     · 结点质量 μ：面内 f_in 严格不变，面外 f_out 按 (1+μa)/(1+μa²) 升高，a = h/(L+h)
     · 松弛阈值 x_c = R·L/h：超过则一根上臂松弛，模型失效（程序会给出警告）

  2. 把轨迹画成二维 Lissajous 图（matplotlib 或 PIL），供界面右侧同步显示、也可导出 PNG

命令行：
    python ypendulum_sim.py --selftest            # 无界面自检，打印物理量
    python ypendulum_sim.py --export out.png      # 无界面导出轨迹图
GUI 入口是同目录的 ypendulum_gui.py。
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field, asdict

G = 9.79324                      # m/s²，与全项目一致
# 模间 x²y² 耦合系数。由"完整非线性动力学直接积分"标定：等振幅释放时
#   T_beat = 4.291994 / 4.305508 / 4.327382 s @ A = 20 / 40 / 60 mm
# （theory-modeler 的 nonlinear_check.py）。selftest 会按同样的振幅复算并核对，
# 若与文档值偏差 > 2e-3 相对，自检会失败 —— 这样动画与报告用的就是同一套物理。
COUPLING_C = 0.420

# ---------------------------------------------------------------- 参数
@dataclass
class Params:
    l: float = 0.250             # 上臂长 (m)
    R: float = 0.060             # 两孔半间距 (m)
    L: float = 0.300             # 下臂长 (m)
    mK: float = 0.0002           # 结点质量 (kg)
    m: float = 0.100             # 摆球质量 (kg)
    A: float = 0.020             # 释放振幅 (m)
    psi_deg: float = 45.0        # 释放方位角 (°)
    damping: float = 0.020       # 线性阻尼系数 b (1/s)
    mode: str = "tied"           # "tied"=系结(主装置) | "sliding"=滑环 | "tripod"=三弦三脚架
    rate: float = 1.0            # 时间倍率（1.0 = 实时）

    def copy(self) -> "Params":
        return Params(**asdict(self))


# ---------------------------------------------------------------- 派生量
def derived(p: Params) -> dict:
    """由几何算出的各个物理量（全部为解析式，与报告一致）。"""
    l, R, L = p.l, p.R, p.L
    h = math.sqrt(max(l * l - R * R, 1e-12))
    a = h / (L + h)
    mu = p.mK / p.m

    # 两个简正模的线性频率
    f_in0 = math.sqrt(G / L) / (2 * math.pi)
    f_out0 = math.sqrt(G / (L + h)) / (2 * math.pi)

    if p.mode == "sliding":
        # 滑环：一整根绳穿过可动环，两上臂张力恒等 ⇒ 两模近简并。
        # 参考几何下项目文档给出的值是 f_r = 1.013574、T_beat ≈ 110.4 s；
        # 面外模与系结式相同（面外运动不受结点自由度影响），面内模按 sqrt(1/L) 缩放。
        # 该式只用于演示"近简并、几乎不旋进"的定性行为。
        f_out = f_out0
        f_in = f_out * 1.013574 * math.sqrt(0.300 / L)
    elif p.mode == "tripod":
        # 三弦三脚架：结点被钉死 ⇒ 两个模都是摆长 L 的单摆 ⇒ 严格简并
        f_in = f_in0
        f_out = f_in0
    else:
        f_in = f_in0
        f_out = f_out0 * math.sqrt((1 + mu * a) / (1 + mu * a * a))

    f_r = f_in / f_out if f_out > 0 else float("nan")

    # ---- 非线性：由精确单摆的椭圆积分展开反解
    #   f(A)/f0 = 1 - (3a/8)A² - (5b/16)A⁴   （单摆是大振幅**变慢**，故取负号）
    #   a = (8/3)/(16 l²) = 1/(6 l²) ,  b = (16/5)·11/(3072 l⁴)
    def nl(l_eff):
        aa = (8.0 / 3.0) * (1.0 / (16.0 * l_eff ** 2))
        bb = (16.0 / 5.0) * (11.0 / (3072.0 * l_eff ** 4))
        return aa, bb

    a_in, b_in = nl(L)
    a_out, b_out = nl(L + h)

    # 释放条件决定两个模各自的振幅
    psi = math.radians(p.psi_deg)
    Ax = p.A * abs(math.cos(psi))
    Ay = p.A * abs(math.sin(psi))
    l_in, l_out = L, L + h
    d_in = -(3.0 * a_in / 8.0) * Ax ** 2 - (5.0 * b_in / 16.0) * Ax ** 4
    d_out = -(3.0 * a_out / 8.0) * Ay ** 2 - (5.0 * b_out / 16.0) * Ay ** 4
    # 模间 x²y² 耦合：每模还被另一模的振幅平方拖慢
    c_in = -COUPLING_C * (Ay ** 2) / (l_in * l_out)
    c_out = -COUPLING_C * (Ax ** 2) / (l_in * l_out)
    f_in_A = f_in * (1.0 + d_in + c_in / 1.0)
    f_out_A = f_out * (1.0 + d_out + c_out / 1.0)

    T_beat = 1.0 / abs(f_in_A - f_out_A) if abs(f_in_A - f_out_A) > 1e-12 else float("inf")
    T_beat_lin = 1.0 / abs(f_in - f_out) if abs(f_in - f_out) > 1e-12 else float("inf")
    f_r_A = f_in_A / f_out_A

    x_slack = R * L / h                      # 上臂松弛阈值 (m)

    return dict(h=h, a_share=a, mu=mu,
                f_in=f_in, f_out=f_out, f_r=f_r,
                f_in_A=f_in_A, f_out_A=f_out_A, f_r_A=f_r_A,
                T_beat=T_beat, T_beat_lin=T_beat_lin,
                a_in=a_in, b_in=b_in, a_out=a_out, b_out=b_out,
                Ax=Ax, Ay=Ay, d_in=d_in, d_out=d_out, c_in=c_in, c_out=c_out,
                x_slack=x_slack, w_in=2 * math.pi * f_in, w_out=2 * math.pi * f_out)


# ---------------------------------------------------------------- 引擎
@dataclass
class YYSim:
    """实时动力学引擎：状态为 (x, y, vx, vy)，单位 m 与 m/s。"""
    p: Params = field(default_factory=Params)
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    t: float = 0.0
    trace: list = field(default_factory=list)      # [(x, y), ...] 下视轨迹
    warnings: list = field(default_factory=list)

    # ---- 生命周期
    def __post_init__(self):
        self.reset()

    def reset(self, keep_params: bool = True):
        p = self.p
        psi = math.radians(p.psi_deg)
        self.x = p.A * math.cos(psi)
        self.y = p.A * math.sin(psi)
        self.vx = 0.0
        self.vy = 0.0
        self.t = 0.0
        self.trace = [(self.x, self.y)]
        self.warnings = []
        d = derived(p)
        if p.A > d["x_slack"]:
            self.warnings.append(
                "释放振幅 %.1f mm 超过松弛阈值 x_c = %.1f mm —— 一根上臂会松弛，模型失效"
                % (p.A * 1e3, d["x_slack"] * 1e3))

    # ---- 动力学
    def accel(self, x, y):
        p = self.p
        d = derived(p)
        w_in2 = d["w_in"] ** 2
        w_out2 = d["w_out"] ** 2
        ai, bi = d["a_in"], d["b_in"]
        ao, bo = d["a_out"], d["b_out"]
        # Duffing 型自非线性（负号 => 大振幅变慢，与单摆一致）
        ax = -w_in2 * (x - ai * x ** 3 - bi * x ** 5)
        ay = -w_out2 * (y - ao * y ** 3 - bo * y ** 5)
        # 模间 x²y² 耦合（系数由完整动力学标定；符号取使两模都变慢）
        C = COUPLING_C
        ax += -C * x * y * y * w_in2
        ay += -C * y * x * x * w_out2
        # 线性阻尼
        ax -= p.damping * self.vx
        ay -= p.damping * self.vy
        return ax, ay

    def step(self, dt: float):
        """定步长 RK4，dt 由界面传入（默认 2 ms），内部再细分以保精度。"""
        n_sub = max(1, int(math.ceil(dt / 5.0e-4)))
        h = dt / n_sub
        for _ in range(n_sub):
            self._rk4(h)
        self.t += dt

    def _rk4(self, h: float):
        x, y, vx, vy = self.x, self.y, self.vx, self.vy

        def f(x, y, vx, vy):
            ax, ay = self.accel(x, y)
            return vx, vy, ax, ay

        k1 = f(x, y, vx, vy)
        k2 = f(x + 0.5 * h * k1[0], y + 0.5 * h * k1[1], vx + 0.5 * h * k1[2], vy + 0.5 * h * k1[3])
        k3 = f(x + 0.5 * h * k2[0], y + 0.5 * h * k2[1], vx + 0.5 * h * k2[2], vy + 0.5 * h * k2[3])
        k4 = f(x + h * k3[0], y + h * k3[1], vx + h * k3[2], vy + h * k3[3])
        self.x = x + h / 6.0 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        self.y = y + h / 6.0 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        self.vx = vx + h / 6.0 * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2])
        self.vy = vy + h / 6.0 * (k1[3] + 2 * k2[3] + 2 * k3[3] + k4[3])

    # ---- 供动画使用的三维几何（与真实装置的约束一致）
    def geometry(self):
        """返回 {'A1','A2','K','P'} 的三维坐标，z 向下为正（与报告图一致）。"""
        p = self.p
        d = derived(p)
        h = d["h"]
        # 结点：面内被锁定(x=0)，面外约为摆球的 h/(L+h)（系结式）
        share = 0.0 if self.p.mode == "tripod" else d["a_share"]
        Ky = self.y * share
        Kz = h
        Pz = h + p.L
        return dict(A1=(-p.R, 0.0, 0.0), A2=(p.R, 0.0, 0.0),
                    K=(0.0, Ky, Kz), P=(self.x, self.y, Pz),
                    P_rigid=(self.x, self.y, h + p.L))

    def push_trace(self, maxlen=60000):
        self.trace.append((self.x, self.y))
        if len(self.trace) > maxlen:
            del self.trace[:len(self.trace) - maxlen]

    def energies(self):
        p = self.p
        d = derived(p)
        U = 0.5 * p.m * d["w_in"] ** 2 * self.x ** 2 + 0.5 * p.m * d["w_out"] ** 2 * self.y ** 2
        T = 0.5 * p.m * (self.vx ** 2 + self.vy ** 2)
        return T, U


# ---------------------------------------------------------------- 二维轨迹图
def make_figure(sim: YYSim, path: str, title: str | None = None):
    """把同步的二维轨迹画成 PNG（matplotlib 可用时用它，否则退回 PIL 手绘）。

    图内标签一律用英文：matplotlib 自带字体不含中文字形，用中文会变成方框。
    界面（tkinter）里用中文没有这个问题。
    """
    p = sim.p
    d = derived(p)
    tr = sim.trace
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6.0, 6.0), dpi=110)
        if len(tr) > 1:
            xs = [q[0] * 1e3 for q in tr]
            ys = [q[1] * 1e3 for q in tr]
            ax.plot(xs, ys, lw=0.9, color="#c0392b", alpha=0.9)
        lim = max(p.A * 1.35, 0.012) * 1e3
        ax.plot([sim.x * 1e3], [sim.y * 1e3], "o", ms=7, color="#1f6fb2")
        ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
        ax.set_aspect("equal")
        ax.axhline(0, color="#888", lw=0.6); ax.axvline(0, color="#888", lw=0.6)
        ax.set_xlabel("in-plane displacement x (mm)")
        ax.set_ylabel("out-of-plane displacement y (mm)")
        ax.set_title(title or "Trajectory (top view)   f_r = %.4f   T_beat = %.2f s"
                     % (d["f_r_A"], d["T_beat"]), fontsize=10)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return True
    except Exception:
        from PIL import Image, ImageDraw
        W = 600
        img = Image.new("RGB", (W, W), "white")
        dr = ImageDraw.Draw(img)
        lim = max(p.A * 1.35, 0.012)
        cx = cy = W // 2
        sc = (W * 0.42) / lim
        dr.line([(0, cy), (W, cy)], fill=(180, 180, 180))
        dr.line([(cx, 0), (cx, W)], fill=(180, 180, 180))
        for i in range(1, len(tr)):
            x0, y0 = tr[i - 1]; x1, y1 = tr[i]
            dr.line([(cx + x0 * sc, cy - y0 * sc), (cx + x1 * sc, cy - y1 * sc)],
                    fill=(192, 57, 43), width=1)
        r = 6
        px, py = cx + sim.x * sc, cy - sim.y * sc
        dr.ellipse([px - r, py - r, px + r, py + r], fill=(31, 111, 178))
        img.save(path)
        return True


# ---------------------------------------------------------------- 自检
def selftest(verbose: bool = True) -> int:
    ok = True
    lines = []

    # 1) 参考几何的解析值与项目一致
    d = derived(Params())
    lines.append("== 参考几何 (l=0.250, R=0.060, L=0.300, mK=0.2 g) ==")
    lines.append("  h        = %.6f m" % d["h"])
    lines.append("  f_in     = %.6f Hz   (期望 0.909332)" % d["f_in"])
    lines.append("  f_out    = %.6f Hz   (μ=0 期望 0.676093)" % d["f_out"])
    lines.append("  f_r      = %.6f      (μ=0 期望 1.344982)" % d["f_r"])
    lines.append("  T_beat   = %.4f s   (线性值)" % d["T_beat_lin"])
    lines.append("  x_slack  = %.4f m" % d["x_slack"])
    for key, ref, tol in (("f_in", 0.909332, 1e-6), ("x_slack", 0.074168, 1e-5)):
        if abs(d[key] - ref) > tol:
            ok = False
            lines.append("  !! %s = %.8f 与参考 %.8f 不一致" % (key, d[key], ref))
    # 默认结点质量 0.2 g (μ=0.002) 会把 f_r 下拉约 2.5e-4，这是物理效应而非错误
    if abs(d["f_r"] - 1.344982) > 5e-4:
        ok = False
        lines.append("  !! f_r 与无质量结点值差得太多（检查 mK 默认值）")

    # 2) 三态
    lines.append("")
    lines.append("== 三态对照 ==")
    for mode, ref in (("tied", 1.34498), ("sliding", 1.01357), ("tripod", 1.00000)):
        dd = derived(Params(mode=mode, mK=0.0 if mode == "tied" else Params().mK))
        lines.append("  %-8s f_r = %.5f   T_beat = %s" %
                     (mode, dd["f_r"], "%.3f s" % dd["T_beat"] if math.isfinite(dd["T_beat"]) else "无限"))
        if mode == "tripod" and abs(dd["f_r"] - 1.0) > 1e-9:
            ok = False; lines.append("  !! 三脚架态必须严格简并")
        if mode == "sliding" and abs(dd["f_r"] - 1.01357) > 2e-3:
            ok = False; lines.append("  !! 滑环态 f_r 偏离参考值")
        if mode == "tied" and abs(dd["f_r"] - ref) > 2e-5:
            ok = False; lines.append("  !! 系结态（无质量结点）f_r 偏离参考值")

    # 3) 结点质量：f_in 严格不变、f_out 升高
    lines.append("")
    lines.append("== 结点质量 μ 的效应 ==")
    f0 = derived(Params(mK=0.0))
    f1 = derived(Params(mK=0.001))
    lines.append("  μ=0     f_in=%.6f  f_out=%.6f  f_r=%.6f" % (f0["f_in"], f0["f_out"], f0["f_r"]))
    lines.append("  μ=0.01  f_in=%.6f  f_out=%.6f  f_r=%.6f" % (f1["f_in"], f1["f_out"], f1["f_r"]))
    if abs(f0["f_in"] - f1["f_in"]) > 1e-12:
        ok = False; lines.append("  !! f_in 必须与 μ 无关")
    if not (f1["f_out"] > f0["f_out"]):
        ok = False; lines.append("  !! f_out 必须随 μ 升高")
    if abs(f1["f_r"] - 1.343331) > 3e-4:
        ok = False
        lines.append("  !! μ=0.01 时 f_r 应为 1.343331，实得 %.6f" % f1["f_r"])

    # 4) 时间步进：能量应近似守恒（无阻尼），频率应复现解析值
    lines.append("")
    lines.append("== 数值积分自检 ==")
    p = Params(damping=0.0, A=0.005, psi_deg=0.0)
    sim = YYSim(p=p)
    E0 = sum(sim.energies())
    dt = 2.0e-3
    n = int(60.0 / dt)
    crossings = []
    prev = sim.x
    for i in range(n):
        sim.step(dt)
        if prev < 0.0 <= sim.x:
            crossings.append(sim.t)
        prev = sim.x
    if len(crossings) > 5:
        per = (crossings[-1] - crossings[0]) / (len(crossings) - 1)
        f_meas = 1.0 / per
        f_pred = derived(p)["f_in"]
        rel = abs(f_meas - f_pred) / f_pred
        lines.append("  小振幅单模释放：测得 f = %.6f Hz，解析 %.6f Hz，相对差 %.2e"
                     % (f_meas, f_pred, rel))
        if rel > 2e-4:
            ok = False; lines.append("  !! 积分频率与解析值不符")
    E1 = sum(sim.energies())
    drift = abs(E1 - E0) / max(E0, 1e-12)
    lines.append("  60 s 无阻尼能量漂移 = %.2e" % drift)
    if drift > 1e-3:
        ok = False; lines.append("  !! 能量漂移过大")

    # 5) 振幅依赖：大振幅频率应下降，且降幅符合椭圆积分律
    sim2 = YYSim(Params(damping=0.0, A=0.05, psi_deg=0.0))
    cr = []
    prev = sim2.x
    for i in range(int(60.0 / dt)):
        sim2.step(dt)
        if prev < 0.0 <= sim2.x:
            cr.append(sim2.t)
        prev = sim2.x
    if len(cr) > 5:
        f_big = 1.0 / ((cr[-1] - cr[0]) / (len(cr) - 1))
        f_small_pred = derived(Params())["f_in"]
        A, l = 0.05, 0.300
        shift_pred = -(A ** 2 / (16 * l ** 2) + 11 * A ** 4 / (3072 * l ** 4))
        f_pred = f_small_pred * (1 + shift_pred)
        lines.append("  A=50 mm：测得 %.6f Hz，椭圆积分律 %.6f Hz，相对差 %.2e"
                     % (f_big, f_pred, abs(f_big - f_pred) / f_pred))
        if abs(f_big - f_pred) / f_pred > 5e-4:
            ok = False; lines.append("  !! 振幅频移与椭圆积分律不符")

    # 6) T_beat 与完整动力学标定值比较
    lines.append("")
    lines.append("== T_beat 的振幅依赖（应与全动力学标定一致）==")
    ok_tb = True
    for A, target in ((0.005, 4.29374), (0.020, 4.291994), (0.040, 4.305508), (0.060, 4.327382)):
        d = derived(Params(damping=0.0, A=A))
        rel = abs(d["T_beat"] - target) / target
        flag = "OK" if rel < 2e-3 else "偏差 %.1e" % rel
        lines.append("  A=%5.1f mm  T_beat=%.5f s  （完整动力学 %.5f s，%s）"
                     % (A * 1e3, d["T_beat"], target, flag))
        if rel >= 2e-3:
            ok_tb = False
    if not ok_tb:
        ok = False
        lines.append("  !! T_beat 与完整动力学标定不符")

    text = "\n".join(lines)
    if verbose:
        print(text)
        print()
        print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def export_png(path: str, seconds: float = 30.0, p: Params | None = None):
    """无界面地跑一段时间并导出二维轨迹图。"""
    p = p or Params(A=0.020, psi_deg=45.0, damping=0.010)
    sim = YYSim(p=p)
    dt = 2.0e-3
    for _ in range(int(seconds / dt)):
        sim.step(dt)
        sim.push_trace()
    make_figure(sim, path)
    d = derived(p)
    print("导出 %s（%.0f s 轨迹，f_r=%.5f，T_beat=%.3f s）" % (path, seconds, d["f_r"], d["T_beat"]))
    return path


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--selftest" in args:
        raise SystemExit(selftest())
    if "--export" in args:
        i = args.index("--export")
        out = args[i + 1] if len(args) > i + 1 else "lissajous.png"
        export_png(out)
        raise SystemExit(0)
    print(__doc__)
    print("用法： --selftest  或  --export 输出.png")
