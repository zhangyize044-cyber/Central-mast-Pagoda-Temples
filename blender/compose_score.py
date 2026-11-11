# -*- coding: utf-8 -*-
"""为 22 s 展示短片合成原创配乐（无外部音源、无版权风险）。

本机系统 Python 没装 numpy，但 Blender 4.4 内置 numpy 1.26，故用：
    blender -b --python model/compose_score.py
输出 48 kHz / 16-bit / stereo WAV，严格 22.000 s（528 帧 @ 24 fps）。

对位依据 deliverables/animation-beats.json：
  BPM 90 → 拍长 2/3 s；以 t = 1/6 s 为第 0 拍，则
  3.5 s = 第 5 拍、11.5 s = 第 17 拍，两个硬重音正好落在小节线上。
  画面事件：0.58–1.42 s 八根扒梁、4.0–7.2 s 九级点灯（每 0.4 s）、
  12.0–14.45 s 八根扒梁（每 0.35 s）、19.5 s 落版。

音色全部程序化：钟磬（非谐波泛音 + 金属起音）、鼓（pitch sweep + 低通噪声）、
木构点击（噪声 + 共振峰）、弦垫（谐波叠加 + chorus）、合成混响（FFT 卷积）。
"""
import os
import math
import wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.environ.get(
    "SCORE_OUT",
    os.path.join(ROOT, "deliverables", "13-配乐-正定凌霄塔.wav"))

SR = 48000
DUR = 22.0
N = int(SR * DUR)
BEAT = 60.0 / 90.0          # 0.666667 s
GRID = 1.0 / 6.0            # 0.166667 s，使 3.5 / 11.5 落在整拍

L = np.zeros(N, dtype=np.float64)
R = np.zeros(N, dtype=np.float64)


def add(t0, sig, gain=1.0, pan=0.0):
    """把一段单声道信号按等功率声像混入 L/R。"""
    i = int(round(t0 * SR))
    if i < 0 or i >= N:
        return
    j = min(N, i + len(sig))
    s = sig[:j - i] * gain
    a = (pan + 1.0) * math.pi / 4.0
    L[i:j] += s * math.cos(a)
    R[i:j] += s * math.sin(a)


def _norm(x, amp=1.0):
    m = np.max(np.abs(x)) + 1e-12
    return x / m * amp


def bell(f0, dur, amp=1.0, bright=1.0, seed=0):
    """钟 / 磬：非谐波泛音组，各自独立衰减，带金属起音与轻微拍频。"""
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    ratios = [0.50, 1.00, 1.19, 1.56, 2.00, 2.66, 3.01, 4.15, 5.43]
    amps = [0.52, 1.00, 0.44, 0.31, 0.33, 0.19, 0.15, 0.09, 0.05]
    decs = [2.6, 2.0, 2.9, 3.3, 3.7, 5.1, 5.7, 7.6, 9.2]
    out = np.zeros(n)
    for r, a, d in zip(ratios, amps, decs):
        det = 1.0 + rng.uniform(-0.0016, 0.0016)
        out += a * np.sin(2 * np.pi * f0 * r * det * t
                          + rng.uniform(0, 2 * np.pi)) * np.exp(-d * t)
    atk = rng.normal(0, 1, n) * np.exp(-t * 240.0) * 0.16 * bright
    out = (out + atk) * np.clip(t / 0.0025, 0, 1)
    return _norm(out, amp)


def drum(f0=95.0, dur=1.6, amp=1.0, seed=0):
    """鼓：95→46 Hz 的下滑基音 + 低通噪声鼓皮瞬态。"""
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    f = 46.0 + (f0 - 46.0) * np.exp(-t * 22.0)
    phase = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(phase) * np.exp(-t * 4.0)
    rng = np.random.default_rng(seed)
    k = np.ones(20) / 20.0
    lp = np.convolve(rng.normal(0, 1, n), k, mode="same")
    atk = lp * np.exp(-t * 34.0) * 0.60
    out = (body * 0.95 + atk) * np.clip(t / 0.0015, 0, 1)
    return _norm(out, amp)


def wood(dur=0.10, amp=1.0, pitch=1.0, seed=0):
    """木构 / 榫卯咬合：噪声瞬态 + 三个衰减共振峰。"""
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 1, n) * np.exp(-t * 85.0)
    tone = np.zeros(n)
    for f, a in [(420.0, 1.0), (790.0, 0.55), (1310.0, 0.28)]:
        tone += a * np.sin(2 * np.pi * f * pitch * t) * np.exp(-t * 52.0)
    out = 0.42 * noise + 0.58 * tone / 1.83
    out *= np.clip(t / 0.0008, 0, 1)
    return _norm(out, amp)


