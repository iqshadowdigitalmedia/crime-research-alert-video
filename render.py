import asyncio
import glob
import math
import os
import random
import re
import subprocess
from functools import lru_cache

import edge_tts
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1280, 720, 12
VOICE = "hi-IN-MadhurNeural"   # पुरुष की हिंदी आवाज़
RATE = "-8%"                   # धीमी और साफ़ आवाज़ (और धीमा करना हो तो "-15%")
PAD = 0.6                      # हर स्लाइड के बाद रुकने का समय
CHUNK = 140                    # एक स्लाइड में अधिकतम अक्षर
BRAND = "IQ SHADOW DIGITAL MEDIA"          # ऊपर का नाम-टैग (बदल सकते हैं)
FOOTER_PARTS = ["साइबर जागरूकता", "सतर्क रहें", "सुरक्षित रहें"]
OUTRO_TITLE = "धन्यवाद"
OUTRO_SPEECH = "देखने के लिए धन्यवाद। जागरूक रहें, सतर्क रहें, सुरक्षित रहें।"  # खाली "" करने पर अंत की स्लाइड नहीं बनेगी
ACCENT = (255, 193, 7)
OUT_DIR, TMP = "output", "tmp"
BW, BH = int(W * 1.12), int(H * 1.12)      # पैन के लिए थोड़ा बड़ा बैकग्राउंड
SPW, SPH = 300, 375                        # प्रेज़ेंटर का आकार


