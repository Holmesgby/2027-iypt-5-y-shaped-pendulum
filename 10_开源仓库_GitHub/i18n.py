"""
界面文案（中 / 英）与字体选择。

把文案集中在这里，而不是散落在 ypendulum_gui.py 里，好处是：
  · 加一种语言只要往 _STRINGS 里补一列；
  · 界面里的字串都是 key，改文案不会碰到逻辑；
  · 自检可以检查两种语言的 key 是否一一对应（见 check_i18n()）。

字体单独处理：中文必须用带 CJK 字形的字体（Windows 上是 Microsoft YaHei），
英文用 Consolas 更整齐。
"""

LANGS = ("zh", "en")
LANG_NAME = {"zh": "中文", "en": "English"}
DEFAULT_LANG = "zh"


def detect_default_lang():
    """按系统区域猜一个默认语言：中文系统给中文，其余给英文。

    只影响"第一次打开"看到什么；界面里随时可以切，也可以用 --lang 强制指定。
    """
    try:
        import locale
        loc = (locale.getdefaultlocale()[0] or "") + " " + (locale.getlocale()[0] or "")
    except Exception:
        loc = ""
    loc = loc.lower()
    if "zh" in loc or "chinese" in loc:
        return "zh"
    return "en" if loc.strip() else DEFAULT_LANG

# key -> (中文, English)
_STRINGS = {
    # ---- 窗口与标签页
    "app.title": ("Y 形摆模拟器 —— IYPT 2027 第 5 题 (Y-shaped pendulum)",
                  "Y-shaped Pendulum Simulator - IYPT 2027 Problem 5"),
    "tab.main": ("  ① 动画 + 二维轨迹  ", "  1. Animation + 2-D trace  "),
    "tab.3d": ("  ② 3D 自由视角  ", "  2. Free 3-D view  "),

    # ---- 左侧面板
    "panel.params": ("参数调节", "Parameters"),
    "panel.language": ("语言 / Language", "Language / 语言"),
    "lang.zh": ("中文", "中文"),
    "lang.en": ("English", "English"),
    "panel.zoom": ("显示缩放", "Display zoom"),
    "panel.mode": ("结点约束状态", "Knot constraint"),
    "panel.presets": ("快速预设", "Presets"),

    # ---- 滑条
    "sl.l": ("上臂长 l", "Upper arm length l"),
    "sl.R": ("孔距半值 R", "Half anchor spacing R"),
    "sl.L": ("下臂长 L", "Lower arm length L"),
    "sl.mK": ("结点质量 m_K", "Knot mass m_K"),
    "sl.A": ("释放振幅 A", "Release amplitude A"),
    "sl.psi": ("释放方位 ψ0", "Release azimuth psi0"),
    "sl.damping": ("阻尼 b", "Damping b"),
    "sl.rate": ("时间倍率", "Time rate"),

    # ---- 缩放
    "zoom.device": ("仅装置", "Device"),
    "zoom.trace": ("适配轨迹", "Whole trace"),
    "zoom.manual": ("手动", "Manual"),
    "zoom.hint": ("自动适配会让整个摆（或整条轨迹）始终完整可见；"
                  "切到「手动」后用滑条或 +/− 自己调。",
                  "Auto-fit keeps the whole pendulum (or the whole trace) visible. "
                  "Switch to Manual to zoom with the slider or +/-."),
    "zoom.manual_suffix": ("（手动）", " (manual)"),
    "zoom.auto_suffix_device": ("（自动·仅装置）", " (auto: device)"),
    "zoom.auto_suffix_trace": ("（自动·适配轨迹）", " (auto: whole trace)"),
    "zoom.readout": ("侧视 %.2f× / 轨迹 %.2f×%s", "side %.2f x / trace %.2f x%s"),

    # ---- 三态
    "mode.tied": ("系结（主装置，f_r≈1.345）", "Tied knot (main, f_r ~ 1.345)"),
    "mode.sliding": ("滑环（近简并，f_r≈1.014）", "Sliding ring (near-degenerate, f_r ~ 1.014)"),
    "mode.tripod": ("三弦三脚架（严格简并，f_r=1）", "3-string tripod (exactly degenerate, f_r = 1)"),

    # ---- 按钮
    "btn.pause": ("⏸ 暂停", "Pause"),
    "btn.play": ("▶ 播放", "Play"),
    "btn.release": ("↺ 重新释放", "Re-release"),
    "btn.clear": ("✕ 清轨迹", "Clear trace"),
    "btn.png": ("保存轨迹 PNG", "Save trace PNG"),
    "btn.show_trace": ("显示轨迹", "Show trace"),
    "btn.reset_view": ("复位视角", "Reset view"),
    "btn.auto_rotate": ("自动旋转", "Auto-rotate"),
    "btn.show_3d_trace": ("显示轨迹", "Show trace"),

    # ---- 预设
    "ps.ref": ("参考几何", "Reference"),
    "ps.degenerate": ("1:1 简并", "1:1 degenerate"),
    "ps.wide": ("宽 V 形", "Wide V"),
    "ps.short": ("短下臂", "Short L"),

    # ---- 读数
    "ro.h": ("h", "h"),
    "ro.slack": ("松弛阈值", "slack limit"),

    # ---- 警告
    "warn.slack": ("⚠ 振幅超过松弛阈值：模型失效（程序仍会跑，仅作演示）",
                   "! Amplitude exceeds the slack threshold: the model no longer holds "
                   "(still running, demonstration only)"),
    "warn.tripod": ("三脚架态：两模严格简并 → 图案不旋进",
                    "Tripod: the two modes are exactly degenerate, so the pattern never precesses"),
    "warn.sliding": ("滑环态：两模近简并 → 旋进极慢（T_beat 上百秒）",
                     "Sliding ring: near-degenerate modes, so precession is very slow "
                     "(T_beat of order 100 s)"),
    "warn.longbeat": ("T_beat = %.0f s：需要很久才看得出旋进，可调大时间倍率",
                      "T_beat = %.0f s: precession takes a long time; raise the time rate"),
    "warn.saved": ("已保存轨迹图：\n%s", "Trace figure saved to:\n%s"),
    "warn.zoom_saved": ("已保存轨迹图", "Trace figure saved"),

    # ---- 画布内文字
    "cv.ceiling": ("天花板", "ceiling"),
    "cv.side_title": ("① 侧视：真实物理动画", "1. Side view: live physics animation"),
    "cv.side_footer": ("振幅 %.0f mm   时间倍率 %.2f×   阻尼 %.3f 1/s",
                       "amplitude %.0f mm   time rate %.2f x   damping %.3f 1/s"),
    "cv.top_title": ("② 下视：与动画同步的二维轨迹（Lissajous 图案）",
                     "2. Top view: 2-D trace (Lissajous pattern), frame-synced"),
    "cv.top_footer": ("满量程 %.1f mm   轨迹点数 %d   f_r = %.4f   T_beat = %s",
                      "full scale %.1f mm   points %d   f_r = %.4f   T_beat = %s"),
    "cv.env_title": ("③ 包络：|x|（红）与 |y|（蓝）的拍",
                     "3. Envelope: beats of |x| (red) and |y| (blue)"),
    "cv.env_footer": ("最近 %.1f s", "last %.1f s"),
    "cv.knot": ("结点 K", "knot K"),
    "cv.bob": ("摆球 P", "bob P"),
    "cv.axis_x": ("面内 x", "in-plane x"),
    "cv.axis_y": ("面外 y", "out-of-plane y"),

    # ---- 3D
    "d3.hint": ("3D 视角：按住左键拖动旋转 · 滚轮缩放 · 双击复位",
                "3-D view: drag to rotate, wheel to zoom, double-click to reset"),
    "d3.note": ("提示：把鼠标拖到差不多从正上方看，就能看到二维 Lissajous 图案；"
                "压低到接近水平则像在实验台旁边看。",
                "Tip: drag until you are almost straight above to see the 2-D Lissajous "
                "pattern; lower the elevation to look at it from beside the bench."),
    "d3.footer": ("拖动=旋转   滚轮=缩放   双击=复位",
                  "drag = rotate   wheel = zoom   double-click = reset"),
    "d3.footer_auto": ("   [自动旋转中]", "   [auto-rotating]"),
    "d3.readout": ("方位角 %6.1f°   仰角 %5.1f°   缩放 %.2f×",
                   "azimuth %6.1f deg   elevation %5.1f deg   zoom %.2f x"),

    # ---- 自检输出
    "test.lang_ok": ("语言表：两种语言的 key 完全一致（%d 条）",
                     "i18n table: both languages define exactly the same keys (%d)"),
    "test.lang_missing": ("!! 语言表 key 不一致：%s", "!! i18n key mismatch: %s"),
    "test.switch": ("切换到 %s：%d 个控件文字已更新",
                    "switched to %s: %d widget labels updated"),
}

