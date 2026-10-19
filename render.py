
import os
import subprocess
import requests
from pathlib import Path
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 720
FPS = 24

OUT = Path("output")
WORK = Path("work")
OUT.mkdir(exist_ok=True)
WORK.mkdir(exist_ok=True)

SCENES = [
    {
        "title": "NCRIB FOUNDATION",
        "text": "Kisi bhi sanstha par bharosa karne se pehle uski jaankari jaanchna zaroori hai.",
        "color": (22, 40, 72),
        "seconds": 7,
    },
    {
        "title": "REGISTRATION KI JAANCH",
        "text": "Registration number, legal name aur official records ko sambandhit sarkari website par verify karein.",
        "color": (25, 66, 83),
        "seconds": 8,
    },
    {
        "title": "DAAVON KI TASDEEQ",
        "text": "Website ya social media par diye gaye daavon ko bina saboot sach na maanein. Mool source dekhein.",
        "color": (65, 47, 83),
        "seconds": 8,
    },
    {
        "title": "NAUKRI AUR BHARTI",
        "text": "Bharti ke vigyapan, padon ki sankhya, fees aur appointment ke daavon ko official notification se milayein.",
        "color": (83, 54, 32),
        "seconds": 8,
    },
    {
        "title": "SAVDHANI ZAROORI HAI",
        "text": "Kisi bhi payment ya personal document ko dene se pehle sanstha aur process ki swatantra jaanch karein.",
        "color": (33, 72, 59),
        "seconds": 8,
    },
    {
        "title": "JAANKARI SHARE KAREIN",
        "text": "Afwah nahi, tathya share karein. Sahi jaankari ke liye official records aur bharosemand sources par nirbhar rahein.",
        "color": (30, 43, 68),
        "seconds": 8,
    },
]


def run(cmd):
    subprocess.run(cmd, check=True)


def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def download_background(index):
    path = WORK / f"background_{index}.jpg"
    url = (
        "https://images.unsplash.com/photo-"
        "1497366754035-f200968a6e72"
        "?auto=format&fit=crop&w=1280&q=80"
    )
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        path.write_bytes(r.content)
        img = Image.open(path).convert("RGB").resize((W, H))
    except Exception:
        img = Image.new("RGB", (W, H), SCENES[index]["color"])
    return img.filter(ImageFilter.GaussianBlur(1))


def make_scene(index, scene):
    img = download_background(index).convert("RGBA")

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, W, H), fill=(*scene["color"], 185))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Decorative accent
    draw.rounded_rectangle(
        (70, 75, 86, 630),
        radius=8,
        fill=(255, 195, 70, 255)
    )

    title_font = font(52, True)
    body_font = font(34, True)
    small_font = font(22)

    draw.text(
        (120, 120),
        scene["title"],
        font=title_font,
        fill="white",
        stroke_width=1,
        stroke_fill=(0, 0, 0, 100)
    )

    # Wrap the narration text
    words = scene["text"].split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textlength(test, font=body_font) > 950:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    y = 245
    for line in lines:
        draw.text(
            (120, y),
            line,
            font=body_font,
            fill=(245, 248, 255, 255)
        )
        y += 58

    # Simple illustrated presenter
    cx, cy = 1080, 435
    draw.ellipse(
        (cx - 72, cy - 150, cx + 72, cy - 6),
        fill=(210, 155, 115, 255)
    )
    draw.rounded_rectangle(
        (cx - 105, cy - 10, cx + 105, cy + 205),
        radius=45,
        fill=(35, 105, 145, 255)
    )
    draw.ellipse(
        (cx - 42, cy - 98, cx - 22, cy - 78),
        fill=(25, 25, 25, 255)
    )
    draw.ellipse(
        (cx + 22, cy - 98, cx + 42, cy - 78),
        fill=(25, 25, 25, 255)
    )
    draw.arc(
        (cx - 30, cy - 75, cx + 30, cy - 35),
        start=10,
        end=165,
        fill=(80, 30, 25, 255),
        width=4
    )

    draw.text(
        (120, 625),
        "AWARENESS • RESEARCH • VERIFICATION",
        font=small_font,
        fill=(255, 211, 115, 255)
    )

    still = WORK / f"scene_{index}.png"
    img.convert("RGB").save(still, quality=95)
    return still


def make_audio(index, text):
    path = WORK / f"audio_{index}.mp3"
    gTTS(text=text, lang="hi", slow=False).save(str(path))
    return path


def audio_duration(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def main():
    clips = []

    for i, scene in enumerate(SCENES):
        print(f"Creating scene {i + 1}/{len(SCENES)}")

        image_path = make_scene(i, scene)
        audio_path = make_audio(i, scene["text"])
        duration = max(scene["seconds"], audio_duration(audio_path) + 1)

        video_path = WORK / f"clip_{i}.mp4"

        run([
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-i", str(audio_path),
            "-vf",
            f"scale={W}:{H},"
            f"zoompan=z='min(zoom+0.0005,1.06)':"
            f"x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={int(duration * FPS)}:s={W}x{H}:fps={FPS},"
            "format=yuv420p",
            "-t", str(duration),
            "-r", str(FPS),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            str(video_path),
        ])
        clips.append(video_path)

    list_path = WORK / "clips.txt"
    with list_path.open("w", encoding="utf-8") as f:
        for clip in clips:
            f.write(f"file '{clip.resolve()}'\n")

    final_path = OUT / "ncrib-awareness.mp4"

    run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-c", "copy",
        "-movflags", "+faststart",
        str(final_path),
    ])

    print(f"Video created: {final_path}")


if __name__ == "__main__":
    main()
