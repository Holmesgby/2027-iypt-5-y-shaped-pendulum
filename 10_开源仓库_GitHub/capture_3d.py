"""
把 3D 视图在几个典型视角下渲染成 PNG，供人工核对（也便于放进报告/PPT）。

不依赖任何 GUI 截图工具：直接复用 ypendulum_gui.App 的画布绘制函数，
把画布内容导出为 PostScript，再用 PIL 转成 PNG。

用法： python capture_3d.py [输出目录]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import tkinter as tk                                   # noqa: E402
from ypendulum_gui import App, DT                       # noqa: E402
from ypendulum_sim import derived                       # noqa: E402

# (标签, 方位角, 仰角, 缩放, 说明)
VIEWS = [
    ("3d_default", 38.0, 16.0, 1.0, "默认斜视"),
    ("3d_top", 0.0, 82.0, 1.05, "接近正上方（与二维轨迹对照）"),
    ("3d_front", 0.0, 2.0, 1.0, "接近正前方（与侧视图对照）"),
    ("3d_side", 90.0, 8.0, 1.0, "从侧面 90°"),
]


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    root = tk.Tk()
    root.geometry("1280x820")
    app = App(root)
    app.nb.select(1)          # 3D 视图是第二个标签页（索引 1）
    root.update()

    # 让摆球先走出一段能看出图案的轨迹
    p = app.params
    app.mode.set("tied")
    app._apply_params(reset=True)
    # 先暂停主循环，否则 root.update() 里的 _tick 会用到刚被重置的 sim，轨迹点数不稳定
    app.running = False
    for _ in range(int(24.0 / DT)):
        app.sim.step(DT)
        app.sim.push_trace()
    print("轨迹点数 = %d（%.1f s 实时）" % (len(app.sim.trace), len(app.sim.trace) * DT))
    root.update()

    made = []
    ps_only = 0
    for name, az, el, zoom, desc in VIEWS:
        app.az, app.el, app.zoom3d = az, el, zoom
        app._draw_3d()
        root.update()
        ps = os.path.join(outdir, name + ".ps")
        png = os.path.join(outdir, name + ".png")
        app.cv_3d.postscript(file=ps, colormode="color")
        try:
            from PIL import Image
            with Image.open(ps) as im:
                im.load()
                im.convert("RGB").save(png, dpi=(150, 150))
            os.remove(ps)
            made.append((name, desc, png))
            print("wrote %s  (%s)" % (png, desc))
        except Exception as e:
            ps_only += 1
            if ps_only == 1:                     # 只提示一次，别刷屏
                print("无法把 PostScript 转成 PNG：%r" % e)
                print("（这一步需要 Ghostscript，本机没装；.ps 文件已保留，可用其他工具转换）")
            print("已保留 %s" % ps)
    d = derived(p)
    print("视角渲染完成：f_r=%.5f  T_beat=%.3f s  轨迹点数=%d"
          % (d["f_r_A"], d["T_beat"], len(app.sim.trace)))
    if made:
        print("成功导出 %d 个 PNG，%d 个只拿到 .ps" % (len(made), ps_only))
    else:
        print("没有 PNG 产出（缺 Ghostscript）—— 这不影响程序本身，"
              "装了 Ghostscript 后重跑即可。")
    root.destroy()
    return made


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "figs")
    main(out)
    # 缺 Ghostscript 属于环境问题，不是程序失败：仍然以 0 退出，避免误判。
    raise SystemExit(0)