# ---------------- फ़ॉन्ट और टेक्स्ट ----------------
@lru_cache(maxsize=None)
def get_font(size, bold, dev):
    if dev:
        names = ["NotoSansDevanagari-Bold.ttf" if bold else "NotoSansDevanagari-Regular.ttf",
                 "NotoSansDevanagari*.ttf", "*Devanagari*.ttf"]
    else:
        names = ["NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf",
                 "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    path = None
    for n in names:
        found = glob.glob(f"/usr/share/fonts/**/{n}", recursive=True)
        if found:
            path = found[0]
            break
    if not path:
        if dev:
            raise SystemExit("देवनागरी फ़ॉन्ट नहीं मिला")
        return get_font(size, bold, True)
    if dev:
        try:
            return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
        except Exception:
            pass
    return ImageFont.truetype(path, size)


def is_dev(ch):
    return "\u0900" <= ch <= "\u097f" or ch in "\u200c\u200d\u25cc"


def split_runs(text):
    runs, cur, cur_dev = [], "", None
    for ch in text:
        if ch == " ":
            cur += ch
            continue
        dev = is_dev(ch)
        if cur_dev is None:
            cur_dev = dev
        if dev != cur_dev:
            runs.append((cur, cur_dev))
            cur, cur_dev = "", dev
        cur += ch
    if cur:
        runs.append((cur, True if cur_dev is None else cur_dev))
    return runs


def tw(d, text, size, bold=False):
    return sum(d.textlength(t, font=get_font(size, bold, dev)) for t, dev in split_runs(text))


def draw_text(d, x, y, text, size, fill, bold=False):
    base = y + int(size * 0.95)
    for t, dev in split_runs(text):
        f = get_font(size, bold, dev)
        d.text((x, base), t, font=f, fill=fill, anchor="ls")
        x += d.textlength(t, font=f)


def wrap(d, text, size, bold, max_w):
    lines, cur = [], ""
    for word in text.split():
        test = (cur + " " + word).strip()
        if tw(d, test, size, bold) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ---------------- आर्टिकल ----------------
def read_article():
    with open("article.txt", encoding="utf-8") as f:
        lines = [l.strip() for l in f.read().splitlines() if l.strip()]
    if not lines:
        raise SystemExit("article.txt खाली है")
    return lines[0], " ".join(lines[1:])


def make_chunks(text):
    sentences = [s for s in re.split(r"(?<=[।.!?])\s+", text.strip()) if s]
    chunks, cur = [], ""
    for s in sentences:
        if len(s) > CHUNK:
            if cur:
                chunks.append(cur)
                cur = ""
            piece = ""
            for w in s.split():
                if len(piece) + len(w) + 1 > CHUNK:
                    chunks.append(piece)
                    piece = w
                else:
                    piece = (piece + " " + w).strip()
            if piece:
                chunks.append(piece)
        elif len(cur) + len(s) + 1 <= CHUNK:
            cur = (cur + " " + s).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = s
    if cur:
        chunks.append(cur)
    return chunks


# ---------------- बैकग्राउंड ----------------
def cover(im, w, h):
    s = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def vignette_mask():
    m = Image.new("L", (BW, BH), 0)
    ImageDraw.Draw(m).rectangle((100, 80, BW - 100, BH - 80), fill=255)
    return m.filter(ImageFilter.GaussianBlur(120))


def finish(im, mask):
    im = Image.blend(im, Image.new("RGB", im.size, (4, 14, 38)), 0.4)
    return Image.composite(im, Image.new("RGB", im.size, (0, 0, 0)), mask)


def cyber_bg(seed):
    rnd = random.Random(seed)
    bg = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        d.line((0, y, W, y), fill=(8, 18 + 25 * y // H, 45 + 50 * y // H))
    for x in range(0, W, 80):
        d.line((x, 0, x, H), fill=(18, 55, 95))
    for y in range(0, H, 80):
        d.line((0, y, W, y), fill=(18, 55, 95))
    pts = [(rnd.randrange(0, W, 80), rnd.randrange(0, H, 80)) for _ in range(14)]
    for a, b in zip(pts, pts[1:]):
        d.line([a, (b[0], a[1]), b], fill=(0, 190, 220), width=3)
    for p in pts:
        d.ellipse((p[0] - 7, p[1] - 7, p[0] + 7, p[1] + 7), fill=(0, 220, 255))
    cx, cy = 1070, 170
    d.arc((cx - 45, cy - 60, cx + 45, cy + 30), 180, 360, fill=(0, 220, 255), width=12)
    d.rounded_rectangle((cx - 70, cy - 20, cx + 70, cy + 80), radius=14, fill=(0, 190, 220))
    d.ellipse((cx - 12, cy + 12, cx + 12, cy + 36), fill=(8, 30, 60))
    d.rectangle((cx - 5, cy + 30, cx + 5, cy + 58), fill=(8, 30, 60))
    return bg


def load_backgrounds():
    mask = vignette_mask()
    exts = (".jpg", ".jpeg", ".png", ".webp")
    files = []
    for folder in (".", "images"):
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if name.lower().endswith(exts):
                    files.append(os.path.join(folder, name))
    bigs = []
    for f in files:
        try:
            bigs.append(finish(cover(Image.open(f).convert("RGB"), BW, BH), mask))
        except Exception as e:
            print("तस्वीर छोड़ी:", f, e)
    if not bigs:
        bigs = [finish(cyber_bg(s).resize((BW, BH), Image.LANCZOS), mask) for s in range(4)]
    return bigs, len(files)


def crop_bg(big, t):
    x = int((BW - W) * (0.5 + 0.5 * math.sin(t * 0.15)))
    y = int((BH - H) * (0.5 + 0.5 * math.cos(t * 0.11)))
    return big.crop((x, y, x + W, y + H))


# ---------------- प्रेज़ेंटर ----------------
def draw_presenter(mouth, blink):
    s = 2
    img = Image.new("RGBA", (400 * s, 500 * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def P(*v):
        return [int(x * s) for x in v]

    def pts(*p):
        return [(int(x * s), int(y * s)) for x, y in p]

    SKIN, SKIN_D = (226, 175, 138), (190, 136, 100)
    SUIT, SUIT_L, SUIT_D = (28, 45, 85), (44, 68, 118), (16, 28, 55)
    HAIR, WHITE, TIE = (38, 32, 30), (246, 248, 251), (232, 170, 20)
    FRAME = (34, 34, 42)

    # धड़, गर्दन, कमीज़, कोट के कॉलर और टाई
    d.rounded_rectangle(P(40, 285, 360, 640), radius=int(90 * s), fill=SUIT)
    d.rectangle(P(172, 205, 228, 292), fill=SKIN_D)
    d.polygon(pts((160, 272), (240, 272), (200, 420)), fill=WHITE)
    d.polygon(pts((150, 268), (200, 420), (145, 440), (100, 310)), fill=SUIT_L)
    d.polygon(pts((250, 268), (200, 420), (255, 440), (300, 310)), fill=SUIT_L)
    d.line(pts((150, 268), (200, 420)), fill=SUIT_D, width=int(3 * s))
    d.line(pts((250, 268), (200, 420)), fill=SUIT_D, width=int(3 * s))
    d.polygon(pts((190, 296), (210, 296), (206, 316), (194, 316)), fill=TIE)
    d.polygon(pts((194, 316), (206, 316), (216, 410), (200, 432), (184, 410)), fill=TIE)

    # कान, बाल (पीछे), चेहरा (गहरा आधार + हल्की परत = 3D जैसा असर)
    d.ellipse(P(121, 140, 141, 182), fill=SKIN_D)
    d.ellipse(P(259, 140, 279, 182), fill=SKIN_D)
    d.ellipse(P(124, 54, 276, 170), fill=HAIR)
    d.ellipse(P(129, 68, 273, 234), fill=SKIN_D)
    d.ellipse(P(129, 68, 266, 230), fill=SKIN)
    d.pieslice(P(129, 60, 271, 176), 180, 360, fill=HAIR)

    # भौंहें, चश्मा
    d.line(pts((160, 136), (190, 132)), fill=HAIR, width=int(6 * s))
    d.line(pts((210, 132), (240, 136)), fill=HAIR, width=int(6 * s))
    d.rounded_rectangle(P(154, 141, 196, 173), radius=int(10 * s), outline=FRAME, width=int(4 * s))
    d.rounded_rectangle(P(204, 141, 246, 173), radius=int(10 * s), outline=FRAME, width=int(4 * s))
    d.line(pts((196, 152), (204, 152)), fill=FRAME, width=int(4 * s))
    d.line(pts((154, 150), (131, 146)), fill=FRAME, width=int(3 * s))
    d.line(pts((246, 150), (269, 146)), fill=FRAME, width=int(3 * s))

    # आँखें
    for ex in (0, 50):
        if blink:
            d.line(pts((165 + ex, 158), (185 + ex, 158)), fill=(40, 30, 28), width=int(4 * s))
        else:
            d.ellipse(P(166 + ex, 150, 184 + ex, 164), fill=WHITE)
            d.ellipse(P(171 + ex, 151, 181 + ex, 163), fill=(60, 40, 30))
            d.ellipse(P(174 + ex, 154, 178 + ex, 160), fill=(10, 10, 10))

    # नाक और मुँह
    d.line(pts((200, 164), (195, 192), (205, 194)), fill=SKIN_D, width=int(3 * s))
    if mouth == 0:
        d.arc(P(180, 192, 220, 216), 20, 160, fill=(150, 70, 62), width=int(4 * s))
    elif mouth == 1:
        d.ellipse(P(187, 200, 213, 216), fill=(105, 32, 38))
        d.ellipse(P(191, 208, 209, 216), fill=(190, 70, 76))
    else:
        d.ellipse(P(182, 198, 218, 226), fill=(105, 32, 38))
        d.rectangle(P(188, 199, 212, 205), fill=WHITE)
        d.ellipse(P(190, 214, 210, 225), fill=(190, 70, 76))
    return img.resize((SPW, SPH), Image.LANCZOS)


def make_glow():
    g = Image.new("RGBA", (420, 420), (0, 170, 230, 0))
    ImageDraw.Draw(g).ellipse((70, 70, 350, 350), fill=(0, 170, 230, 120))
    return g.filter(ImageFilter.GaussianBlur(35))


# ---------------- स्लाइड का टेक्स्ट कार्ड ----------------
def text_layer(kind, title, body, idx, total):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    acc = ACCENT + (255,)
    white = (255, 255, 255, 255)
    d.rounded_rectangle((40, 40, 930, 676), radius=28, fill=(5, 12, 30, 150),
                        outline=(255, 255, 255, 50), width=2)
    bw = int(tw(d, BRAND, 22, True)) + 36
    d.rounded_rectangle((70, 64, 70 + bw, 102), radius=19, fill=acc)
    draw_text(d, 88, 69, BRAND, 22, (20, 25, 40, 255), True)

    if kind in ("intro", "outro"):
        size = 64
        lines = wrap(d, title, size, True, 820)
        if len(lines) > 3:
            size = 50
            lines = wrap(d, title, size, True, 820)
        lh = int(size * 1.3)
        y = 360 - lh * len(lines) // 2
        for line in lines:
            draw_text(d, 100, y, line, size, white, True)
            y += lh
        d.rectangle((100, y + 10, 240, y + 15), fill=acc)
    else:
        size = 44
        lines = wrap(d, title, size, True, 820)
        if len(lines) > 3:
            size = 36
            lines = wrap(d, title, size, True, 820)
        lh = int(size * 1.32)
        y = 124
        d.rounded_rectangle((60, y, 67, y + lh * len(lines)), radius=3, fill=acc)
        for line in lines:
            draw_text(d, 100, y, line, size, white, True)
            y += lh
        y += 10
        d.rectangle((100, y, 220, y + 4), fill=acc)
        y += 28
        for line in wrap(d, body, 38, False, 820):
            draw_text(d, 100, y, line, 38, (236, 241, 250, 255))
            y += 60

    x = 100
    for j, part in enumerate(FOOTER_PARTS):
        if j:
            d.ellipse((x + 4, 649, x + 12, 657), fill=acc)
            x += 24
        draw_text(d, x, 638, part, 24, acc)
        x += int(tw(d, part, 24)) + 10
    txt = f"{idx} / {total}"
    draw_text(d, 900 - int(tw(d, txt, 24)), 638, txt, 24, (200, 210, 225, 255))
    return layer


# ---------------- आवाज़ ----------------
async def tts(text, mp3):
    for _ in range(4):
        try:
            await edge_tts.Communicate(text, VOICE, rate=RATE).save(mp3)
            return
        except Exception as e:
            print("आवाज़ दोबारा बना रहे हैं:", e)
            await asyncio.sleep(3)
    raise SystemExit("आवाज़ नहीं बन सकी")


async def make_audio(i, text):
    mp3, wav = f"{TMP}/s{i}.mp3", f"{TMP}/s{i}.wav"
    await tts(text, mp3)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ar", "44100", "-ac", "2",
                    "-af", f"apad=pad_dur={PAD}", wav], check=True)
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", wav],
                         capture_output=True, text=True, check=True)
    total = float(out.stdout.strip())
    return wav, total, total - PAD


# ---------------- मुख्य ----------------
MOUTH = [1, 2, 1, 0, 2, 1, 2, 0]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(f"{TMP}/frames", exist_ok=True)
    title, body = read_article()
    slides = [("intro", title, "", title)]
    for c in make_chunks(body):
        slides.append(("body", title, c, c))
    if OUTRO_SPEECH:
        slides.append(("outro", OUTRO_TITLE, "", OUTRO_SPEECH))

    bigs, photo_count = load_backgrounds()
    sprites = {(m, b): draw_presenter(m, b) for m in range(3) for b in (0, 1)}
    glow = make_glow()
    print("स्लाइड:", len(slides), "| तस्वीरें:", photo_count)

    wavs, n, prev_big = [], 0, None
    for i, (kind, ttl, shown, spoken) in enumerate(slides):
        wav, total, speak_end = asyncio.run(make_audio(i, spoken))
        wavs.append(wav)
        big = bigs[(i // 3) % len(bigs)]   # हर 3 स्लाइड पर तस्वीर बदलती है
        layer = text_layer(kind, ttl, shown, i + 1, len(slides))
        alpha = layer.getchannel("A")
        frames = max(1, round(total * FPS))
        fade = int(0.6 * FPS)
        for k in range(frames):
            t = n / FPS
            img = crop_bg(big, t)
            if i % 3 == 0 and prev_big is not None and k < fade:
                img = Image.blend(crop_bg(prev_big, t), img, (k + 1) / fade)
            img.paste(glow, (895, 250), glow)
            if k < fade:
                a = (k + 1) / fade
                lay = layer.copy()
                lay.putalpha(alpha.point(lambda v, a=a: int(v * a)))
            else:
                lay = layer
            img.paste(lay, (0, 0), lay)

            speaking = (k / FPS) < speak_end
            mouth = MOUTH[(k // 2) % len(MOUTH)] if speaking else 0
            blink = 1 if n % 40 < 2 else 0
            sprite = sprites[(mouth, blink)]
            px = 955 + int(4 * math.sin(t * 1.2))
            py = H - SPH + 3 + int(3 * math.sin(t * 2.4))
            img.paste(sprite, (px, py), sprite)

            prog = (i + (k + 1) / frames) / len(slides)
            d = ImageDraw.Draw(img)
            d.rectangle((0, H - 8, W, H), fill=(20, 30, 50))
            d.rectangle((0, H - 8, int(W * prog), H), fill=ACCENT)
            img.save(f"{TMP}/frames/{n:05d}.jpg", quality=88)
            n += 1
        prev_big = big

    with open(f"{TMP}/list.txt", "w") as f:
        for w in wavs:
            f.write(f"file '{os.path.abspath(w)}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", f"{TMP}/list.txt", f"{TMP}/audio.wav"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
                    "-i", f"{TMP}/frames/%05d.jpg", "-i", f"{TMP}/audio.wav",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    f"{OUT_DIR}/ncrib-awareness.mp4"], check=True)
    print("तैयार: output/ncrib-awareness.mp4")


if __name__ == "__main__":
    main()
