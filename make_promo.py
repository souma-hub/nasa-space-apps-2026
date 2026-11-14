#!/usr/bin/env python3
"""30 秒プロモーション動画（試作）を作る。 docs/promo/README.md 参照。

使い方:  python make_promo.py      （uv なら: uv run --with pillow make_promo.py）
前提:    Windows（SAPI の英語音声）, ffmpeg/ffprobe が PATH にあること, Pillow
出力:    out/promo_draft.mp4（確認用に out/promo_cut1..6.png も出す）
"""
import subprocess, sys, wave, shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageStat

# ===== 原稿（差し替え可）=====================================
# 各カットの読み上げ文。字幕も同じ文を焼き込む。
NARRATION = [
    "We're Windfall Rice, tackling the Field Shift challenge.",
    "When a typhoon is forecast, many rice farmers in Japan harvest early, "
    "even before the grain is fully ripe, because there's no clear rule for when it's safe to wait.",
    "We built that rule from NASA data: GPM IMERG rainfall and NASA POWER wind and temperature.",
    'Tested on 23 past typhoons, it said "safe to wait" in 10 of 16 no-damage cases, missing 1 of 7.',
    "It even runs on a Raspberry Pi Pico.",
    "It shows when current crops are most vulnerable, and compares planting strategies.",
]
# MAX_TOTAL を超えたとき、カット 3 の読み上げをこれに置き換える（データ名は画面の文字のみ）
NARRATION_3_SHORT = "We built that rule from NASA data."
VOICE_HINT = ("Zira", "David", "Mark", "Hazel")   # 優先する英語の声
RATE = 0            # SAPI の話速（-10..10）。長すぎるときは自動で上げる（最大 RATE_MAX）
RATE_MAX = 3
MAX_TOTAL = 29.5    # 秒
VOICE_TAG = "Voice: AI-generated (TTS)"
COMMENT = "Narration: AI-generated text-to-speech (Windows SAPI)"
# ==============================================================

W, H, FPS = 1920, 1080, 30
XF = 0.30                 # クロスフェード秒
LEAD, TAIL = 0.15, 0.30   # フェード完了後に声が始まるまで / 声のあとの余白
PICO_MIN = 4.0            # カット 5 の LED 映像の長さ
BG, FG, ACC = "#fbfaf6", "#1d1b19", "#b3261e"

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "docs" / "promo" / "assets"
OUT = ROOT / "out"
WORK = OUT / "promo_work"
FD = Path("C:/Windows/Fonts")
SERIF, SERIF_B = "georgia.ttf", "georgiab.ttf"
SANS, SANS_SB = "segoeui.ttf", "seguisb.ttf"


def font(name, size):
    return ImageFont.truetype(str(FD / name), size)


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


# ---------- 音声（Windows SAPI）----------
PS = """
param($TextFile, $Out, $Rate, $Hints)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = @($s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'en-*' })
if ($voices.Count -eq 0) { [Console]::Error.WriteLine('NO_EN_VOICE'); exit 3 }
$pick = $null
foreach ($h in $Hints.Split(',')) {
  $pick = $voices | Where-Object { $_.VoiceInfo.Name -like "*$h*" } | Select-Object -First 1
  if ($pick) { break }
}
if (-not $pick) { $pick = $voices | Select-Object -First 1 }
$s.SelectVoice($pick.VoiceInfo.Name)
$s.Rate = [int]$Rate
$s.SetOutputToWaveFile($Out)
$s.Speak([IO.File]::ReadAllText($TextFile, [Text.Encoding]::UTF8))
$s.Dispose()
Write-Output $pick.VoiceInfo.Name
"""


