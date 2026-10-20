import asyncio
import os
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, TextClip

# 1. गंभीर और स्पष्ट वॉइसओवर (Serious Male Voice)
TEXT = """
सावधान! NCRIB फाउंडेशन और NGO दर्पण जैसे नामों से भ्रमित न हों। 
सरकारी जैसी दिखने वाली वेबसाइट, वास्तविक सरकारी संस्था नहीं होती। 
किसी भी जॉब वैकेंसी या विज्ञापन के बहकावे में आने से पहले दस्तावेज़ और वेबसाइट इतिहास की पुष्टि ज़रूर करें।
"""

VOICE = "hi-IN-MadhurNeural"  # सीरियस और क्लियर मेल वॉइस
AUDIO_PATH = "voiceover.mp3"
OUTPUT_PATH = "output/ncrib-awareness.mp4"

async def generate_voice():
    communicate = edge_tts.Communicate(TEXT, VOICE, rate="+0%")
    await communicate.save(AUDIO_PATH)

def create_video():
    # ऑडियो जनरेट करें
    asyncio.run(generate_voice())
    
    # आउटपुट फोल्डर बनाएं
    os.makedirs("output", exist_ok=True)
    
    # ऑडियो लोड करें
    audio = AudioFileClip(AUDIO_PATH)
    duration = audio.duration
    
    # इमेज/बैकग्राउंड लोड करें (अगर इमेज है तो 1000273241.jpg का यूज़ करें)
    # यहाँ हम बेसिक इमेज/बैकग्राउंड से वीडियो बना रहे हैं
    if os.path.exists("background.jpg"):
        clip = ImageClip("background.jpg").set_duration(duration)
    else:
        # बैकग्राउंड इमेज न होने पर डिफ़ॉल्ट क्लिप
        from moviepy.editor import ColorClip
        clip = ColorClip(size=(1280, 720), color=(15, 23, 42)).set_duration(duration)

    # ऑडियो अटैच करें
    final_clip = clip.set_audio(audio)
    
    # MP4 सेव करें
    final_clip.write_videofile(
        OUTPUT_PATH,
        fps=24,
        codec="libx264",
        audio_codec="aac"
    )

if __name__ == "__main__":
    create_video()
