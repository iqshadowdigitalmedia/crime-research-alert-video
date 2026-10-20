import asyncio
import glob
import math
import os
import random
import re
import subprocess
from functools import lru_cache

import edge_tts
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1280, 720, 12
VOICE = "hi-IN-MadhurNeural"   # पुरुष की हिंदी आवाज़
RATE = "-8%"                   # धीमी और साफ़ आवाज़ (और धीमा करना हो तो "-15%")
PAD = 0.6                      # हर स्लाइड के बाद रुकने का समय
CHUNK = 140                    # एक स्लाइड में अधिकतम अक्षर
FOOTER = "साइबर जागरूकता • सतर्क रहें • सुरक्षित रहें"
OUT_DIR, TMP = "output", "tmp"


@lru_cache(maxsize=None)
def load_font(size, bold=False):
    name = "NotoSansDevanagari-Bold.ttf" if bold else "NotoSansDevanagari-Regular.ttf"
    paths = glob.glob(f"/usr/share/fonts/**/{name}", recursive=True)
    paths += glob.glob("/usr/share/fonts/**/NotoSansDevanagari*.ttf", recursive=True)
    paths += glob.glob("/usr/share/fonts/**/*Devanagari*.ttf", recursive=True)
    if not paths:
        raise SystemExit("देवनागरी फ़ॉन्ट नहीं मिला")
    try:
        return ImageFont.truetype(paths[0], size, layout_engine=ImageFont.Layout.RAQM)
    except Exception:
        return ImageFont.truetype(paths[0], size)


def wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        test = (cur + " " + word).strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


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


def cover(im):
    s = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1))
    x, y = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


def load_backgrounds():
    exts = (".jpg", ".jpeg", ".png", ".webp")
    files = []
    for folder in (".", "images"):
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if name.lower().endswith(exts):
                    files.append(os.path.join(folder, name))
    black = Image.new("RGB", (W, H), (0, 0, 0))
    bgs = []
    for f in files:
        try:
            bgs.append(Image.blend(cover(Image.open(f).convert("RGB")), black, 0.45))
        except Exception as e:
            print("तस्वीर छोड़ी:", f, e)
    return bgs


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


def text_layer(title, body):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f_title, f_body, f_foot = load_font(46, True), load_font(38), load_font(26)
    d.rounded_rectangle((40, 50, 940, 690), radius=24, fill=(0, 0, 0, 120))
    d.rounded_rectangle((60, 80, 70, 620), radius=5, fill=(255, 193, 7, 255))
    y = 80
    for line in wrap(d, title, f_title, 840):
        d.text((100, y), line, font=f_title, fill=(255, 255, 255, 255))
        y += 58
    y += 25
    for line in wrap(d, body, f_body, 800):
        d.text((100, y), line, font=f_body, fill=(235, 240, 250, 255))
        y += 60
    d.text((100, 640), FOOTER, font=f_foot, fill=(255, 193, 7, 255))
    return layer


def draw_character(img, t, speaking, frame_i):
    d = ImageDraw.Draw(img)
    bob = int(6 * math.sin(t * 3))
    cx, top = 1070, 330 + bob
    d.rounded_rectangle((cx - 110, top + 140, cx + 110, top + 330), radius=40, fill=(35, 110, 160))
    d.ellipse((cx - 75, top, cx + 75, top + 150), fill=(212, 160, 120))
    d.ellipse((cx - 35, top + 50, cx - 21, top + 66), fill=(20, 20, 20))
    d.ellipse((cx + 21, top + 50, cx + 35, top + 66), fill=(20, 20, 20))
    if speaking and (frame_i // 2) % 2 == 0:
        d.ellipse((cx - 20, top + 95, cx + 20, top + 125), fill=(120, 30, 30))
    else:
        d.arc((cx - 28, top + 85, cx + 28, top + 120), 20, 160, fill=(90, 40, 30), width=4)


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


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(f"{TMP}/frames", exist_ok=True)
    title, body = read_article()
    slides = [("", title)] + [(c, c) for c in make_chunks(body)]
    bgs = load_backgrounds()
    fallback = [cyber_bg(s) for s in range(4)] if not bgs else []
    print("स्लाइड:", len(slides), "| तस्वीरें:", len(bgs))

    wavs, n = [], 0
    for i, (shown, spoken) in enumerate(slides):
        wav, total, speak_end = asyncio.run(make_audio(i, spoken))
        wavs.append(wav)
        group = i // 3   # हर 3 स्लाइड पर तस्वीर बदलती है
        bg = bgs[group % len(bgs)] if bgs else fallback[group % 4]
        layer = text_layer(title, shown)
        alpha = layer.getchannel("A")
        base = bg.copy()
        base.paste(layer, (0, 0), layer)
        frames = max(1, round(total * FPS))
        fade = int(0.6 * FPS)
        for k in range(frames):
            t = k / FPS
            if k < fade:
                a = (k + 1) / fade
                lay = layer.copy()
                lay.putalpha(alpha.point(lambda v, a=a: int(v * a)))
                img = bg.copy()
                img.paste(lay, (0, 0), lay)
            else:
                img = base.copy()
            draw_character(img, t, t < speak_end, k)
            img.save(f"{TMP}/frames/{n:05d}.jpg", quality=88)
            n += 1

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
