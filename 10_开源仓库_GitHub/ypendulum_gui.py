r"""
Y 形摆交互式模拟器（图形界面）

用法：
    python ypendulum_gui.py                # 启动
    python ypendulum_gui.py --smoke        # 无显示自检：建窗、改参数、跑若干帧后退出
                                           # （用于在无人值守时确认程序真的能起来）

界面构成
    ┌───────────────┬──────────────────────────────┐
    │  参数滑条      │   侧视动画（真实物理动画）      │
    │  · 上臂长 l    │   A₁ ──── A₂                 │
    │  · 孔距 R      │     \    /    ← 两根上臂       │
    │  · 下臂长 L    │      \  /                    │
    │  · 结点质量    │       K       ← 结点          │
    │  · 释放振幅    │       |                      │
    │  · 释放方位    │       P       ← 摆球（带轨迹）  │
    │  · 阻尼        ├──────────────────────────────┤
    │  · 时间倍率    │   下视轨迹（与动画同步的 2D 图）│
    │  三态切换      │   实时绘出 Lissajous 图案      │
    │  播放/重置     │                              │
    └───────────────┴──────────────────────────────┘
    右上角实时显示 f_in、f_out、f_r、T_beat 与松弛警告。
"""
from __future__ import annotations

import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from ypendulum_sim import Params, YYSim, derived, make_figure   # noqa: E402
from i18n import (Translator, LANGS, LANG_NAME, check_i18n,   # noqa: E402
                  detect_default_lang)

FPS = 60
DT = 1.0 / FPS

# ---------------------------------------------------------------- 颜色
C_BG = "#f7f9fc"
C_PANEL = "#ffffff"
C_TEXT = "#142a4c"
C_DIM = "#5a6270"
C_A1 = "#1f6fb2"
C_ARM = "#2f3b4a"
C_BOB = "#c0392b"
C_KNOT = "#e0a020"
C_CEIL = "#8a94a2"
C_TRACE = "#c0392b"
C_TRACE2 = "#1f6fb2"
C_ACCENT = "#c0392b"

SLIDERS = [
    # key, 标签, 范围, 初值, 单位, 格式
    ("l", "上臂长 l", 0.100, 0.800, 0.250, "m", "%.3f"),
    ("R", "孔距半值 R", 0.005, 0.300, 0.060, "m", "%.3f"),
    ("L", "下臂长 L", 0.050, 0.900, 0.300, "m", "%.3f"),
    ("mK", "结点质量 m_K", 0.0, 5.0, 0.2, "g", "%.1f"),
    ("A", "释放振幅 A", 0.002, 0.150, 0.020, "m", "%.3f"),
    ("psi", "释放方位 ψ₀", 0.0, 90.0, 45.0, "°", "%.0f"),
    ("damping", "阻尼 b", 0.0, 0.200, 0.020, "1/s", "%.3f"),
    ("rate", "时间倍率", 0.1, 3.0, 1.0, "×", "%.2f"),
]


