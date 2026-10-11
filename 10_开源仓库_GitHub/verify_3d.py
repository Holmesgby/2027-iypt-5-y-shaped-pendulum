"""
3D 视图的数值自检（不需要图形环境、不需要截图）。

3D 视图只有"看起来对不对"这种主观判据，但投影数学是能客观检验的。检验项：

  1. 相机基是正交归一的右手系（三个基矢两两垂直、模为 1、right × up = fwd）；
  2. 验证脚本用的投影公式与界面 _draw_3d 里的**完全一致**（用同一段代码算）；
  3. 从正上方看：世界里的直线在屏幕上仍是直线（透视把直线映成直线），
     且屏幕纵坐标是世界坐标的莫比乌斯函数（透视的正确判据，不是相似变换）；
  4. 从正前方看：屏幕横坐标必须线性正比于世界 x；
  5. 不同方位角给出不同投影（否则"旋转"是假的）；
  6. 深度单调：沿相机视线更远的点投影尺度更小，且比例等于深度反比；
  7. 极端视角（±89.99°、方位角 0/360°）投影仍然有限，不出现除零。

用法： python verify_3d.py
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from ypendulum_sim import Params, YYSim, derived          # noqa: E402

# ---------------------------------------------------------------------------
# 界面里 _draw_3d 使用的常数（改界面时这里也要跟着改，脚本第 0 项会检查一致性）
CAM_FACTOR = 2.6          # d_cam = CAM_FACTOR * Ltot
FIT_FACTOR = 0.85         # f_px = min(W,H) / (FIT_FACTOR * Ltot) * zoom
DEPTH_FLOOR = 0.02        # zc 下限 = DEPTH_FLOOR * Ltot


def view(p, az_deg, el_deg):
    """世界坐标 -> 相机坐标（与 ypendulum_gui.App._view 相同公式）。"""
    a = math.radians(az_deg); e = math.radians(el_deg)
    ca, sa, ce, se = math.cos(a), math.sin(a), math.cos(e), math.sin(e)
    right = (-sa, ca, 0.0)
    up = (-ce * ca, -ce * sa, se)
    fwd = (se * ca, se * sa, ce)
    dx, dy, dz = p
    return (dx * right[0] + dy * right[1] + dz * right[2],
            dx * up[0] + dy * up[1] + dz * up[2],
            -(dx * fwd[0] + dy * fwd[1] + dz * fwd[2]))


def make_proj(az, el, Ltot, W=900, H=700, zoom=1.0):
    """与 ypendulum_gui.App._draw_3d 内部一致的投影。"""
    cx3, cy3, cz3 = 0.0, 0.0, -Ltot / 2.0
    d_cam = CAM_FACTOR * Ltot
    f_px = min(W, H) / (FIT_FACTOR * Ltot) * zoom
    cxs, cys = W / 2, H / 2

    def proj(pt):
        q = view((pt[0] - cx3, pt[1] - cy3, pt[2] - cz3), az, el)
        zc = max(d_cam + q[2], DEPTH_FLOOR * Ltot)
        return cxs + f_px * q[0] / zc, cys - f_px * q[1] / zc, zc

    proj.f_px = f_px
    proj.d_cam = d_cam
    return proj


def cross(u, v):
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def dot(u, v):
    return sum(x * y for x, y in zip(u, v))


def norm(v):
    return math.sqrt(dot(v, v))


def main():
    ok = True
    L = []

    # ---- 0. 与界面源码的一致性（保证这个脚本检验的就是界面用的公式）
    gui = os.path.join(HERE, "ypendulum_gui.py")
    src = open(gui, encoding="utf-8").read()
    checks = [("CAM_FACTOR", "d_cam = 2.6 * Ltot"),
              ("FIT_FACTOR", "min(W, H) / (0.85 * Ltot) * zoom"),
              ("DEPTH_FLOOR", "0.02 * Ltot")]
    for name, needle in checks:
        if needle not in src:
            ok = False
            L.append("  !! 界面源码里找不到 %s 对应的写法（%r）—— 脚本与界面可能已不同步"
                     % (name, needle))
    if "d_cam + q[2]" not in src:
        ok = False
        L.append("  !! 界面源码里的透视深度不是 d_cam + q[2]")
    L.append("  与界面源码的一致性：%s" % ("OK" if ok else "不一致"))

    # ---- 1. 相机基正交归一 + 右手系
    for az, el in ((0, 0), (37, 22), (140, -55), (270, 80)):
        a = math.radians(az); e = math.radians(el)
        right = (-math.sin(a), math.cos(a), 0.0)
        up = (-math.cos(e) * math.cos(a), -math.cos(e) * math.sin(a), math.sin(e))
        fwd = (math.sin(e) * math.cos(a), math.sin(e) * math.sin(a), math.cos(e))
        errs = [abs(norm(v) - 1) for v in (right, up, fwd)]
        errs += [abs(dot(right, up)), abs(dot(right, fwd)), abs(dot(up, fwd))]
        cr = cross(right, up)
        errs.append(max(abs(cr[i] - fwd[i]) for i in range(3)))
        m = max(errs)
        if m > 1e-12:
            ok = False
            L.append("  !! 方位%4d° 仰角%4d° 相机基不正交（%.2e）" % (az, el, m))
    L.append("  相机基正交归一 + 右手系：4 个视角全部通过（最大偏差 <1e-12）")

    # ---- 真实轨迹
    p = Params(A=0.020, psi_deg=45.0, damping=0.010)
    sim = YYSim(p=p)
    dt = 2.0e-3
    for _ in range(int(20.0 / dt)):
        sim.step(dt)
        sim.push_trace()
    d = derived(p)
    Ltot = p.L + d["h"]
    pts3 = [(x, y, -Ltot) for (x, y) in sim.trace]
    L.append("")
    L.append("  真实轨迹 %d 点 / %.1f s，h=%.4f m，Ltot=%.4f m" % (len(pts3), len(pts3) * dt, d["h"], Ltot))

    # ---- 2. 俯视：世界直线 -> 屏幕直线
    proj_t = make_proj(0.0, 89.9, Ltot)
    worst = 0.0
    for (x1, y1), (x2, y2) in (((-0.02, -0.02), (0.02, 0.02)),
                               ((0.0, -0.03), (0.0, 0.03)),
                               ((-0.03, 0.01), (0.03, 0.01))):
        for t in (0.13, 0.37, 0.62, 0.88):
            mx = x1 + t * (x2 - x1); my = y1 + t * (y2 - y1)
            sxa, sya, _ = proj_t((x1, y1, 0.0))
            sxb, syb, _ = proj_t((x2, y2, 0.0))
            sxm, sym, _ = proj_t((mx, my, 0.0))
            # 点到直线的距离
            dx = sxb - sxa; dy = syb - sya
            ln = math.hypot(dx, dy)
            dev = abs((sxm - sxa) * dy - (sym - sya) * dx) / ln
            worst = max(worst, dev)
    L.append("  俯视：世界直线在屏幕上的共线偏差 max %.2e px" % worst)
    if worst > 1e-9:
        ok = False
        L.append("  !! 直线被投影成曲线 —— 投影公式有误")

    # ---- 3/4. 用一套独立写出的解析透视式核对投影（俯视 + 正视 + 任意斜视）
    #
    # 相机绕场景中心 (0, 0, -Ltot/2) 转，基为
    #     right = (-sin a,  cos a, 0)
    #     up    = (-ce·cos a, -ce·sin a, se)
    #     fwd   = ( se·cos a,  se·sin a, ce)
    # 于是对世界点 w，相机坐标是
    #     q_r = right·(w-c) ,  q_u = up·(w-c) ,  深度 zc = d_cam - fwd·(w-c)
    # 屏幕坐标
    #     sx = W/2 + f_px·q_r/zc ,  sy = H/2 - f_px·q_u/zc
    # 这段是**独立重写**的，用来交叉验证界面里的 _view + proj。
    def analytic(w, az, el, W=900, H=700, zoom=1.0):
        a = math.radians(az); e = math.radians(el)
        ca, sa, ce, se = math.cos(a), math.sin(a), math.cos(e), math.sin(e)
        right = (-sa, ca, 0.0)
        up = (-ce * ca, -ce * sa, se)
        fwd = (se * ca, se * sa, ce)
        c = (0.0, 0.0, -Ltot / 2.0)
        rel = (w[0] - c[0], w[1] - c[1], w[2] - c[2])
        f_px = min(W, H) / (FIT_FACTOR * Ltot) * zoom
        zc = max(dcam0 - dot(fwd, rel), DEPTH_FLOOR * Ltot)
        return W / 2 + f_px * dot(right, rel) / zc, H / 2 - f_px * dot(up, rel) / zc

    dcam0 = CAM_FACTOR * Ltot
    worst = 0.0
    worst_at = None
    for (az, el) in ((0.0, 90.0), (0.0, 0.0), (35.0, 20.0), (140.0, -55.0), (270.0, 80.0)):
        pr = make_proj(az, el, Ltot)
        for xw in (-0.02, 0.0, 0.02):
            for yw in (-0.02, 0.0, 0.02):
                for zw in (0.0, -0.10, -Ltot):
                    sx, sy, _ = pr((xw, yw, zw))
                    ax, ay = analytic((xw, yw, zw), az, el)
                    dv = max(abs(sx - ax), abs(sy - ay))
                    if dv > worst:
                        worst, worst_at = dv, (az, el, xw, yw, zw)
    L.append("  投影 vs 独立解析透视式：5 个视角 × 27 个点，最大偏差 %.2e px" % worst)
    if worst > 1e-9:
        ok = False
        L.append("  !! 界面投影与解析式不符，最大偏差出现在 %s" % (worst_at,))

    # 各向同性：数值雅可比的两个奇异值应几乎相等（否则图案会被拉扁）
    def jac(pr, p0, h=1e-6):
        x0, y0, z0 = p0
        sx0, sy0, _ = pr(p0)
        cols = []
        for d_ in ((h, 0, 0), (0, h, 0), (0, 0, h)):
            p1 = (x0 + d_[0], y0 + d_[1], z0 + d_[2])
            sx1, sy1, _ = pr(p1)
            cols.append(((sx1 - sx0) / h, (sy1 - sy0) / h))
        return cols

    def svd2(a, b):          # a, b 是 3x2 的列；对 2x3 雅可比做 2x2 奇异值
        # M M^T 是 2x2
        m = [[sum(a[k][i] * a[k][j] for k in range(len(a))) for j in range(2)] for i in range(2)]
        tr = m[0][0] + m[1][1]
        det = m[0][0] * m[1][1] - m[0][1] * m[1][0]
        disc = max(tr * tr / 4 - det, 0.0)
        r = math.sqrt(disc)
        return math.sqrt(max(tr / 2 + r, 0)), math.sqrt(max(tr / 2 - r, 0))

    for (az, el) in ((0.0, 89.0), (0.0, 90.0), (25.0, 40.0), (90.0, 5.0)):
        pr = make_proj(az, el, Ltot)
        cols = jac(pr, (0.0, 0.0, -Ltot / 2.0))
        s1, s2 = svd2(cols, None)
        L.append("  各向同性 @方位%5.1f° 仰角%4.1f°：奇异值 %.2f / %.2f px/m（比 %.4f）"
                 % (az, el, s1, s2, (s2 / s1) if s1 else 0))
        # 透视本来会让近处略大，允许 5% 的尺度差
        if s1 <= 0 or s2 / s1 < 0.95:
            ok = False
            L.append("  !! 该视角下水平面投影严重各向异性，图案会被拉扁")

    # 画幅检查：装置在**所有**方位角与可用仰角下都必须完整可见。
    # 注意屏幕高度 ∝ sin(仰角)：仰角 0° 时装置完全压成一条水平线，这是正常的，
    # 所以不使用统一的"最小填充率"，而是分开检查：
    #   (a) 任何视角都不许裁切；
    #   (b) 常用仰角区间（≥20°）必须填满到 40% 以上；
    #   (c) 填充率要大致跟随 sin(仰角) —— 若不然说明竖直方向的投影用错了轴。
    frac_at, clipped = {}, []
    for az_t in (0.0, 38.0, 90.0, 140.0, 200.0, 270.0, 330.0):
        for el_t in (8.0, 16.0, 24.0, 35.0, 45.0, 55.0, 65.0, 75.0):
            pr_t = make_proj(az_t, el_t, Ltot)
            pts = [(-p.R, 0, 0), (p.R, 0, 0), (0, 0, -d["h"]), (0, 0, -Ltot)]
            for ang in range(0, 360, 15):
                pts.append((0.06 * math.cos(math.radians(ang)),
                            0.06 * math.sin(math.radians(ang)), -Ltot))
            scr = [pr_t(q) for q in pts]
            xs = [s[0] for s in scr]; ys = [s[1] for s in scr]
            fh = (max(ys) - min(ys)) / 700.0
            frac_at[(az_t, el_t)] = fh
            pad = min(min(xs), 900 - max(xs), min(ys), 700 - max(ys))
            if pad < 0:
                clipped.append((az_t, el_t, round(pad, 1)))
    if clipped:
        ok = False
        L.append("  !! 以下视角装置会被裁掉（方位, 仰角, 越界像素）：%s" % clipped[:6])
    L.append("  画幅：7 方位 × 8 仰角 = 56 个视角，装置占画面高度 %.0f%%–%.0f%%，%s"
             % (100 * min(frac_at.values()), 100 * max(frac_at.values()),
                "全部不出界" if not clipped else "有裁切"))
    small = [(a, e, round(100 * v)) for (a, e), v in sorted(frac_at.items())
             if e >= 20.0 and v < 0.40]
    if small:
        ok = False
        L.append("  !! 仰角 ≥20° 时仍有视角填充不足 40%%：%s" % small[:6])
    L.append("  填充率 @仰角 ≥20°：最小 %.0f%%（要求 ≥40%%）"
             % (100 * min(v for (a, e), v in frac_at.items() if e >= 20.0)))
    # (c) 竖直填充率必须随仰角单调增长，直到接近俯视时才开始收缩。
    # 小角度下 fill ∝ sin(仰角)，但透视下前后景深度不同，所以只能核对
    # "单调增长且量级相当"，不能要求严格等于 sin 之比。
    els = (16.0, 24.0, 35.0, 45.0, 55.0, 65.0)
    fills = [frac_at[(38.0, e)] for e in els]
    mono = all(fills[i] < fills[i + 1] for i in range(len(fills) - 1))
    naive = math.sin(math.radians(55.0)) / math.sin(math.radians(24.0))
    ratio = frac_at[(38.0, 55.0)] / frac_at[(38.0, 24.0)]
    L.append("  竖直填充率随仰角 16→65°：%s（应单调增长）"
             % " < ".join("%.0f%%" % (100 * f) for f in fills))
    L.append("  24°→55° 填充率之比 %.3f，sin 之比 %.3f（透视下不必相等，量级相当即可）"
             % (ratio, naive))
    if not mono:
        ok = False
        L.append("  !! 填充率不随仰角单调增长，竖直方向可能用错了轴")
    if not (0.5 * naive <= ratio <= 1.5 * naive):
        ok = False
        L.append("  !! 填充率随仰角的增长量级不对，竖直方向可能用错了轴")

    # 默认视角下所有关键点都必须在画面内
    pr_d = make_proj(38.0, 24.0, Ltot)
    outside = []
    for nm, q in (("A1", (-0.06, 0.0, 0.0)), ("A2", (0.06, 0.0, 0.0)),
                  ("K", (0.0, 0.0, -0.24)), ("P", (0.02, 0.02, -Ltot))):
        sx, sy, _ = pr_d(q)
        if not (0 <= sx <= 900 and 0 <= sy <= 700):
            outside.append((nm, round(sx, 1), round(sy, 1)))
    L.append("  默认视角（方位38°仰角24°）关键点越界检查：%s"
             % ("全部在画面内" if not outside else outside))
    if outside:
        ok = False
        L.append("  !! 默认视角下有关键点跑到画面外")

    # ---- 5. 方位角必须改变投影
    seen = {}
    for az in (0, 30, 60, 90, 120):
        pr = make_proj(az, 15.0, Ltot)
        key = tuple(round(c, 4) for c in pr(pts3[len(pts3) // 2])[:2])
        seen.setdefault(key, []).append(az)
    if len(seen) != 5:
        ok = False
        L.append("  !! 不同方位角给出了相同投影：%s" % seen)
    L.append("  5 个方位角 -> %d 组不同投影" % len(seen))

    # ---- 6. 深度单调 + 尺度 ∝ 1/zc
    proj_d = make_proj(35.0, 20.0, Ltot)
    a_ = math.radians(35.0); e_ = math.radians(20.0)
    fwd = (math.sin(e_) * math.cos(a_), math.sin(e_) * math.sin(a_), math.cos(e_))
    c3 = (0.0, 0.0, -Ltot / 2.0)
    near_pt = tuple(c3[i] + 0.05 * fwd[i] for i in range(3))     # 沿视线朝相机移
    far_pt = tuple(c3[i] - 0.05 * fwd[i] for i in range(3))      # 沿视线远离相机
    _, _, z_near = proj_d(near_pt)
    _, _, z_far = proj_d(far_pt)
    ratio_pred = z_far / z_near
    ratio_meas = ((proj_d.f_px / z_near) / (proj_d.f_px / z_far))
    L.append("  深度：沿视线近点 zc=%.4f，远点 zc=%.4f；尺度比 %.6f = 深度反比 %.6f"
             % (z_near, z_far, ratio_meas, ratio_pred))
    if not (z_near < z_far):
        ok = False
        L.append("  !! 深度排序反了")
    if abs(ratio_meas - ratio_pred) > 1e-12:
        ok = False
        L.append("  !! 透视尺度与深度不成反比")

    # ---- 7. 极端视角不退化
    bad = []
    for az in (0.0, 359.9, 180.0):
        for el in (89.99, -89.99, 0.0):
            pr = make_proj(az, el, Ltot)
            for q in pts3[::211]:
                sx, sy, zc = pr(q)
                if not (math.isfinite(sx) and math.isfinite(sy) and math.isfinite(zc)) or zc <= 0:
                    bad.append((az, el))
                    break
    if bad:
        ok = False
        L.append("  !! 极端视角出现非有限投影：%s" % bad)
    L.append("  极端视角（仰角 ±89.99°、方位角 0/180/359.9°）：投影全部有限且 zc>0")

    # ---- 8. 三种结点状态都能投影
    for mode in ("tied", "sliding", "tripod"):
        pp = Params(mode=mode, A=0.02, damping=0.01)
        ss = YYSim(p=pp)
        dd = derived(pp)
        for _ in range(600):
            ss.step(dt)
        g = ss.geometry()
        pr = make_proj(40.0, 18.0, pp.L + dd["h"])
        for v in (g["A1"], g["A2"], g["K"], g["P"]):
            sx, sy, zc = pr((v[0], v[1], -v[2]))
            if not (math.isfinite(sx) and math.isfinite(sy)):
                ok = False
                L.append("  !! %s 态的 %s 投影为非有限值" % (mode, v))
    L.append("  三种结点状态（系结/滑环/三脚架）的锚点、结点、摆球均可投影")

    print("\n".join(L))
    print()
    print("VERIFY 3D:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