FONT = {
    "zh": {"ui": "Microsoft YaHei", "mono": "Consolas"},
    "en": {"ui": "Segoe UI", "mono": "Consolas"},
}


class Translator:
    """按 key 取文案；缺 key 时返回 key 本身，方便定位漏译。"""

    def __init__(self, lang="zh"):
        self.lang = lang if lang in LANGS else "zh"

    def set(self, lang):
        self.lang = lang if lang in LANGS else "zh"

    def __call__(self, key):
        pair = _STRINGS.get(key)
        if pair is None:
            return key
        return pair[0] if self.lang == "zh" else pair[1]

    # ---- 供界面使用
    @property
    def ui_font(self):
        return FONT[self.lang]["ui"]

    @property
    def mono_font(self):
        return FONT[self.lang]["mono"]

    def ui(self, size, bold=False):
        return (self.ui_font, size, "bold") if bold else (self.ui_font, size)

    def mono(self, size, bold=False):
        return (self.mono_font, size, "bold") if bold else (self.mono_font, size)


def check_i18n(verbose=False):
    """自检：两种语言的 key 必须一一对应，不能有漏译或多译。"""
    problems = []
    for key, pair in _STRINGS.items():
        if not isinstance(pair, tuple) or len(pair) != 2:
            problems.append("%s: 不是 (中文, English) 二元组" % key)
            continue
        for i, s in enumerate(pair):
            if not isinstance(s, str) or not s.strip():
                problems.append("%s[%d]: 空文案" % (key, i))
    # 格式占位符必须两种语言一致，否则格式化时会报错
    import re
    ph = re.compile(r"%[-+ #0-9.]*[a-zA-Z%]")
    for key, (zh, en) in _STRINGS.items():
        if sorted(ph.findall(zh)) != sorted(ph.findall(en)):
            problems.append("%s: 占位符不一致  zh=%s  en=%s"
                            % (key, ph.findall(zh), ph.findall(en)))
    if verbose:
        print("i18n: %d 条文案，%d 个问题" % (len(_STRINGS), len(problems)))
        for p in problems:
            print("   ", p)
    return problems


if __name__ == "__main__":
    import sys
    probs = check_i18n(verbose=True)
    print("I18N:", "PASS" if not probs else "FAIL")
    raise SystemExit(0 if not probs else 1)