class App:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk
        self.tk = tk
        self.ttk = ttk
        self.root = root
        # 语言：默认按系统区域猜（中文系统给中文，其余给英文），界面里随时可切，
        # 也可以用 --lang zh / --lang en 强制指定。所有界面文案走 i18n.Translator。
        _lang0 = detect_default_lang()
        self.tr = Translator(_lang0)
        self.lang = tk.StringVar(value=_lang0)
        self._texts = {}          # 控件 -> i18n key，供切换语言时批量刷新
        self._computed = []       # 需要重算的复合文案（滑条数值、读数、缩放标签…）
        root.title(self.tr("app.title"))
        root.configure(bg=C_BG)
        root.geometry("1400x880")
        root.minsize(1150, 760)

        self.params = Params()
        self.sim = YYSim(p=self.params.copy())
        self.running = True
        self.show_trace = True
        self.max_trace_pts = 40000
        self.frame = 0
        # 3D 视角状态（方位角 / 仰角；缩放用 zoom3d，与左侧"显示缩放"相乘）
        self.az, self.el, self.zoom3d = 38.0, 24.0, 1.0
        self._zoom_auto = 1.0
        self._cur_xr = 0.02
        self._drag = None

        self._build_left(ttk)
        self._build_right(tk)
        self._apply_language()

        self._apply_params(reset=True)
        self.last = time.perf_counter()
        self._tick()

    # ------------------------------------------------------------ 语言
    def _t(self, key):
        return self.tr(key)

    def _bind_text(self, widget, key):
        """登记一个"文字来自 i18n 表"的控件。"""
        self._texts[widget] = key
        return widget

    def _on_lang_change(self):
        self.tr.set(self.lang.get())
        self._apply_language()
        self._apply_params(reset=False)

    def _apply_language(self):
        """把当前语言应用到所有已登记的控件、标签页、以及需要重算的复合文案。"""
        tr = self.tr
        for widget, key in self._texts.items():
            try:
                widget.config(text=tr(key))
            except Exception:
                pass
        # 标签页标题
        try:
            self.nb.tab(0, text=tr("tab.main"))
            self.nb.tab(1, text=tr("tab.3d"))
        except Exception:
            pass
        # 字体（中文用 Microsoft YaHei，英文用 Segoe UI）
        for widget in list(self._texts.keys()) + [self.info, self.warn, self.zoom_label]:
            try:
                widget.config(font=tr.ui(9))
            except Exception:
                pass
        try:
            self.btn_play.config(font=tr.ui(9))
        except Exception:
            pass
        self.root.title(tr("app.title"))
        # 复合文案（数值 + 单位、读数、缩放、画布）
        self._refresh_computed()

    def _refresh_computed(self):
        """刷新随语言变化的"数值型"文案。"""
        for key, (scale, fmt, unit) in self.scales.items():
            try:
                self.vars[key].config(text="%s %s" % (fmt % float(scale.get()), unit))
            except Exception:
                pass
        self._update_info()
        self._auto_zoom_quiet()
        self._update_play_button()
        # 关键：切语言时要把**所有**画布都重画一遍，不能只画当前可见的标签页。
        # 否则用户在 3D 标签页时切语言，回头切到主标签页会看到上一个语言的旧文字。
        self._draw_side()
        self._draw_top()
        self._draw_env()
        self._draw_3d()

    def _update_play_button(self):
        self.btn_play.config(text=self.tr("btn.play") if not self.running else self.tr("btn.pause"))

    # ------------------------------------------------------------ 左侧控制面板
    SLIDER_KEYS = {                 # 滑条 key -> i18n key
        "l": "sl.l", "R": "sl.R", "L": "sl.L", "mK": "sl.mK",
        "A": "sl.A", "psi": "sl.psi", "damping": "sl.damping", "rate": "sl.rate",
    }

    def _build_left(self, ttk):
        tk = self.tk
        tr = self.tr
        left = tk.Frame(self.root, bg=C_BG, width=310)
        left.pack(side="left", fill="y", padx=(10, 4), pady=10)
        left.pack_propagate(False)
        self.left = left

        # 语言选择（放在最上面，方便一进来就切）
        lang_row = tk.Frame(left, bg=C_BG)
        lang_row.pack(fill="x", pady=(0, 4))
        self._bind_text(tk.Label(lang_row, bg=C_BG, fg=C_TEXT, font=tr.ui(9)),
                        "panel.language").pack(side="left")
        for code in LANGS:
            self._bind_text(
                tk.Radiobutton(lang_row, value=code, variable=self.lang,
                               command=self._on_lang_change, bg=C_BG, fg=C_TEXT,
                               selectcolor=C_PANEL, activebackground=C_BG,
                               font=tr.ui(9)),
                "lang." + code).pack(side="left", padx=2)

        self._bind_text(tk.Label(left, font=tr.ui(14, True), bg=C_BG, fg=C_TEXT),
                        "panel.params").pack(anchor="w", pady=(2, 6))

        self.vars = {}
        self.scales = {}
        for key, label, lo, hi, init, unit, fmt in SLIDERS:
            box = tk.Frame(left, bg=C_BG)
            box.pack(fill="x", pady=(2, 0))
            name = tk.Label(box, bg=C_BG, fg=C_TEXT, font=tr.ui(10))
            if key in self.SLIDER_KEYS:
                self._bind_text(name, self.SLIDER_KEYS[key])
            else:
                name.config(text=label)
            name.pack(side="left")
            val = tk.Label(box, text=("%s %s" % (fmt % init, unit)), bg=C_BG, fg=C_ACCENT,
                           font=tr.mono(10, True))
            val.pack(side="right")
            n = 600 if (hi - lo) > 1 else 200
            s = tk.Scale(left, from_=lo, to=hi, resolution=(hi - lo) / n,
                         orient="horizontal", showvalue=False,
                         bg=C_BG, highlightthickness=0, bd=0, length=280,
                         command=lambda v, k=key: self._on_slider(k, v))
            s.set(init)
            s.pack(fill="x")
            self.vars[key] = val
            self.scales[key] = (s, fmt, unit)

        # 显示缩放
        self._bind_text(tk.Label(left, bg=C_BG, fg=C_TEXT, font=tr.ui(10)),
                        "panel.zoom").pack(anchor="w", pady=(10, 2))
        self.zoom_mode = tk.StringVar(value="device")
        zrow = tk.Frame(left, bg=C_BG)
        zrow.pack(fill="x")
        for val, key in (("trace", "zoom.trace"), ("device", "zoom.device"),
                         ("manual", "zoom.manual")):
            self._bind_text(
                tk.Radiobutton(zrow, value=val, variable=self.zoom_mode,
                               command=self._on_zoom_mode, bg=C_BG, fg=C_TEXT,
                               selectcolor=C_PANEL, activebackground=C_BG,
                               font=tr.ui(9)), key).pack(side="left")
        zrow2 = tk.Frame(left, bg=C_BG)
        zrow2.pack(fill="x", pady=(2, 0))
        self.zoom_var = tk.DoubleVar(value=1.0)
        self.zoom_scale = tk.Scale(zrow2, from_=0.25, to=4.0, resolution=0.01,
                                   orient="horizontal", showvalue=False,
                                   variable=self.zoom_var, bg=C_BG,
                                   highlightthickness=0, bd=0, length=180,
                                   command=lambda v: self._on_zoom_slider(v))
        self.zoom_scale.pack(side="left")
        tk.Button(zrow2, text="\u2212", width=2,
                  command=lambda: self._zoom_step(1 / 1.25)).pack(side="left", padx=1)
        tk.Button(zrow2, text="+", width=2,
                  command=lambda: self._zoom_step(1.25)).pack(side="left")
        self.zoom_label = tk.Label(left, text="1.00x", bg=C_BG, fg=C_ACCENT,
                                   font=tr.mono(10, True))
        self.zoom_label.pack(anchor="w")
        tk.Label(left, bg=C_BG, fg=C_DIM, font=tr.ui(8), wraplength=280,
                 justify="left", text=tr("zoom.hint")).pack(anchor="w")

        # 三态切换
        self._bind_text(tk.Label(left, bg=C_BG, fg=C_TEXT, font=tr.ui(10)),
                        "panel.mode").pack(anchor="w", pady=(10, 2))
        self.mode = tk.StringVar(value="tied")
        for val, key in (("tied", "mode.tied"), ("sliding", "mode.sliding"),
                         ("tripod", "mode.tripod")):
            self._bind_text(
                tk.Radiobutton(left, value=val, variable=self.mode,
                               command=lambda: self._apply_params(reset=True),
                               bg=C_BG, fg=C_TEXT, selectcolor=C_PANEL,
                               activebackground=C_BG, font=tr.ui(9),
                               wraplength=270, justify="left"), key).pack(anchor="w")

        # 按钮
        btns = tk.Frame(left, bg=C_BG)
        btns.pack(fill="x", pady=(12, 4))
        self.btn_play = tk.Button(btns, text=tr("btn.pause"), width=9,
                                  font=tr.ui(9), command=self._toggle)
        self.btn_play.pack(side="left")
        self.btn_release = self._bind_text(
            tk.Button(btns, width=11, font=tr.ui(9),
                      command=lambda: self._apply_params(reset=True)), "btn.release")
        self.btn_release.pack(side="left", padx=4)
        self._bind_text(tk.Button(btns, width=9, font=tr.ui(9),
                                  command=self._clear_trace),
                        "btn.clear").pack(side="left")

        btns2 = tk.Frame(left, bg=C_BG)
        btns2.pack(fill="x", pady=(2, 4))
        self._bind_text(tk.Button(btns2, width=14, font=tr.ui(9),
                                  command=self._save_png), "btn.png").pack(side="left")
        self.show_var = tk.BooleanVar(value=True)
        self._bind_text(
            tk.Checkbutton(btns2, variable=self.show_var,
                           command=lambda: setattr(self, "show_trace", self.show_var.get()),
                           bg=C_BG, fg=C_TEXT, selectcolor=C_PANEL,
                           activebackground=C_BG, font=tr.ui(9)),
            "btn.show_trace").pack(side="left", padx=4)

        # 预设
        self._bind_text(tk.Label(left, bg=C_BG, fg=C_TEXT, font=tr.ui(10)),
                        "panel.presets").pack(anchor="w", pady=(8, 2))
        pre = tk.Frame(left, bg=C_BG)
        pre.pack(fill="x")
        for key, fn in (("ps.ref", self._preset_ref),
                        ("ps.degenerate", self._preset_degenerate),
                        ("ps.wide", self._preset_wide),
                        ("ps.short", self._preset_short)):
            w = 7 if key == "ps.degenerate" else 6
            self._bind_text(tk.Button(pre, width=w, font=tr.ui(8), command=fn),
                            key).pack(side="left", padx=1)

        # 读数
        self.info = tk.Label(left, text="", justify="left", anchor="nw",
                             bg=C_PANEL, fg=C_TEXT, font=tr.mono(10),
                             relief="solid", bd=1, padx=8, pady=6)
        self.info.pack(fill="x", pady=(10, 0))

        self.warn = tk.Label(left, text="", justify="left", anchor="nw",
                             bg=C_BG, fg=C_BOB, font=tr.ui(9), wraplength=280)
        self.warn.pack(fill="x", pady=(6, 0))

    # ------------------------------------------------------------ 右侧画布
    def _build_right(self, tk):
        right = tk.Frame(self.root, bg=C_BG)
        right.pack(side="left", fill="both", expand=True, padx=(4, 10), pady=10)

        nb = self.ttk.Notebook(right)
        nb.pack(fill="both", expand=True)
        self.nb = nb

        # ---------------- 标签 1：主视图（侧视动画 + 二维轨迹，同一屏）
        # 用 grid 的 weight 按比例分配：左列（轨迹 + 包络）宽度是右列（侧视）的 2.6 倍，
        # 行方向 2:1。窗口缩放时三块画布一起按比例变化。
        page1 = tk.Frame(nb, bg=C_BG)
        nb.add(page1, text="  ① 动画 + 二维轨迹  ")
        page1.columnconfigure(0, weight=34, minsize=380)
        page1.columnconfigure(1, weight=11, minsize=180)
        page1.rowconfigure(0, weight=1)
        page1.rowconfigure(1, weight=1)

        self.cv_top = tk.Canvas(page1, bg=C_PANEL, highlightthickness=1,
                                highlightbackground="#ccd4de")
        self.cv_top.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 4))
        self.cv_env = tk.Canvas(page1, bg=C_PANEL, highlightthickness=1,
                                highlightbackground="#ccd4de")
        self.cv_env.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(4, 0))
        self.cv_side = tk.Canvas(page1, bg=C_PANEL, highlightthickness=1,
                                 highlightbackground="#ccd4de")
        self.cv_side.grid(row=0, column=1, rowspan=2, sticky="nsew", pady=0)

        # 画布内的标题（贴在画布左上角，比单独的 Label 省纵向空间）
        self._label_top = "② 下视：与动画同步的二维轨迹（Lissajous 图案）"
        self._label_side = "① 侧视：真实物理动画"

        # ---------------- 标签 2：3D 自由视角
        page2 = tk.Frame(nb, bg=C_BG)
        nb.add(page2, text=self.tr("tab.3d"))
        bar = tk.Frame(page2, bg=C_BG)
        bar.pack(fill="x", pady=(4, 2))
        self._bind_text(tk.Label(bar, bg=C_BG, fg=C_TEXT, font=self.tr.ui(10, True)),
                        "d3.hint").pack(side="left")
        self._bind_text(tk.Button(bar, font=self.tr.ui(9), command=self._reset_view),
                        "btn.reset_view").pack(side="right", padx=2)
        self.auto_rot = tk.BooleanVar(value=False)
        self._bind_text(
            tk.Checkbutton(bar, variable=self.auto_rot, bg=C_BG, fg=C_TEXT,
                           selectcolor=C_PANEL, activebackground=C_BG,
                           font=self.tr.ui(9)), "btn.auto_rotate").pack(side="right", padx=6)
        self.show_3d_trace = tk.BooleanVar(value=True)
        self._bind_text(
            tk.Checkbutton(bar, variable=self.show_3d_trace, bg=C_BG, fg=C_TEXT,
                           selectcolor=C_PANEL, activebackground=C_BG,
                           font=self.tr.ui(9)), "btn.show_3d_trace").pack(side="right", padx=6)
        self.cv_3d = tk.Canvas(page2, bg=C_PANEL, highlightthickness=1,
                               highlightbackground="#ccd4de", cursor="fleur")
        self.cv_3d.pack(fill="both", expand=True)
        self._bind_text(
            tk.Label(page2, bg=C_BG, fg=C_DIM, font=self.tr.ui(9), wraplength=1100,
                     justify="left"), "d3.note").pack(anchor="w", pady=(2, 0))

        for cv in (self.cv_side, self.cv_top, self.cv_env, self.cv_3d):
            cv.bind("<Configure>", lambda e: self._redraw_all())
        self.cv_3d.bind("<ButtonPress-1>", self._orbit_start)
        self.cv_3d.bind("<B1-Motion>", self._orbit_move)
        self.cv_3d.bind("<ButtonRelease-1>", self._orbit_end)
        self.cv_3d.bind("<Double-Button-1>", lambda e: self._reset_view())
        self.cv_3d.bind("<MouseWheel>", self._orbit_zoom)
        self.cv_3d.bind("<Button-4>", lambda e: self._orbit_zoom(e, 120))
        self.cv_3d.bind("<Button-5>", lambda e: self._orbit_zoom(e, -120))
        nb.bind("<<NotebookTabChanged>>", lambda e: self._redraw_all())

    # ------------------------------------------------------------ 3D 视角控制
    def _reset_view(self):
        self.az, self.el, self.zoom3d = 38.0, 24.0, 1.0
        self._redraw_all()

    def _orbit_start(self, ev):
        self._drag = (ev.x, ev.y)

    def _orbit_move(self, ev):
        if not getattr(self, "_drag", None):
            return
        x0, y0 = self._drag
        self.az += (ev.x - x0) * 0.45
        # 允许越过天顶，方便直接俯视看图案
        self.el = max(-88.0, min(88.0, self.el + (ev.y - y0) * 0.35))
        self._drag = (ev.x, ev.y)
        self._draw_3d()

    def _orbit_end(self, ev):
        self._drag = None

    def _orbit_zoom(self, ev, delta=None):
        d = delta if delta is not None else (ev.delta if ev.delta else 0)
        self.zoom3d = max(0.2, min(8.0, getattr(self, "zoom3d", 1.0) * (1.15 if d > 0 else 1 / 1.15)))
        self._draw_3d()

    # ------------------------------------------------------------ 缩放控制
    def _zoom_value(self):
        """手动模式下的缩放倍率（自动模式下 1.0 = 各视图用各自的适配倍率）。"""
        if getattr(self, "zoom_mode", None) is not None and self.zoom_mode.get() != "manual":
            return 1.0
        try:
            return float(self.zoom_var.get())
        except Exception:
            return 1.0

    def _fit_factor(self, view):
        """"刚好把内容框进该视图"所需的换算系数（像素/米，含视图自身的边距）。

        侧视画布高而窄（约 452x832）、下视轨迹画布接近方形（约 600x412），
        两者的长宽比差得很远，所以必须分开算 —— 用一个共同数必然有一个视图被裁掉。

        这里**不设上限**：装置本身可能只有几厘米（例如 R=60 mm、L=0.9 m），
        需要几百倍的放大才能占满画布；人为限幅反而会把内容缩成一小团看不见。
        """
        xr, ztop, zbot = self._extent(self.zoom_mode.get())
        xr = max(xr, 1e-6)
        zspan = max(zbot - ztop, 1e-6)
        margin = 1.12
        if view == "side":
            W = max(self.cv_side.winfo_width(), 40)
            H = max(self.cv_side.winfo_height(), 40)
            return min(W * 0.46 / xr, (H - 74) * 0.96 / zspan) / margin
        W = max(self.cv_top.winfo_width(), 40)
        H = max(self.cv_top.winfo_height(), 40)
        return min(W, H) * 0.44 / xr / margin

    def _scale_for(self, view):
        """绘制时该用的换算系数（像素/米）。

        自动模式：用该视图自己的适配系数（保证内容完整可见，不会被裁）。
        手动模式：用"恰好放下装置"的基准系数乘滑条倍率 —— 滑条 1.0× 就是装置正好
        铺满视图，调大即放大细看。两者都按各自画布的长宽比算，互不牵连。
        """
        if self.zoom_mode.get() != "manual":
            xr, ztop, zbot = self._extent(self.zoom_mode.get())
        else:
            xr, ztop, zbot = self._extent("device")
        xr = max(xr, 1e-6)
        zspan = max(zbot - ztop, 1e-6)
        margin = 1.12
        if view == "side":
            W = max(self.cv_side.winfo_width(), 40)
            H = max(self.cv_side.winfo_height(), 40)
            base = min(W * 0.46 / xr, (H - 74) * 0.96 / zspan) / margin
        else:
            W = max(self.cv_top.winfo_width(), 40)
            H = max(self.cv_top.winfo_height(), 40)
            base = min(W, H) * 0.44 / xr / margin
        if self.zoom_mode.get() == "manual":
            return base * self._zoom_value()
        return base

    def _on_zoom_mode(self):
        self._update_auto_zoom()

    def _on_zoom_slider(self, v):
        # 只有在手动模式下，拖滑条才是"用户直接指定倍率"
        if self.zoom_mode.get() == "manual":
            self.zoom_label.config(text="%.2f x" % float(v))
            self._redraw_all()

    def _zoom_step(self, factor):
        if self.zoom_mode.get() != "manual":
            self.zoom_mode.set("manual")
        self.zoom_var.set(max(0.25, min(4.0, self._zoom_value() * factor)))
        self.zoom_label.config(text="%.2f x" % self._zoom_value())
        self._redraw_all()

    def _extent(self, which):
        """返回 (xr, ztop, zbot)：需要的水平半径与上下竖直范围（米，z 向下为正）。

        which="device"：整台装置（锚点 + 结点 + 下臂 + 摆球释放振幅）
        which="trace" ：装置的静态部分 UNION 迄今走过的轨迹 —— 保证图案不被裁掉

        轨迹可能有几万个点、而每帧要被问好几次，所以按"轨迹长度"做记忆化：
        长度没变就复用上次结果，避免每帧都去扫一遍列表。
        """
        p = self.params
        d = derived(p)
        ztop = 0.0                      # 天花板
        zbot = p.L + d["h"]             # 摆球静止位置
        xr = max(p.R, p.A)
        if which != "trace" or not self.sim.trace:
            return xr, ztop, zbot
        n = len(self.sim.trace)
        if getattr(self, "_ext_cache_n", None) == n:
            return max(xr, self._ext_cache_xr), ztop, zbot
        mx = 0.0
        for q in self.sim.trace:
            ax = abs(q[0]); ay = abs(q[1])
            if ax > mx:
                mx = ax
            if ay > mx:
                mx = ay
        self._ext_cache_n = n
        self._ext_cache_xr = mx
        return max(xr, mx), ztop, zbot

    def _update_auto_zoom(self):
        """切换自动/手动时调用：刷新读数并重绘。"""
        self._auto_zoom_quiet()
        self._redraw_all()

    # ------------------------------------------------------------ 交互
    def _on_slider(self, key, val):
        v = float(val)
        if key == "mK":
            self.params.mK = v / 1000.0
        elif key == "psi":
            self.params.psi_deg = v
        else:
            setattr(self.params, key, v)
        s, fmt, unit = self.scales[key]
        self.vars[key].config(text="%s %s" % (fmt % v, unit))
        # R 不能超过 l，否则几何不存在
        if key == "l" and self.params.R > 0.98 * self.params.l:
            self.params.R = 0.98 * self.params.l
            sc, _, _ = self.scales["R"]
            sc.set(self.params.R)
        if key == "R" and self.params.R > 0.98 * self.params.l:
            self.params.R = 0.98 * self.params.l
            sc, _, _ = self.scales["R"]
            sc.set(self.params.R)
        if key in ("A", "psi", "l", "R", "L", "mK", "damping", "rate"):
            self._apply_params(reset=(key in ("A", "psi")))

    def _preset_ref(self):
        self._set_params(dict(l=0.250, R=0.060, L=0.300, A=0.020, psi=45.0, damping=0.020))

    def _preset_degenerate(self):
        # h → 0：把孔距推到接近上臂长，两模趋于简并
        self._set_params(dict(l=0.250, R=0.244, L=0.300, A=0.020, psi=45.0, damping=0.010))

    def _preset_wide(self):
        self._set_params(dict(l=0.250, R=0.200, L=0.300, A=0.030, psi=45.0, damping=0.010))

    def _preset_short(self):
        self._set_params(dict(l=0.250, R=0.060, L=0.100, A=0.010, psi=45.0, damping=0.020))

    def _set_params(self, d):
        for k, v in d.items():
            if k in self.scales:
                s, fmt, unit = self.scales[k]
                if k == "mK":
                    s.set(v * 1000.0)
                else:
                    s.set(v)
        self._apply_params(reset=True)

    def _apply_params(self, reset=True):
        self.params.mode = self.mode.get()
        self.params.mK = float(self.scales["mK"][0].get()) / 1000.0
        self.params.A = float(self.scales["A"][0].get())
        self.params.psi_deg = float(self.scales["psi"][0].get())
        self.params.damping = float(self.scales["damping"][0].get())
        self.params.rate = float(self.scales["rate"][0].get())
        for k in ("l", "R", "L"):
            setattr(self.params, k, float(self.scales[k][0].get()))
        if reset:
            self.sim = YYSim(p=self.params.copy())
            self._ext_cache_n = None
        else:
            self.sim.p = self.params.copy()
        self._update_info()

    def _clear_trace(self):
        self.sim.trace = [(self.sim.x, self.sim.y)]
        self._ext_cache_n = None

    def _toggle(self):
        self.running = not self.running
        self._update_play_button()

    def _save_png(self):
        out = os.path.join(HERE, "lissajous_export.png")
        # 用当前轨迹直接画图
        import shutil
        tmp = YYSim(p=self.params.copy())
        tmp.trace = list(self.sim.trace)
        tmp.x, tmp.y = self.sim.x, self.sim.y
        make_figure(tmp, out)
        self.warn.config(text=self._t("warn.saved") % out, fg=C_DIM)

    # ------------------------------------------------------------ 主循环
    def _tick(self):
        now = time.perf_counter()
        wall = now - self.last
        self.last = now
        wall = min(wall, 0.05)                      # 卡顿时不要一次跳太多
        if self.running:
            sim_dt = DT * self.params.rate
            n = max(1, int(round(wall / DT)))
            for _ in range(n):
                self.sim.step(sim_dt)
                self.sim.push_trace(self.max_trace_pts)
            self._update_info()
        self._redraw_all()
        self.root.after(int(1000 / FPS), self._tick)

    # ------------------------------------------------------------ 读数
    def _update_info(self):
        d = derived(self.params)
        self.warn.config(text="")
        txt = (
            "h        = %8.4f m\n"
            "f_in     = %8.5f Hz\n"
            "f_out    = %8.5f Hz\n"
            "f_r      = %8.5f\n"
            "T_beat   = %8.3f s\n"
            "x_slack  = %8.4f m\n"
            "t        = %8.2f s\n"
            "|x|,|y|  = %5.1f, %5.1f mm"
            % (d["h"], d["f_in_A"], d["f_out_A"], d["f_r_A"],
               d["T_beat"] if math.isfinite(d["T_beat"]) else float("inf"),
               d["x_slack"], self.sim.t,
               abs(self.sim.x) * 1e3, abs(self.sim.y) * 1e3)
        )
        self.info.config(text=txt)
        msgs = list(self.sim.warnings)
        if self.params.A > d["x_slack"]:
            msgs.append(self._t("warn.slack"))
        if self.params.mode == "tripod":
            msgs.append(self._t("warn.tripod"))
        if self.params.mode == "sliding":
            msgs.append(self._t("warn.sliding"))
        if d["T_beat"] > 60:
            msgs.append(self._t("warn.longbeat") % d["T_beat"])
        if msgs:
            self.warn.config(text="\n".join(msgs), fg=C_BOB)

    # ------------------------------------------------------------ 绘制
    def _redraw_all(self):
        # 自动模式下每帧都要重算倍率（参数或轨迹一变，需要的倍率就变），
        # 但如果算出来的值和当前一致，_auto_zoom_quiet 不会递归调用本函数。
        # _auto_zoom_quiet 同时把"当前框住的范围"写进 self._cur_xr，
        # 供 _draw_side / _draw_top 使用，保证两者算的是同一个范围。
        self._auto_zoom_quiet()
        # 只重画当前可见的标签页 —— 每帧画所有画布会白白吃掉 CPU
        try:
            tab = self.nb.index(self.nb.select())
        except Exception:
            tab = 0
        if tab == 0:
            # 侧视动画和二维轨迹同屏，必须一起画
            self._draw_side()
            self._draw_top()
            self._draw_env()
        else:
            self._draw_3d()

    def _auto_zoom_quiet(self):
        """记录当前框住的范围，并刷新倍率读数（各视图的实际倍率在绘制时算）。"""
        mode = self.zoom_mode.get()
        xr, ztop, zbot = self._extent(mode)
        self._cur_xr = xr                 # _draw_side / _draw_top 用它决定量程
        if mode == "manual":
            self.zoom_label.config(text="%.2f x" % self._zoom_value() + self._t("zoom.manual_suffix"))
            return
        ks = self._fit_factor("side")
        kt = self._fit_factor("top")
        self._zoom_auto = min(ks, kt)
        self.zoom_label.config(
            text=self._t("zoom.readout")
            % (ks, kt, self._t("zoom.auto_suffix_trace") if mode == "trace"
               else self._t("zoom.auto_suffix_device")))

    # ------------------------------------------------------------ 3D 视图
    @staticmethod
    def _view(p, az_deg, el_deg):
        """世界坐标 -> 相机坐标。世界系 z 轴向上，摆球静止时在 z = -(L+h)。"""
        a = math.radians(az_deg); e = math.radians(el_deg)
        ca, sa, ce, se = math.cos(a), math.sin(a), math.cos(e), math.sin(e)
        right = (-sa, ca, 0.0)
        up = (-ce * ca, -ce * sa, se)
        fwd = (se * ca, se * sa, ce)
        dx, dy, dz = p
        return (dx * right[0] + dy * right[1] + dz * right[2],
                dx * up[0] + dy * up[1] + dz * up[2],
                -(dx * fwd[0] + dy * fwd[1] + dz * fwd[2]))

    @staticmethod
    def _lighten(hexcol, k):
        """k<1 变暗，k>1 变亮 —— 用来做深度提示。"""
        k = max(0.25, min(1.6, k))
        h = hexcol.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        f = lambda v: max(0, min(255, int(v * k)))
        return "#%02x%02x%02x" % (f(r), f(g), f(b))

    def _draw_3d(self):
        cv = self.cv_3d
        cv.delete("all")
        W = cv.winfo_width(); H = cv.winfo_height()
        if W < 60 or H < 60:
            return
        p = self.params
        d = derived(p)
        g = self.sim.geometry()          # z 向下为正
        az = getattr(self, "az", 38.0)
        el = getattr(self, "el", 16.0)
        # 左侧"显示缩放"作为基础倍率，滚轮在此之上再叠一个系数（只影响 3D 视图）
        zoom = self._zoom_value() * getattr(self, "zoom3d", 1.0)
        if self.auto_rot.get():
            az += 0.5
            self.az = az

        Ltot = p.L + d["h"]
        # 世界坐标：z 向上，天花板在 0，摆球静止时 z = -Ltot
        def w3(v):
            return (v[0], v[1], -v[2])

        A1 = w3(g["A1"]); A2 = w3(g["A2"]); K = w3(g["K"]); P = w3(g["P"])
        cx3, cy3, cz3 = 0.0, 0.0, -Ltot / 2.0
        # 相机到场景中心的距离（世界单位）。透视深度必须写成 d_cam + q[2]，
        # 其中 q[2] 也是世界单位 —— 早先把像素焦距和世界深度相加，量纲错了。
        # d_cam = 2.6·Ltot 让整个装置约占画面高度的 77%，再远就显得太小。
        d_cam = 2.6 * Ltot
        f_px = min(W, H) / (0.85 * Ltot) * zoom
        cxs, cys = W / 2, H / 2

        def proj(pt):
            q = self._view((pt[0] - cx3, pt[1] - cy3, pt[2] - cz3), az, el)
            zc = max(d_cam + q[2], 0.02 * Ltot)
            return cxs + f_px * q[0] / zc, cys - f_px * q[1] / zc, zc

        # --- 画一条 3D 线（在屏幕上用两点即可，透视是线性投影）
        def seg(pt1, pt2, col, w=2, dash=None):
            x1, y1, _ = proj(pt1); x2, y2, _ = proj(pt2)
            cv.create_line(x1, y1, x2, y2, fill=col, width=w, dash=dash)

        def disc(pt, r_world, col, outline=""):
            x, y, zc = proj(pt)
            r = max(2.0, r_world * f_px / zc)
            cv.create_oval(x - r, y - r, x + r, y + r, fill=col, outline=outline)

        # --- 天花板格网（画在锚点之上，避免挡住摆线）
        gy = max(p.R * 2.1, 0.16)
        for i in range(-3, 4):
            t = i / 3.0 * gy
            seg((t, -gy, 0.014), (t, gy, 0.014), "#e8ecf1", 1)
            seg((-gy, t, 0.014), (gy, t, 0.014), "#e8ecf1", 1)

        # --- 地面格网（摆球静止高度）作为深度参照
        fl = max(self.params.A * 2.0, 0.12)
        for i in range(-2, 3):
            t = i / 2.0 * fl
            seg((t, -fl, -Ltot - 0.010), (t, fl, -Ltot - 0.010), "#f0f3f7", 1)
            seg((-fl, t, -Ltot - 0.010), (fl, t, -Ltot - 0.010), "#f0f3f7", 1)

        # --- 两个锚点的短立柱
        for A, nm in ((A1, "A1"), (A2, "A2")):
            seg((A[0], A[1], 0.0), (A[0], A[1], 0.055), C_ARM, 3)
            x, y, _ = proj((A[0], A[1], 0.062))
            cv.create_text(x, y, text=nm, fill=C_ARM, font=self.tr.mono(9))

        # --- 两根上臂
        seg(A1, K, self._lighten(C_ARM, 1.0), 2)
        seg(A2, K, self._lighten(C_ARM, 1.0), 2)
        # --- 下臂
        seg(K, P, C_A1, 2)

        # --- 结点
        disc(K, 0.010, C_KNOT, "#8a6208")
        kx, ky, _ = proj(K)
        cv.create_text(kx + 12, ky - 10, text="K", anchor="w", fill=C_KNOT,
                       font=self.tr.mono(9, True))

        # --- 摆球 + 地面投影点
        disc((P[0], P[1], -Ltot - 0.010), 0.011, "#e6e9ee")
        disc(P, 0.017, C_BOB, "#7d2019")
        px, py, _ = proj(P)
        cv.create_text(px + 16, py, text="P", anchor="w", fill=C_BOB,
                       font=self.tr.mono(9, True))

        # --- 3D 轨迹（把每个历史点都还原成摆球的三维位置）
        if self.show_3d_trace.get() and len(self.sim.trace) > 1:
            step = max(1, len(self.sim.trace) // 2500)
            pts = []
            for (tx, ty) in self.sim.trace[::step]:
                pts.append(proj((tx, ty, -Ltot)))
            for i in range(1, len(pts)):
                x1, y1, z1 = pts[i - 1]
                x2, y2, _ = pts[i]
                cv.create_line(x1, y1, x2, y2, fill="#e8b4ad", width=1)

        # --- 左上角视角读数
        cv.create_text(10, 10, anchor="nw", fill=C_DIM, font=self.tr.mono(9),
                       text=self._t("d3.readout")
                            % (az % 360.0, el, zoom))
        cv.create_text(10, H - 12, anchor="w", fill=C_DIM,
                       font=self.tr.ui(9),
                       text=self._t("d3.footer") + (self._t("d3.footer_auto") if self.auto_rot.get() else ""))

    def _draw_side(self):
        cv = self.cv_side
        cv.delete("all")
        W = cv.winfo_width(); H = cv.winfo_height()
        if W < 50 or H < 50:
            return
        p = self.params
        g = self.sim.geometry()
        d = derived(p)

        A1 = g["A1"]; A2 = g["A2"]; K = g["K"]; P = g["P"]
        Ltot = p.L + d["h"]
        # 侧视：换算系数由 _scale_for 统一给出（自动=适配，手动=基准×滑条）
        s = self._scale_for("side")
        cx = W / 2
        y0 = 34

        def scr(x, z):
            return cx + x * s, y0 + z * s

        # 天花板
        half = W * 0.47 / s if s > 0 else 0.24
        ax1, ay1 = scr(-min(half, 0.30), 0.0); ax2, ay2 = scr(min(half, 0.30), 0.0)
        cv.create_line(ax1, ay1, ax2, ay2, fill=C_CEIL, width=3)
        cv.create_text(ax1 + 6, ay1 - 12, text=self._t("cv.ceiling"), anchor="w",
                       fill=C_DIM, font=self.tr.ui(9))

        # 上臂
        for A, col in ((A1, C_ARM), (A2, C_ARM)):
            x1, y1 = scr(A[0], A[2]); x2, y2 = scr(K[0], K[2])
            cv.create_line(x1, y1, x2, y2, fill=col, width=2)
        # 下臂
        xk, yk = scr(K[0], K[2]); xp, yp = scr(P[0], P[2])
        cv.create_line(xk, yk, xp, yp, fill=C_A1, width=2)

        # 结点
        r = 6
        cv.create_oval(xk - r, yk - r, xk + r, yk + r,
                       fill=C_KNOT, outline="#8a6208", width=1)
        cv.create_text(xk + 12, yk - 10, text=self._t("cv.knot"), anchor="w", fill=C_KNOT,
                       font=self.tr.ui(9))
        # 锚点
        for A, nm in ((A1, "A₁"), (A2, "A₂")):
            x, y = scr(A[0], A[2])
            cv.create_oval(x - 4, y - 4, x + 4, y + 4, fill=C_ARM, outline="")
            cv.create_text(x, y - 14, text=nm, fill=C_ARM, font=self.tr.mono(9))

        # 摆球 + 侧视轨迹
        xs_, ys_ = scr(P[0], P[2])
        if self.show_trace and len(self.sim.trace) > 1:
            pts = []
            for (tx, ty) in self.sim.trace[-4000:]:
                px, py = scr(tx, P[2])
                pts += [px, py]
            if len(pts) >= 4:
                cv.create_line(*pts, fill="#e8b4ad", width=1)
        rb = max(9, 13)
        cv.create_oval(xs_ - rb, ys_ - rb, xs_ + rb, ys_ + rb,
                       fill=C_BOB, outline="#7d2019", width=2)
        cv.create_text(xs_ + rb + 10, ys_, text=self._t("cv.bob"), anchor="w", fill=C_BOB,
                       font=self.tr.ui(9))

        # 竖直参考线
        cv.create_line(cx, y0, cx, y0 + Ltot * s, fill="#dfe4ea", dash=(2, 4))
        # 面板标题 + 底部标尺
        cv.create_text(10, 10, anchor="nw", fill=C_TEXT,
                       font=self.tr.ui(10, True),
                       text=self._t("cv.side_title"))
        cv.create_text(12, H - 16, anchor="w", fill=C_DIM,
                       font=self.tr.ui(9),
                       text=self._t("cv.side_footer")
                            % (p.A * 1e3, p.rate, p.damping))

    def _draw_top(self):
        cv = self.cv_top
        cv.delete("all")
        W = cv.winfo_width(); H = cv.winfo_height()
        if W < 50 or H < 50:
            return
        s = self._scale_for("top")
        # 量程跟着换算系数走，网格与读数与之一致
        lim = min(W, H) * 0.44 / max(s, 1e-9)
        cx, cy = W / 2, H / 2

        # 坐标轴
        cv.create_line(0, cy, W, cy, fill="#dfe4ea")
        cv.create_line(cx, 0, cx, H, fill="#dfe4ea")
        for frac in (0.33, 0.66, 1.0):
            rr = lim * frac * s
            cv.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline="#eef1f5")
        cv.create_text(W - 8, cy - 10, text=self._t("cv.axis_x"), anchor="e", fill=C_DIM,
                       font=self.tr.ui(9))
        cv.create_text(cx + 8, 12, text=self._t("cv.axis_y"), anchor="w", fill=C_DIM,
                       font=self.tr.ui(9))

        # 轨迹
        tr = self.sim.trace
        if self.show_trace and len(tr) > 1:
            step = max(1, len(tr) // 12000)
            pts = []
            for (x, y) in tr[::step]:
                pts += [cx + x * s, cy - y * s]
            if len(pts) >= 4:
                cv.create_line(*pts, fill=C_TRACE, width=1)
        # 下视轨迹：与侧视动画同屏，读数放在画布内
        cv.create_text(10, 12, anchor="w", fill=C_TEXT,
                       font=self.tr.ui(10, True),
                       text=self._t("cv.top_title"))
        cxs_, cys_ = cx + self.sim.x * s, cy - self.sim.y * s
        r = 6
        cv.create_oval(cxs_ - r, cys_ - r, cxs_ + r, cys_ + r, fill=C_TRACE2, outline="")
        cv.create_text(10, H - 14, anchor="w", fill=C_DIM,
                       font=self.tr.ui(9),
                       text=self._t("cv.top_footer")
                            % (lim * 1e3, len(tr),
                               derived(self.params)["f_r_A"],
                               ("%.2f s" % derived(self.params)["T_beat"])
                               if math.isfinite(derived(self.params)["T_beat"]) else "∞"))

    def _draw_env(self):
        """右侧：两个方向的位移-时间包络（拍结构）。"""
        cv = self.cv_env
        cv.delete("all")
        W = cv.winfo_width(); H = cv.winfo_height()
        if W < 40 or H < 40:
            return
        cv.create_text(10, 12, anchor="w", fill=C_TEXT,
                       font=self.tr.ui(9, True),
                       text=self._t("cv.env_title"))
        tr = self.sim.trace
        if len(tr) < 4:
            return
        n = min(len(tr), 3000)
        seg = tr[-n:]
        A = max(self.params.A, 1e-9)
        y0 = 30; h = H - 50
        pts_x = []; pts_y = []
        for i, (x, y) in enumerate(seg):
            px = 8 + (W - 16) * i / max(n - 1, 1)
            pts_x += [px, y0 + h * (1 - min(abs(x) / A, 1.0))]
            pts_y += [px, y0 + h * (1 - min(abs(y) / A, 1.0))]
        cv.create_line(8, y0 + h, W - 8, y0 + h, fill="#dfe4ea")
        if len(pts_x) >= 4:
            cv.create_line(*pts_x, fill=C_TRACE, width=1)
            cv.create_line(*pts_y, fill=C_TRACE2, width=1)
        cv.create_text(10, H - 14, anchor="w", fill=C_DIM,
                       font=self.tr.ui(9),
                       text=self._t("cv.env_footer") % (n * DT * self.params.rate))


def smoke_test():
    """无显示环境下确认程序能建窗、改参数、跑帧，并逐个标签页画一遍。"""
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception as e:
        print("SMOKE: 无法创建窗口（%r）—— 需要有图形环境才能运行界面" % e)
        return 0 if os.environ.get("DSH_ALLOW_NO_DISPLAY") else 1
    app = App(root)
    # 改几个参数并强制重绘
    for k, v in (("L", 0.15), ("R", 0.12), ("A", 0.04), ("psi", 30.0)):
        app.scales[k][0].set(v)
    app.mode.set("sliding"); app._apply_params(reset=True)
    for _ in range(30):
        app._apply_params(reset=False)
        app.sim.step(DT)
        app.sim.push_trace()
        app._redraw_all()
        root.update()

    # 逐个标签页画一遍，确认两个视图都不会抛异常
    for idx, name in enumerate(("动画+二维轨迹", "3D 视角")):
        app.nb.select(idx)
        root.update()
        app._redraw_all()
        root.update()
        n_side = len(app.cv_side.find_all())
        n_top = len(app.cv_top.find_all())
        n_env = len(app.cv_env.find_all())
        n_3d = len(app.cv_3d.find_all())
        print("  标签 %d %-12s 侧视=%d 轨迹=%d 包络=%d 3D=%d"
              % (idx, name, n_side, n_top, n_env, n_3d))
        if idx == 0:
            # 侧视与二维轨迹必须同屏且都画出了东西
            if app.nb.index(app.nb.select()) != 0:
                print("SMOKE FAIL: 无法停留在标签 0")
                root.destroy(); return 1
            if not (n_side > 5 and n_top > 5 and n_env > 2):
                print("SMOKE FAIL: 同屏的两个视图未同时绘制")
                root.destroy(); return 1
            w1 = app.cv_side.winfo_width(); h1 = app.cv_side.winfo_height()
            w2 = app.cv_top.winfo_width(); h2 = app.cv_top.winfo_height()
            w3 = app.cv_env.winfo_width(); h3 = app.cv_env.winfo_height()
            print("        画布尺寸：侧视 %dx%d，轨迹 %dx%d，包络 %dx%d"
                  % (w1, h1, w2, h2, w3, h3))
            if min(w1, h1, w2, h2, w3, h3) < 40:
                print("SMOKE FAIL: 同屏时有画布被压得看不见")
                root.destroy(); return 1
        if idx == 1 and n_3d < 10:
            print("SMOKE FAIL: 3D 视图几乎没画出东西")
            root.destroy()
            return 1

    # ---- 缩放功能自检 ----------------------------------------------------
    # 1) 手动模式：滑条与 +/− 按钮必须真的改变倍率
    app.zoom_mode.set("manual")
    app.zoom_var.set(1.0)
    app._zoom_step(1.25)
    if abs(app._zoom_value() - 1.25) > 1e-9:
        print("SMOKE FAIL: + 按钮没有把倍率改成 1.25（实为 %.4f）" % app._zoom_value())
        root.destroy(); return 1
    app._zoom_step(1 / 1.25)
    if abs(app._zoom_value() - 1.0) > 1e-9:
        print("SMOKE FAIL: − 按钮没有把倍率改回 1.00")
        root.destroy(); return 1
    app.zoom_var.set(9.0); app._on_zoom_slider(9.0)
    print("  手动模式：滑条/按钮可改倍率，当前 %.2f×" % app._zoom_value())
    app.zoom_var.set(1.0); app._on_zoom_slider(1.0)

    # 2) 自动模式：换一组差别很大的参数，内容必须始终完整落在画布内
    print("自动缩放随参数变化（应始终框得住）：")
    ok_auto = True
    for mode_test in ("device", "trace"):
      for tag, preset in (("参考几何", dict(l=0.250, R=0.060, L=0.300, A=0.020)),
                        ("宽 V 形", dict(l=0.250, R=0.200, L=0.300, A=0.030)),
                        ("短下臂", dict(l=0.250, R=0.060, L=0.100, A=0.010)),
                        ("长下臂", dict(l=0.250, R=0.060, L=0.900, A=0.020)),
                        ("大振幅", dict(l=0.250, R=0.060, L=0.300, A=0.120))):
        app.zoom_mode.set(mode_test)
        app._set_params(dict(preset, psi=45.0))
        root.update()
        # 走界面同一条路径：_redraw_all 会先刷新范围/读数，再画
        app._redraw_all()
        root.update()
        k = app._scale_for("side")
        ks = app._fit_factor("side")
        kt = app._fit_factor("top")
        # 侧视：把装置的极值点按同样的变换算回屏幕坐标，检查是否越界
        pp = app.params
        dd = derived(pp)
        Ltot = pp.L + dd["h"]
        W = app.cv_side.winfo_width(); H = app.cv_side.winfo_height()
        s = k
        cx, y0 = W / 2, 34
        pts = [(-pp.R, 0.0), (pp.R, 0.0), (0.0, Ltot)]
        for a in (0, 90, 180, 270):
            pts.append((max(pp.R, pp.A) * math.cos(math.radians(a)), Ltot))
        bad = [(x, z) for (x, z) in pts
               if not (0 <= cx + x * s <= W and 0 <= y0 + z * s <= H)]
        # 下视：轨迹半径应落在画布内
        st = app._scale_for("top")
        half = min(app.cv_top.winfo_width(), app.cv_top.winfo_height()) / 2
        rpx = getattr(app, "_cur_xr", pp.A) * st
        ok_top = rpx <= half
        print("    %-8s 侧视 %.0f px/m（适配 %.0f）轨迹 %.0f px/m  "
              "侧视越界点 %d  下视半径 %.0f/%.0f px %s"
              % (tag, k, ks, st, len(bad), rpx, half,
                 "" if (not bad and ok_top) else "  <-- 被裁掉了"))
        if bad or not ok_top:
            ok_auto = False
    if not ok_auto:
        print("SMOKE FAIL: 自动缩放下有内容被裁掉")
        root.destroy(); return 1

    # 1) 语言表自检：两种语言的 key 必须一一对应、占位符一致
    probs = check_i18n()
    if probs:
        print("SMOKE FAIL: i18n 表有问题：%s" % probs[:4])
        root.destroy(); return 1
    print("  " + app.tr("test.lang_ok") % len(app._texts))

    # 2) 切换语言后，所有登记的控件文字都要跟着变
    def snapshot():
        snap = {}
        for w, key in app._texts.items():
            try:
                snap[key] = str(w.cget("text"))
            except Exception:
                pass
        return snap

    def cv_text(name):
        cv = getattr(app, name)
        return " ".join(str(cv.itemcget(i, "text")) for i in cv.find_all()
                        if cv.type(i) == "text")

    app.lang.set("zh"); app._on_lang_change(); root.update()
    zh_snap = snapshot()
    zh_cv = {name: cv_text(name) for name in ("cv_top", "cv_side", "cv_env", "cv_3d")}
    app.lang.set("en"); app._on_lang_change(); root.update()
    en_snap = snapshot()
    # 不管当前停在哪个标签页，四个画布都必须切换到英文
    for name in ("cv_top", "cv_side", "cv_env", "cv_3d"):
        before = zh_cv[name]
        after = cv_text(name)
        if after == before and before:
            print("SMOKE FAIL: 切到英文后 %s 文字没变（当前标签页 %d）"
                  % (name, app.nb.index(app.nb.select())))
            root.destroy(); return 1
    same = [k for k in zh_snap if k in en_snap and zh_snap[k] == en_snap[k]]
    # 允许 zh 与 en 文案相同的条目（例如 lang.zh / lang.en 两个语言名本身）
    allow_same = {"lang.zh", "lang.en", "ro.h", "btn.show_trace", "btn.show_3d_trace"}
    bad_same = [k for k in same if k not in allow_same]
    if bad_same:
        print("SMOKE FAIL: 切到英文后这些控件文字没变：%s" % bad_same[:6])
        root.destroy(); return 1
    # 抽查几个关键文字确实是英文
    for key, expect in (("panel.params", "Parameters"), ("sl.L", "Lower arm"),
                        ("btn.release", "Re-release"), ("mode.tripod", "tripod")):
        if expect not in en_snap.get(key, ""):
            print("SMOKE FAIL: 英文文案异常 %s = %r（应含 %r）"
                  % (key, en_snap.get(key), expect))
            root.destroy(); return 1
    # 画布上也要出现英文标题
    cv_txt = " ".join(str(app.cv_top.itemcget(i, "text"))
                      for i in app.cv_top.find_all()
                      if app.cv_top.type(i) == "text")
    if "Top view" not in cv_txt:
        print("SMOKE FAIL: 画布标题没有切换到英文（%r）" % cv_txt[:120])
        root.destroy(); return 1
    print("  " + app.tr("test.switch") % ("English", len(en_snap)))
    # 切回中文，确认可以来回切
    app.lang.set("zh"); app._on_lang_change(); root.update()
    zh2 = snapshot()
    back_ok = all(zh2.get(k) == v for k, v in zh_snap.items() if k in zh2)
    if not back_ok:
        print("SMOKE FAIL: 切回中文后文字没有完全恢复")
        root.destroy(); return 1
    print("  切回中文：%d 个控件文字完全恢复" % len(zh2))

    # 3) 自动模式下的换算系数必须随参数变化（否则"自动"是假的）
    vals = []
    for preset in (dict(l=0.250, R=0.060, L=0.900, A=0.020),
                   dict(l=0.250, R=0.060, L=0.100, A=0.020)):
        app.zoom_mode.set("device")
        app._set_params(dict(preset, psi=45.0))
        root.update()
        app._redraw_all()
        vals.append(app._scale_for("side"))
    print("  自动换算系数：长下臂 %.0f px/m vs 短下臂 %.0f px/m（应不同，且长下臂更小）"
          % (vals[0], vals[1]))
    if not (vals[0] < vals[1] * 0.8):
        print("SMOKE FAIL: 自动换算系数没有随参数合理变化")
        root.destroy(); return 1

    # 4) 手动模式：滑条必须真的改变绘制用的换算系数
    app.zoom_mode.set("manual")
    app.zoom_var.set(1.0)
    s1 = app._scale_for("side")
    app.zoom_var.set(2.0)
    s2 = app._scale_for("side")
    if abs(s2 / s1 - 2.0) > 1e-9:
        print("SMOKE FAIL: 手动倍率没有线性作用到换算系数（%.1f -> %.1f）" % (s1, s2))
        root.destroy(); return 1
    print("  手动模式：滑条 1.00×→2.00× 使换算系数 %.0f→%.0f px/m（正好翻倍）" % (s1, s2))
    app.zoom_mode.set("device")
    app.zoom_var.set(1.0)
    app._set_params(dict(l=0.250, R=0.060, L=0.300, A=0.020, psi=45.0))
    root.update()

    # 3D 交互：模拟拖动与滚轮，再从多个角度各画一次
    class _E:
        def __init__(self, x, y, delta=0):
            self.x, self.y, self.delta = x, y, delta

    app._orbit_start(_E(300, 300))
    app._orbit_move(_E(420, 250))
    app._orbit_end(_E(420, 250))
    z_before = app.zoom3d
    app._orbit_zoom(_E(0, 0, 120))
    if abs(app.zoom3d / z_before - 1.15) > 1e-9:
        print("SMOKE FAIL: 滚轮没有按 1.15 倍缩放 3D 视图")
        root.destroy(); return 1
    app._orbit_zoom(_E(0, 0, -120))
    az0, el0, z0 = app.az, app.el, app.zoom3d
    for (az, el) in ((0.0, 0.0), (90.0, 5.0), (200.0, 70.0), (0.0, 89.0), (0.0, -89.0)):
        app.az, app.el = az, el
        app._draw_3d()
        root.update()
    app._reset_view()
    root.update()
    if not (abs(az0 - (38.0 + 120 * 0.45)) < 1e-6 and abs(z0 - 1.0) < 1e-9):
        print("SMOKE FAIL: 拖动/滚轮没有正确改变视角 (az=%.3f zoom3d=%.3f)" % (az0, z0))
        root.destroy()
        return 1
    if not (app.az == 38.0 and app.el == 24.0 and app.zoom3d == 1.0):
        print("SMOKE FAIL: 复位视角没有恢复默认值")
        root.destroy()
        return 1
    print("  3D：拖动改方位/仰角、滚轮 1.15 倍缩放、复位均正常")

    d = derived(app.params)
    print("SMOKE OK: 两个标签页均正常绘制（侧视与二维轨迹同屏）；"
          "中英切换（含四个画布）正常；缩放（手动/自动/3D 滚轮）正常；"
          "当前 f_r=%.5f  T_beat=%s"
          % (d["f_r_A"], ("%.2f s" % d["T_beat"]) if math.isfinite(d["T_beat"]) else "无限"))
    root.destroy()
    return 0


if __name__ == "__main__":
    if "--smoke" in sys.argv:
        raise SystemExit(smoke_test())
    import tkinter as tk
    # --lang en / --lang zh ：直接以指定语言启动（界面里也能随时切）。
    # 不给参数时用 detect_default_lang()：中文系统给中文，其余给英文。
    start_lang = detect_default_lang()
    if "--lang" in sys.argv:
        i = sys.argv.index("--lang")
        if len(sys.argv) > i + 1 and sys.argv[i + 1] in LANGS:
            start_lang = sys.argv[i + 1]
    root = tk.Tk()
    app = App(root)
    if start_lang != app.lang.get():
        app.lang.set(start_lang)
        app._on_lang_change()
    root.mainloop()