def pad(freqs, dur, amp=1.0, attack=0.8, release=1.2, seed=0):
    """低音弦垫：谐波叠加 + 轻微 chorus + 慢速起伏。"""
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    for f in freqs:
        for h, ha in [(1, 1.0), (2, 0.30), (3, 0.13), (4, 0.055)]:
            det = f * h * (1.0 + rng.uniform(-0.0012, 0.0012))
            out += ha * np.sin(2 * np.pi * det * t + rng.uniform(0, 2 * np.pi))
    out /= (len(freqs) * 1.485)
    e = np.clip(t / attack, 0, 1) * np.clip((dur - t) / release, 0, 1)
    out *= e ** 1.3
    out *= 1.0 + 0.055 * np.sin(2 * np.pi * 0.33 * t)
    return out * amp


def riser(dur, amp=1.0, seed=0):
    """极轻的低通噪声上扬，只用来给硬切前蓄力。"""
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    k = np.ones(28) / 28.0
    x = np.convolve(rng.normal(0, 1, n), k, mode="same")
    e = (t / dur) ** 2.4
    return _norm(x * e, amp)


# ── 音高：D 宫五声 ──────────────────────────────────────────────────────
D2, A2, D3, FS3, A3 = 73.42, 110.00, 146.83, 185.00, 220.00
PENTA = [293.66, 329.63, 369.99, 440.00, 493.88,
         587.33, 659.26, 739.99, 880.00]          # D4 → A5 九级上行

# 01 起 · 结构 Reveal（0–3.5 s）：留白，只给结构显形的耳语
add(0.20, bell(880.0, 1.1, 0.075, 1.1, 1), pan=0.05)
for i in range(8):                                  # 0.58–1.42 s 八根扒梁
    t = 0.58 + i * 0.12
    add(t, wood(0.085, 0.052 + 0.010 * i, 1.0 + 0.035 * i, 10 + i),
        pan=0.22 if i % 2 == 0 else -0.22)
add(1.60, bell(D3, 3.2, 0.105, 0.8, 30), pan=-0.08)   # 外壳显形
add(1.60, pad([D2, A2, D3, FS3], 8.0, 0.062, 1.15, 1.6, 40), pan=0.0)
add(2.40, riser(1.05, 0.045, 50), pan=0.0)             # 硬切前蓄力

# 02 重音 ①（3.5 s）：鼓 + 低钟，硬起不渐入
add(3.50, drum(95.0, 1.7, 0.86, 60))
add(3.50, bell(D2, 3.6, 0.55, 1.0, 61), pan=-0.06)
add(3.50, bell(A3, 2.1, 0.19, 1.2, 62), pan=0.14)

# 90 BPM 拍点（第 5 拍 = 3.5 s 起，第 26 拍 = 17.5 s 收）
for k in range(5, 27):
    t = GRID + k * BEAT
    if t >= 19.0:
        break
    g = 0.055
    if 8.0 <= t < 11.5:
        g = 0.032                                   # 斗拱特写让位给画面
    if t >= 16.0:
        g *= max(0.25, 1.0 - (t - 16.0) / 3.5)     # 16 s 后渐收
    add(t, wood(0.07, g, 0.72, 100 + k), pan=0.10 if k % 2 else -0.10)

# 03 递 · 逐层点灯（4.0–7.2 s，每 0.4 s 一记上行磬）
for i, f in enumerate(PENTA):
    t = 4.0 + i * 0.4
    add(t, bell(f, 1.35, 0.105 + 0.011 * i, 1.0 + 0.03 * i, 200 + i),
        pan=0.16 if i % 2 else -0.16)
add(8.00, bell(1174.66, 1.6, 0.115, 1.35, 220), pan=0.10)  # 宝珠收亮

# 04 动 · 推近斗拱（8.0–11.5 s）：只留弦垫与稀疏拍点
add(8.00, pad([D2, A2, D3], 4.2, 0.048, 0.7, 1.3, 230), pan=-0.05)
add(11.00, riser(0.48, 0.038, 240), pan=0.0)

# 05 重音 ②（11.5 s）：更低更厚，比 ① 多一层
add(11.50, drum(110.0, 2.0, 1.00, 250))
add(11.50, bell(D2, 4.2, 0.68, 0.95, 251), pan=-0.08)
add(11.50, bell(FS3, 2.6, 0.22, 1.1, 252), pan=0.18)

