import asyncio
import os
import subprocess
import edge_tts
from PIL import Image, ImageDraw

# गंभीर और स्पष्ट हिंदी स्क्रिप्ट
TEXT = """
सावधान! NCRIB फाउंडेशन और NGO दर्पण जैसे नामों से भ्रमित न हों। 
सरकारी जैसी दिखने वाली वेबसाइट, वास्तविक सरकारी संस्था नहीं होती। 
किसी भी जॉब वैकेंसी या विज्ञापन के बहकावे में आने से पहले दस्तावेज़ और वेबसाइट इतिहास की पुष्टि ज़रूर करें।
"""

VOICE = "hi-IN-MadhurNeural"  # सीरियस और क्लियर मेल वॉइस
AUDIO_PATH = "voiceover.mp3"
FRAME_PATH = "frame.png"
OUTPUT_PATH = "output/ncrib-awareness.mp4"

async def generate_voice():
    communicate = edge_tts.Communicate(TEXT, VOICE, rate="+0%")
    await communicate.save(AUDIO_PATH)

def create_base_image():
    # 1280x720 का पेशेवर डार्क बैकग्राउंड बनाएं
    img = Image.new("RGB", (1280, 720), color=(15, 23, 42))
    img.save(FRAME_PATH)

def create_video():
    print("Generating voiceover...")
    asyncio.run(generate_voice())
    
    print("Creating background frame...")
    create_base_image()
    
    os.makedirs("output", exist_ok=True)
    
    print("Rendering MP4 video using FFmpeg...")
    # FFmpeg के जरिए इमेज और ऑडियो को जोड़कर MP4 बनाना
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", FRAME_PATH,
        "-i", AUDIO_PATH,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        OUTPUT_PATH
    ]
    
    subprocess.run(cmd, check=True)
    print("Video rendered successfully!")

if __name__ == "__main__":
    create_video()