def synth(texts, rate):
    WORK.mkdir(parents=True, exist_ok=True)
    ps1 = WORK / "tts.ps1"
    ps1.write_text(PS, encoding="utf-8-sig")
    wavs, voice = [], ""
    for i, t in enumerate(texts):
        tf, wf = WORK / f"t{i+1}.txt", WORK / f"v{i+1}.wav"
        tf.write_text(t, encoding="utf-8")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1),
                            "-TextFile", str(tf), "-Out", str(wf), "-Rate", str(rate),
                            "-Hints", ",".join(VOICE_HINT)], capture_output=True, text=True)
        if r.returncode != 0:
            return None, r.stderr.strip() or r.stdout.strip()
        voice = r.stdout.strip().splitlines()[-1]
        wavs.append(wf)
    return (wavs, voice), None


def wav_len(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


# ---------- 描画ヘルパ ----------
def cover(img, zoom=1.0, pan=(0.5, 0.5)):
    """W×H を覆うように拡大・クロップ。zoom>1 でゆっくりズーム。"""
    s = max(W / img.width, H / img.height) * zoom
    nw, nh = int(img.width * s + .5), int(img.height * s + .5)
    im = img.resize((nw, nh), Image.BILINEAR)
    x = int((nw - W) * pan[0])
    y = int((nh - H) * pan[1])
    return im.crop((x, y, x + W, y + H))


def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def text_center(d, xy, s, f, fill, shadow=False):
    x, y = xy
    if shadow:
        d.text((x + 3, y + 3), s, font=f, fill=(0, 0, 0, 170), anchor="mm")
    d.text((x, y), s, font=f, fill=fill, anchor="mm")


def subtitle(img, text):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f = font(SANS_SB, 44)
    lines = wrap(d, text, f, 1560)
    lh = 60
    bh = lh * len(lines) + 36
    y0 = H - 50 - bh
    d.rounded_rectangle((120, y0, W - 120, H - 50), 18, fill=(0, 0, 0, 175))
    for i, ln in enumerate(lines):
        d.text((W // 2, y0 + 18 + lh * i + lh // 2), ln, font=f, fill="white", anchor="mm")
    base = img.convert("RGBA")
    base.alpha_composite(ov)
    return base.convert("RGB")


def darken(img, a):
    return Image.blend(img, Image.new("RGB", (W, H), (0, 0, 0)), a)


# ---------- 各カットの画（t=カット内秒, p=0..1 進行度, d=カット長）----------
class Cuts:
    def __init__(self, pico_frames):
        self.field = Image.open(ASSETS / "field.jpg").convert("RGB")
        self.frog = Image.open(ASSETS / "frog.jpg").convert("RGB")
        self.demo = Image.open(ASSETS / "demo.png").convert("RGB")
        self.pico = pico_frames
        self.frog_bg = darken(cover(self.frog.filter(ImageFilter.GaussianBlur(30))), 0.35)

    def c1(self, t, p, d):
        im = darken(cover(self.field, 1.0 + 0.08 * p), 0.25)
        o = ImageDraw.Draw(im, "RGBA")
        text_center(o, (W // 2, 400), "Windfall Rice", font(SERIF_B, 120), "white", True)
        text_center(o, (W // 2, 530), "Field Shift challenge", font(SERIF, 70), "white", True)
        return im

    def c2(self, t, p, d):
        im = darken(cover(self.field, 1.08 + 0.05 * p, (0.3, 0.5)), 0.62)
        o = ImageDraw.Draw(im, "RGBA")
        text_center(o, (W // 2, 330), "Typhoon forecast", font(SERIF, 70), "white", True)
        text_center(o, (W // 2, 470), "Harvest now, or wait?", font(SERIF_B, 110), "white", True)
        text_center(o, (W // 2, 610), "No clear rule.", font(SERIF, 70), "#ffb4ab", True)
        return im

    def c3(self, t, p, d):
        im = Image.new("RGB", (W, H), BG)
        o = ImageDraw.Draw(im)
        text_center(o, (W // 2, 150), "Built from NASA data", font(SERIF_B, 76), FG)
        bw, bh = 700, 330
        for k, (a, b, c) in enumerate([("NASA GPM IMERG", "Rain", "satellite rainfall"),
                                      ("NASA POWER", "Wind & temperature", "weather data")]):
            x = W // 2 - bw - 60 if k == 0 else W // 2 + 60
            y = 260
            o.rounded_rectangle((x, y, x + bw, y + bh), 24, outline=FG, width=4, fill="white")
            text_center(o, (x + bw // 2, y + 80), a, font(SANS_SB, 52), FG)
            text_center(o, (x + bw // 2, y + 190), b, font(SERIF_B, 56 if k else 62), ACC)
            text_center(o, (x + bw // 2, y + 265), c, font(SANS, 38), "#5b5750")
        text_center(o, (W // 2, 650), "Inputs  \u2192  a clear rule for when it's safe to wait",
                    font(SANS, 44), FG)
        return im

    def c4(self, t, p, d):
        im = Image.new("RGB", (W, H), BG)
        o = ImageDraw.Draw(im)
        for cx, num, label in [(W // 2 - 420, "10 / 16", "safe to wait"), (W // 2 + 420, "1 / 7", "missed")]:
            text_center(o, (cx, 330), num, font(SERIF_B, 190), ACC)
            text_center(o, (cx, 490), label, font(SANS_SB, 60), FG)
        text_center(o, (W // 2, 660), "23 past typhoons", font(SANS, 48), "#5b5750")
        return im

    def c5(self, t, p, d):
        dm = 0.0 if d <= PICO_MIN + 0.05 else d - PICO_MIN   # 余った分は前半にデモ画面を見せる
        if t < dm:
            im = cover(self.demo, 1.0 + 0.03 * (t / max(dm, .01)))
        else:
            i = min(int((t - dm) * FPS), len(self.pico) - 1)
            im = cover(self.pico[i])
        o = ImageDraw.Draw(im, "RGBA")
        text_center(o, (W // 2, 90), "Runs on a laptop or a Raspberry Pi Pico", font(SERIF_B, 62), "white", True)
        return im

    def c6(self, t, p, d):
        im = self.frog_bg.copy()
        ph = int(940 * (1 + 0.04 * p))
        fw = int(self.frog.width * ph / self.frog.height)
        fr = self.frog.resize((fw, ph), Image.BILINEAR)
        cw = min(fw, 700)
        fr = fr.crop(((fw - cw) // 2, (ph - 940) // 2, (fw + cw) // 2, (ph - 940) // 2 + 940))
        im.paste(fr, ((W - fr.width) // 2, 40))
        o = ImageDraw.Draw(im, "RGBA")
        for k, s in enumerate(["NASA data for", "harvest decision", "support"]):
            text_center(o, (310, 400 + 76 * k), s, font(SERIF_B, 56), "white", True)
        o.text((W - 40, 40), VOICE_TAG, font=font(SANS, 28), fill=(255, 255, 255, 235), anchor="ra")
        return im


def pico_window():
    """pico_led.mp4 から 点灯→消灯 が映る約 4 秒を切り出して PIL 画像列で返す。"""
    pd = WORK / "pico_all"
    if pd.exists():
        shutil.rmtree(pd)
    pd.mkdir(parents=True)
    run(["ffmpeg", "-v", "error", "-i", str(ASSETS / "pico_led.mp4"), "-vf", f"fps={FPS}", str(pd / "%04d.png")])
    files = sorted(pd.glob("*.png"))
    br = []  # 基板上の LED 付近にある黄緑の明るい画素数（点灯で数百、消灯で数十）
    for f in files:
        im = Image.open(f).convert("RGB")
        w, h = im.size
        c = im.crop((int(.24 * w), int(.55 * h), int(.34 * w), int(.72 * h))).resize((60, 60))
        br.append(sum(1 for r, g, b in c.get_flattened_data() if g > 200 and b < g - 70))
    lo, hi = min(br), max(br)
    on = [b > (lo + hi) / 2 for b in br]
    trans = [i for i in range(1, len(on)) if on[i - 1] and not on[i]]
    if not trans:
        sys.exit("点灯→消灯の切り替わりが見つからない")
    n = int(PICO_MIN * FPS)
    t = trans[0]
    s = max(0, min(t - n // 2, len(files) - n))
    print(f"pico: 消灯への切替フレーム={t} ({t/FPS:.2f}s), 使用 {s/FPS:.2f}s-{(s+n)/FPS:.2f}s, LED画素数 {lo}-{hi}")
    return [Image.open(f).convert("RGB") for f in files[s:s + n]]


def plan(auds):
    ds = [LEAD + XF + a + TAIL for a in auds]
    ds[4] = max(ds[4], PICO_MIN)
    ds[5] += 0.4   # 最後は少し余韻（Voice 表示）
    starts = [0.0]
    for d in ds[:-1]:
        starts.append(starts[-1] + d - XF)
    return ds, starts, starts[-1] + ds[-1]


def main():
    OUT.mkdir(exist_ok=True)
    texts = list(NARRATION)
    rate, shortened = RATE, False
    while True:
        res, err = synth(texts, rate)
        if res is None:
            print("英語の声が使えない:", err)
            sys.exit(3)
        wavs, voice = res
        auds = [wav_len(w) for w in wavs]
        ds, starts, total = plan(auds)
        print(f"rate={rate} short3={shortened} total={total:.2f}s auds={[round(a, 2) for a in auds]}")
        if total <= MAX_TOTAL:
            break
        if not shortened:
            texts[2] = NARRATION_3_SHORT
            shortened = True
        elif rate < RATE_MAX:
            rate += 1
        else:
            print("話速を上げても収まらない")
            sys.exit(4)

    # 音声トラックを結合（各カットの フェード完了 + LEAD に声を置く）
    with wave.open(str(wavs[0])) as w:
        params = w.getparams()
    sr, sw, ch = params.framerate, params.sampwidth, params.nchannels
    buf = bytearray(int(total * sr + sr) * sw * ch)
    for wf, st in zip(wavs, starts):
        with wave.open(str(wf)) as w:
            data = w.readframes(w.getnframes())
        off = int((st + (XF if st > 0 else 0) + LEAD) * sr) * sw * ch
        buf[off:off + len(data)] = data
    mix = WORK / "narration.wav"
    with wave.open(str(mix), "wb") as w:
        w.setparams(params)
        w.writeframes(bytes(buf))

    cuts = Cuts(pico_window())
    fns = [cuts.c1, cuts.c2, cuts.c3, cuts.c4, cuts.c5, cuts.c6]
    nframes = int(round(total * FPS))
    silent = WORK / "video_silent.mp4"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                            "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)

    def frame_of(k, t):
        return subtitle(fns[k](t, t / ds[k], ds[k]), texts[k])

    for fi in range(nframes):
        T = fi / FPS
        act = [k for k in range(6) if starts[k] <= T < starts[k] + ds[k]] or [5]
        k = act[-1]
        im = frame_of(k, T - starts[k])
        if len(act) > 1:  # クロスフェード
            a = frame_of(act[0], T - starts[act[0]])
            im = Image.blend(a, im, (T - starts[k]) / XF)
        enc.stdin.write(im.tobytes())
    enc.stdin.close()
    enc.wait()

    for k in range(6):  # 確認用: 各カット中央のフレーム
        frame_of(k, ds[k] / 2).save(OUT / f"promo_cut{k+1}.png")

    final = OUT / "promo_draft.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-i", str(mix), "-map_metadata", "-1",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.3f}",
         "-metadata", f"comment={COMMENT}", "-movflags", "+faststart", str(final)])
    print("voice:", voice)
    for k in range(6):
        print(f"cut{k+1}: start {starts[k]:.2f}s  dur {ds[k]:.2f}s  audio {auds[k]:.2f}s")
    print(f"total {total:.2f}s -> {final}")


if __name__ == "__main__":
    main()
