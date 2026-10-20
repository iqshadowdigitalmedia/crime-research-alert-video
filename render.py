import asyncio
import os
import subprocess
import edge_tts
from PIL import Image

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
VOICE = "hi-IN-MadhurNeural"  # Serious Male Voice
AUDIO_PATH = "voiceover.mp3"
INPUT_BG = "background.jpg"   # Poster image
PROCESSED_FRAME = "base_frame.png"
OUTPUT_PATH = "output/ncrib-awareness-horizontal.mp4"

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
# 2. Serious Voiceover Generator
# ---------------------------------------------------------
async def generate_voice(script_text):
    communicate = edge_tts.Communicate(script_text, VOICE, rate="-8%", pitch="+0Hz")
    await communicate.save(AUDIO_PATH)

# ---------------------------------------------------------
# 3. Base Image Resizing to 1920x1080
# ---------------------------------------------------------
def prepare_base_frame():
    if os.path.exists(INPUT_BG):
        img = Image.open(INPUT_BG).convert("RGB").resize((1920, 1080))
    else:
        img = Image.new("RGB", (1920, 1080), color=(15, 23, 42))
    img.save(PROCESSED_FRAME)

# ---------------------------------------------------------
# 4. Fast Direct FFmpeg Filter Engine
# ---------------------------------------------------------
def build_video():
    script_text = get_script_text()
    print("Reading article text...")
    
    print("Generating Serious Hindi Voiceover...")
    asyncio.run(generate_voice(script_text))
    
    print("Preparing 1920x1080 Base Frame...")
    prepare_base_frame()
    
    os.makedirs("output", exist_ok=True)
    
    print("Rendering Animated Video via FFmpeg...")
    
    # Smooth Zoom Animation + Red Header + Scrolling Yellow Ticker
    filter_complex = (
        "[0:v]zoompan=z='min(zoom+0.0008,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1920x1080:fps=25[bg];"
        "[bg]drawbox=y=0:color=red@0.85:width=iw:height=70:t=fill[topbar];"
        "[topbar]drawtext=text='CYBERSECURITY WARNING AND FRAUD PREVENTION ALERT':fontcolor=white:fontsize=32:x=40:y=20[header];"
        "[header]drawbox=y=1010:color=black@0.9:width=iw:height=70:t=fill[bottombar];"
        "[bottombar]drawtext=text='WARNING: FRAUD PREVENTION - SCAM ALERT - CORRUPTION WARNING - VERIFY DOCUMENTS BEFORE APPLYING':fontcolor=yellow:fontsize=28:x='w-mod(t*180\\,w+1200)':y=1030[outv]"
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", PROCESSED_FRAME,
        "-i", AUDIO_PATH,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "256k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        OUTPUT_PATH
    ]
    
    subprocess.run(cmd, check=True)
    print("Video Render Completed Successfully!")

if __name__ == "__main__":
    build_video()