# 06 递 · 扒梁（12.0–14.45 s，每 0.35 s 一记木构点击，渐强）
for i in range(8):
    t = 12.0 + i * 0.35
    add(t, wood(0.11, 0.10 + 0.020 * i, 0.92 + 0.02 * i, 260 + i),
        pan=0.26 if i % 2 == 0 else -0.26)
    if i % 2 == 0:
        add(t, bell(PENTA[i // 2 + 2], 0.9, 0.055, 0.9, 270 + i), pan=-0.12)

# 07 放 · 回到全景（16.0 s）：最后一次宽和声，之后不再加新元素
add(16.00, pad([D2, A2, D3, FS3, A3], 3.6, 0.105, 0.55, 1.7, 280), pan=0.0)
add(16.00, bell(A3, 2.8, 0.21, 1.0, 281), pan=0.12)
add(16.00, bell(293.66, 2.2, 0.115, 1.15, 282), pan=-0.14)

# 08 收 · 落版（19.5 s）：一记长钟，其余退场
add(19.50, bell(D2, 3.4, 0.30, 0.75, 290), pan=0.0)
add(19.50, pad([D2, A2], 2.6, 0.052, 0.15, 2.1, 291), pan=0.0)

# ── 合成混响（FFT 卷积，湿声按 RMS 与干声配平） ─────────────────────────
def make_ir(dur=1.8, seed=999):
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    ir = rng.normal(0, 1, n) * np.exp(-t * 4.6)
    for d, a in [(0.019, 0.55), (0.033, 0.38), (0.057, 0.29), (0.083, 0.20)]:
        ir[int(d * SR)] += a
    ir = np.convolve(ir, np.ones(12) / 12.0, mode="same")
    return ir


IR = make_ir()


def reverb(x, wet=0.20):
    size = 1 << (len(x) + len(IR) - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(IR, size), size)[:len(x)]
    rms_x = np.sqrt(np.mean(x ** 2)) + 1e-12
    rms_y = np.sqrt(np.mean(y ** 2)) + 1e-12
    return (1 - wet) * x + wet * y * (rms_x / rms_y)


L = reverb(L)
R = reverb(R)

# 软限幅 + 全局淡入淡出（21.2–22.0 s 收干净）
peak = max(np.max(np.abs(L)), np.max(np.abs(R))) + 1e-12
L, R = L / peak, R / peak
L = np.tanh(1.15 * L) / np.tanh(1.15)
R = np.tanh(1.15 * R) / np.tanh(1.15)
t = np.arange(N) / SR
fade = np.clip(t / 0.06, 0, 1) * np.clip((DUR - t) / 0.80, 0, 1)
L *= fade * 0.89
R *= fade * 0.89

# 写 16-bit stereo WAV
os.makedirs(os.path.dirname(OUT), exist_ok=True)
pcm = np.empty(N * 2, dtype=np.int16)
pcm[0::2] = np.clip(L * 32767, -32768, 32767).astype(np.int16)
pcm[1::2] = np.clip(R * 32767, -32768, 32767).astype(np.int16)
with wave.open(OUT, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())

# ── 数值复核 ────────────────────────────────────────────────────────────
def rms(a, b):
    s = (L[int(a * SR):int(b * SR)] + R[int(a * SR):int(b * SR)]) / 2
    return float(np.sqrt(np.mean(s ** 2)))

print("SCORE_OK file=%s bytes=%d sr=%d dur=%.3fs" %
      (OUT, os.path.getsize(OUT), SR, N / SR))
print("SCORE_LEVEL peak=%.4f rms_all=%.4f clipped=%d" %
      (max(np.max(np.abs(L)), np.max(np.abs(R))),
       rms(0, DUR), int(np.sum(np.abs(L) >= 0.999) + np.sum(np.abs(R) >= 0.999))))
print("SCORE_ACCENT pre1(3.2-3.5)=%.4f hit1(3.5-3.8)=%.4f | "
      "pre2(11.2-11.5)=%.4f hit2(11.5-11.8)=%.4f" %
      (rms(3.2, 3.5), rms(3.5, 3.8), rms(11.2, 11.5), rms(11.5, 11.8)))
print("SCORE_SECTIONS", " ".join("%.1f-%.1f:%.4f" % (a, b, rms(a, b))
                                 for a, b in [(0, 3.5), (3.5, 8), (8, 11.5),
                                              (11.5, 16), (16, 19.5), (19.5, 22)]))
