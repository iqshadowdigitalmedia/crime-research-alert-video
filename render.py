import asyncio
import os
import math
import subprocess
import edge_tts
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------
# Configuration for Horizontal 16:9 (1920x1080) Video
# ---------------------------------------------------------
VOICE = "hi-IN-MadhurNeural"  # Serious Male Voice
AUDIO_PATH = "voiceover.mp3"
INPUT_BG = "background.jpg"   # Your poster image
OUTPUT_PATH = "output/ncrib-awareness-horizontal.mp4"
FRAMES_DIR = "frames"

# Scrolling Ticker Text
TICKER_TEXT = " ⚠️ FRAUD PREVENTION • SCAM ALERT • CORRUPTION WARNING • CYBERSECURITY PROTECTION • VERIFY BEFORE TRUSTING ⚠️ "

# ---------------------------------------------------------
# 1. Read Script from article.txt
# ---------------------------------------------------------
def get_script_text():
    if os.path.exists("article.txt"):
        with open("article.txt", "r", encoding="utf-8") as f:
            text = f.read().strip()
            if text:
                return text
    return """
    सावधान! NCRIB फाउंडेशन और NGO दर्पण जैसे नामों से भ्रमित न हों। 
    सरकारी जैसी दिखने वाली वेबसाइट, वास्तविक सरकारी संस्था नहीं होती। 
    किसी भी जॉब वैकेंसी या विज्ञापन के बहकावे में आने से पहले, दस्तावेज़ और वेबसाइट इतिहास की पुष्टि ज़रूर करें।
    """

# ---------------------------------------------------------
# 2. Generate Serious Voiceover
# ---------------------------------------------------------
async def generate_voice(script_text):
    communicate = edge_tts.Communicate(script_text, VOICE, rate="-8%", pitch="+0Hz")
    await communicate.save(AUDIO_PATH)

# ---------------------------------------------------------
# 3. Get Audio Duration using FFmpeg
# ---------------------------------------------------------
def get_audio_duration(file_path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(result.stdout.strip())

# ---------------------------------------------------------
# 4. Generate Horizontal (1920x1080) Animated Frames
# ---------------------------------------------------------
def generate_animated_frames(duration, fps=25):
    os.makedirs(FRAMES_DIR, exist_ok=True)
    total_frames = int(duration * fps)
    
    # Base background image resized to Full HD Horizontal (1920x1080)
    if os.path.exists(INPUT_BG):
        base_img = Image.open(INPUT_BG).convert("RGB").resize((1920, 1080))
    else:
        base_img = Image.new("RGB", (1920, 1080), color=(15, 23, 42))

    print(f"Generating {total_frames} horizontal animated frames...")
    
    ticker_x = 0
    font = ImageFont.load_default()

    for i in range(total_frames):
        # Continuous slow zoom effect for background
        zoom_factor = 1.0 + (0.05 * (i / total_frames))
        w, h = base_img.size
        crop_w, crop_h = int(w / zoom_factor), int(h / zoom_factor)
        crop_x, crop_y = (w - crop_w) // 2, (h - crop_h) // 2
        
        frame = base_img.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
        frame = frame.resize((1920, 1080))
        
        draw = ImageDraw.Draw(frame)

        # Top Warning Header Bar (Horizontal Wide)
        draw.rectangle([(0, 0), (1920, 60)], fill=(180, 20, 20))
        draw.text((30, 20), "CYBERSECURITY WARNING & FRAUD PREVENTION ALERT", fill=(255, 255, 255), font=font)

        # Pulsing Alert Indicator Light on Top-Right Corner
        pulse = int(127 + 127 * math.sin(i * 0.2))
        draw.ellipse([(1850, 15), (1885, 45)], fill=(255, pulse, pulse))

        # Bottom Scrolling Ticker Banner Animation
        draw.rectangle([(0, 1020), (1920, 1080)], fill=(0, 0, 0))
        ticker_x -= 6  # Scrolling speed
        if abs(ticker_x) > 1500:
            ticker_x = 0
            
        draw.text((ticker_x, 1040), TICKER_TEXT * 4, fill=(255, 215, 0), font=font)

        # Save each frame
        frame_filename = os.path.join(FRAMES_DIR, f"frame_{i:04d}.png")
        frame.save(frame_filename)

    return total_frames

# ---------------------------------------------------------
# 5. Build Final Horizontal MP4 Video via FFmpeg
# ---------------------------------------------------------
def build_video():
    script_text = get_script_text()
    print("Reading article text...")
    
    print("Generating Serious Hindi Voiceover...")
    asyncio.run(generate_voice(script_text))
    
    duration = get_audio_duration(AUDIO_PATH)
    print(f"Audio Duration: {duration:.2f} seconds")
    
    generate_animated_frames(duration, fps=25)
    
    os.makedirs("output", exist_ok=True)
    
    print("Combining Frames and Audio into Horizontal MP4...")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", "25",
        "-i", f"{FRAMES_DIR}/frame_%04d.png",
        "-i", AUDIO_PATH,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "256k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        OUTPUT_PATH
    ]
    
    subprocess.run(cmd, check=True)
    print("Horizontal Long Video Render Completed Successfully!")

if __name__ == "__main__":
    build_video()
