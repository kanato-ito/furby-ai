"""PAM8403 版 音声出力回路図を描く

実行: python3 docs/draw_audio_circuit.py docs/audio_circuit.png（matplotlib と macOS のヒラギノフォントが必要）
"""
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle

plt.rcParams['font.family'] = 'Hiragino Sans'

RED, BLUE, GRAY, ORANGE, PURPLE, GREEN = '#c62828', '#0d47a1', '#424242', '#ef6c00', '#6a1b9a', '#2e7d32'
fig, ax = plt.subplots(figsize=(20, 12.6), dpi=121)
ax.set_xlim(0, 20)
ax.set_ylim(0, 12.6)
ax.axis('off')
fig.patch.set_facecolor('#fafafa')


def wire(xs, ys, c=GRAY, lw=3):
    ax.plot(xs, ys, color=c, lw=lw, solid_capstyle='round', zorder=1)


def dot(x, y, c=GRAY):
    ax.plot(x, y, 'o', color=c, ms=11, zorder=3)


def text(x, y, s, c=GRAY, size=14, **kw):
    ax.text(x, y, s, color=c, fontsize=size, ha='center', va='center', zorder=4, **kw)


def ground(x, y):
    wire([x, x], [y, y - 0.3])
    for i, w in enumerate((0.4, 0.25, 0.1)):
        wire([x - w, x + w], [y - 0.3 - i * 0.18] * 2, lw=3)


text(10, 12.1, 'ファービーAI 音声出力回路（PAM8403 アンプ）', '#1a237e', 22, weight='bold')

# Raspberry Pi
Y5V, YSIG, YGND = 10.0, 6.5, 2.6
ax.add_patch(FancyBboxPatch((0.25, 2.0), 3.6, 8.9, boxstyle='round,pad=0.05,rounding_size=0.15',
                            fc='#e8f5e9', ec=GREEN, lw=3))
text(2.05, 11.35, 'Raspberry Pi\nZero 2W', GREEN, 16)
for y, label, c in ((Y5V, '2番ピン\n5V（電源）', RED), (YSIG, '32番ピン\nGPIO 12（PWM 音声）', BLUE),
                    (YGND, '6番ピン\nGND', GRAY)):
    text(1.95, y, label, c, 13)
    ax.add_patch(Rectangle((3.72, y - 0.13), 0.26, 0.26, color=c, zorder=3))

# PAM8403
PX0, PX1, PY0, PY1 = 12.2, 15.6, 3.6, 10.6
ax.add_patch(Rectangle((PX0, PY0), PX1 - PX0, PY1 - PY0, fc='#ede7f6', ec=PURPLE, lw=3))
text((PX0 + PX1) / 2, 7.75, 'PAM8403\nアンプモジュール', PURPLE, 17, weight='bold')
YIN = YSIG
for y, label in ((Y5V, 'VCC (+)'), (YIN, 'L_IN'), (4.2, 'GND (−)')):
    text(PX0 + 0.75, y + 0.35, label, PURPLE, 12)
YOP, YOM = 8.6, 5.6
for y, label in ((YOP, 'L_OUT+'), (YOM, 'L_OUT−')):
    text(PX1 - 0.75, y + 0.35, label, PURPLE, 12)

# 5V → VCC
wire([3.98, PX0], [Y5V, Y5V], RED, 4)

# GND レール
wire([3.98, 13.0], [YGND, YGND], GRAY, 4)
wire([13.0, 13.0], [YGND, PY0], GRAY, 3)
wire([PX0, 13.0], [4.2, 4.2], GRAY, 3)
dot(13.0, YGND)
ground(13.0, YGND)

# GPIO12 → R1(1kΩ) → ノード → C2(10μF) → L_IN
wire([3.98, 5.0], [YSIG, YSIG])
ax.add_patch(Rectangle((5.0, YSIG - 0.45), 2.0, 0.9, fc='#fff8e1', ec=ORANGE, lw=3, zorder=2))
text(6.0, YSIG, '1kΩ', ORANGE, 15)
text(6.0, YSIG + 0.75, 'R1', RED, 12)
NX = 8.0
wire([7.0, 9.5], [YSIG, YSIG])
dot(NX, YSIG)
# C1 100nF（ノード → GND）
wire([NX, NX], [YSIG, 4.6])
wire([NX - 0.6, NX + 0.6], [4.6, 4.6], BLUE, 6)
wire([NX - 0.6, NX + 0.6], [4.25, 4.25], BLUE, 6)
wire([NX, NX], [4.25, YGND])
dot(NX, YGND)
text(NX + 1.75, 4.42, '100nF（104）\nC1', BLUE, 12)
# C2 10μF 電解（+ が左）
wire([9.5, 9.5], [YSIG - 0.5, YSIG + 0.5], BLUE, 6)
ax.add_patch(Polygon([(9.85, YSIG - 0.5), (9.85, YSIG + 0.5)], closed=False, ec=BLUE, lw=6))
ax.plot([9.85, 9.85], [YSIG - 0.5, YSIG + 0.5], color=BLUE, lw=6)
text(9.2, YSIG + 0.75, '+', BLUE, 18, weight='bold')
text(9.68, YSIG - 1.0, '10μF 電解\nC2（+ を左＝GPIO 側）', BLUE, 12)
wire([9.85, PX0], [YIN, YIN])

text(6.4, 8.0, 'RC ローパスフィルタ\n（PWM のノイズを減らす）', '#5d4037', 12)
text(10.9, 8.0, 'AC 結合\n（直流をカット）', '#5d4037', 12)

# スピーカー
SX = 17.9
wire([PX1, SX], [YOP, YOP], RED, 3)
wire([PX1, SX], [YOM, YOM], GRAY, 3)
wire([SX, SX], [YOP, 7.6], RED, 3)
wire([SX, SX], [YOM, 6.6], GRAY, 3)
ax.add_patch(Rectangle((SX - 0.3, 6.6), 0.6, 1.0, color=PURPLE, zorder=2))
ax.add_patch(Polygon([(SX + 0.3, 6.6), (SX + 1.1, 6.15), (SX + 1.1, 8.05), (SX + 0.3, 7.6)], color=PURPLE, zorder=2))
text(SX + 0.45, 5.0, 'ファービー純正\nスピーカー（約 32Ω）', PURPLE, 13)
text(SX - 0.55, 7.9, '+', RED, 15, weight='bold')
text(SX - 0.55, 6.3, '−', GRAY, 15, weight='bold')

# 注意書き
ax.add_patch(FancyBboxPatch((0.3, 0.15), 19.4, 1.25, boxstyle='round,pad=0.02,rounding_size=0.1',
                            fc='#fffde7', ec='#fbc02d', lw=2.5))
text(10, 1.0, '[!] PAM8403 の VCC−GND 間には追加のコンデンサを入れない（実機で逆効果と確認）'
              '　　L_OUT− は GND につながない（BTL 出力）', '#5d4037', 13)
text(10, 0.5, '/boot/firmware/config.txt: dtparam=audio=on と dtoverlay=audremap（PWM 音声を GPIO 12/13 へ）'
              '　　詳細は 基本設計書 §3.5.1', '#5d4037', 12)

fig.savefig(sys.argv[1], facecolor=fig.get_facecolor(), bbox_inches='tight', pad_inches=0.2)
