#!/usr/bin/env python3
"""
Generate 30-second Orvima promotional video with:
- Edge TTS voiceover with Ultron-style modulation
- Smooth animations (Framer Motion style)
- WhatsApp + Email demo sequences
- Orvima branding (#F5A524 on #0D1117)
"""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

# Video specs
WIDTH = 1920
HEIGHT = 1080
FPS = 30
DURATION = 30  # seconds
TOTAL_FRAMES = DURATION * FPS

BG_COLOR = "#0D1117"
ACCENT = "#F5A524"
ACCENT_HOVER = "#FFB84D"
CARD_BG = "#161B22"
BORDER = "#30363D"
TEXT = "#E6EDF3"
TEXT_MUTED = "#8B949E"
GREEN = "#3FB950"
RED = "#F85149"

SCRIPT = """
[0:00-0:05] Your AI agent can browse. But can it send emails? WhatsApp? Speak?
[0:05-0:10] Most agents hit a wall — no email, no messaging, no voice.
[0:10-0:15] Orvima. 49 MCP tools. One server. Browser, mail, WhatsApp, voice, math, science.
[0:15-0:22] Watch: mail_send — verified delivery. whatsapp_send — blue ticks confirmed. browse_navigate — DOM verified.
[0:22-0:27] Safety gates on destructive actions. Verified badges on every step. Run on your infrastructure.
[0:27-0:30] Get started free. github.com/Sachitt-AV-08/orvima
"""

# Timing breakdown for animation sync
SCENES = [
    {"start": 0, "end": 5, "text": "Your AI agent can browse. But can it send emails? WhatsApp? Speak?", "type": "hook"},
    {"start": 5, "end": 10, "text": "Most agents hit a wall — no email, no messaging, no voice.", "type": "problem"},
    {"start": 10, "end": 15, "text": "Orvima. 49 MCP tools. One server. Browser, mail, WhatsApp, voice, math, science.", "type": "solution"},
    {"start": 15, "end": 22, "text": "Watch: mail_send — verified delivery. whatsapp_send — blue ticks confirmed. browse_navigate — DOM verified.", "type": "demo"},
    {"start": 22, "end": 27, "text": "Safety gates on destructive actions. Verified badges on every step. Run on your infrastructure.", "type": "features"},
    {"start": 27, "end": 30, "text": "Get started free. github.com/Sachitt-AV-08/orvima", "type": "cta"},
]


async def generate_tts(text: str, output_path: str, voice: str = "en-US-GuyNeural", rate: str = "+0%", pitch: str = "-2.5st") -> None:
    """Generate TTS using Edge TTS with Ultron-style modulation."""
    cmd = [
        "edge-tts",
        "--voice", voice,
        "--rate", rate,
        "--pitch", pitch,
        "--text", text,
        "--write-media", output_path
    ]
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.wait()


def create_frame_script() -> str:
    """Generate a Manim/Python script for frame-by-frame video generation."""
    return f'''
from moviepy.editor import *
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

WIDTH = {WIDTH}
HEIGHT = {HEIGHT}
FPS = {FPS}
DURATION = {DURATION}
BG = "{BG_COLOR}"
ACCENT = "{ACCENT}"
CARD = "{CARD_BG}"
BORDER = "{BORDER}"
TEXT = "{TEXT}"
MUTED = "{TEXT_MUTED}"
GREEN = "{GREEN}"

# Create frames directory
os.makedirs("frames", exist_ok=True)

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

BG_RGB = hex_to_rgb(BG)
ACCENT_RGB = hex_to_rgb(ACCENT)
CARD_RGB = hex_to_rgb(CARD)
BORDER_RGB = hex_to_rgb(BORDER)
TEXT_RGB = hex_to_rgb(TEXT)
MUTED_RGB = hex_to_rgb(MUTED)
GREEN_RGB = hex_to_rgb(GREEN)

def draw_rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)

def ease_out_cubic(t):
    return 1 - (1 - t) ** 3

def ease_out_elastic(t):
    if t == 0: return 0
    if t == 1: return 1
    return 2 ** (-10 * t) * np.sin((t * 10 - 0.75) * 2 * np.pi / 0.3) + 1

# Load font
try:
    font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
    font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
    font_mono = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 28)
except:
    font_large = ImageFont.load_default()
    font_medium = ImageFont.load_default()
    font_small = ImageFont.load_default()
    font_mono = ImageFont.load_default()

scenes = {SCENES}

for frame_num in range({TOTAL_FRAMES}):
    t = frame_num / FPS
    progress = t / DURATION
    
    # Create base image
    img = Image.new('RGB', (WIDTH, HEIGHT), BG_RGB)
    draw = ImageDraw.Draw(img)
    
    # Background gradient orbs
    orb1_x = int(WIDTH * 0.15 + np.sin(t * 0.5) * 50)
    orb1_y = int(HEIGHT * 0.2 + np.cos(t * 0.3) * 30)
    orb2_x = int(WIDTH * 0.85 + np.sin(t * 0.7) * 40)
    orb2_y = int(HEIGHT * 0.8 + np.cos(t * 0.4) * 25)
    
    # Draw gradient orbs (simplified as circles with alpha)
    for i in range(100, 0, -2):
        alpha = int(255 * (1 - i/100) * 0.08)
        color = (*ACCENT_RGB[:3], alpha)
        # Can't do alpha easily with ImageDraw, skip for now
    
    # Find current scene
    current_scene = None
    for scene in scenes:
        if scene["start"] <= t < scene["end"]:
            current_scene = scene
            break
    
    if not current_scene:
        current_scene = scenes[-1]
    
    scene_progress = (t - current_scene["start"]) / (current_scene["end"] - current_scene["start"])
    scene_progress = max(0, min(1, scene_progress))
    eased = ease_out_cubic(scene_progress)
    
    # Scene-specific rendering
    if current_scene["type"] == "hook":
        # Large animated text
        y_pos = int(HEIGHT * 0.4 - 100 * (1 - eased))
        opacity = int(255 * eased)
        # Split text into lines
        lines = ["Your AI agent can browse.", "But can it send emails?", "WhatsApp? Speak?"]
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font_large)
            w = bbox[2] - bbox[0]
            x = (WIDTH - w) // 2
            y = y_pos + i * 100
            # Draw with accent highlight for key words
            draw.text((x, y), line, font=font_large, fill=TEXT_RGB)
    
    elif current_scene["type"] == "problem":
        # Red X animation + text
        scale = eased
        cx, cy = WIDTH // 2, HEIGHT // 2 - 50
        size = int(120 * scale)
        # Draw X
        draw.line((cx-size, cy-size, cx+size, cy+size), fill=RED, width=8)
        draw.line((cx+size, cy-size, cx-size, cy+size), fill=RED, width=8)
        
        text = current_scene["text"]
        bbox = draw.textbbox((0, 0), text, font=font_medium)
        w = bbox[2] - bbox[0]
        x = (WIDTH - w) // 2
        y = HEIGHT // 2 + 100
        draw.text((x, y), text, font=font_medium, fill=MUTED_RGB)
    
    elif current_scene["type"] == "solution":
        # Orvima logo + feature grid
        logo_y = int(HEIGHT * 0.25)
        draw.text((WIDTH//2 - 150, logo_y), "ORVIMA", font=font_large, fill=ACCENT_RGB)
        
        features = ["Browser", "Mail", "WhatsApp", "Voice", "Math", "Science"]
        for i, feat in enumerate(features):
            row = i // 3
            col = i % 3
            x = WIDTH//2 - 300 + col * 300
            y = HEIGHT//2 + row * 100
            delay = i * 0.1
            feat_progress = max(0, min(1, (scene_progress - delay) / (1 - delay)))
            feat_eased = ease_out_elastic(feat_progress)
            scale = 0.5 + 0.5 * feat_eased
            opacity = int(255 * feat_eased)
            
            # Card
            card_w, card_h = int(250 * scale), int(80 * scale)
            draw_rounded_rect(draw, (x - card_w//2, y - card_h//2, x + card_w//2, y + card_h//2), 
                            12, CARD_RGB, BORDER_RGB, 2)
            draw.text((x - 60, y - 15), feat, font=font_small, fill=TEXT_RGB)
    
    elif current_scene["type"] == "demo":
        # Terminal animation
        term_x, term_y = 100, 150
        term_w, term_h = WIDTH - 200, HEIGHT - 300
        
        # Terminal background
        draw_rounded_rect(draw, (term_x, term_y, term_x + term_w, term_y + term_h), 12, (13, 17, 23), BORDER_RGB, 2)
        
        # Terminal header
        draw_rounded_rect(draw, (term_x, term_y, term_x + term_w, term_y + 40), 12, CARD_RGB, BORDER_RGB, 2)
        for i, color in enumerate([(255, 95, 86), (255, 189, 46), (40, 205, 65)]):
            draw.ellipse((term_x + 20 + i * 18, term_y + 10, term_x + 32 + i * 18, term_y + 22), fill=color)
        
        # Terminal content - animated typing
        commands = [
            ('$ orvima mail_send --to "hr@company.com" --subject "Application"', 0, 2),
            ('✓ Email sent — Message-ID: <20261021.12345@smtp.mailin.fr>', 2, 4),
            ('$ orvima whatsapp_send --to "+15551234567" --text "Ready for demo?"', 4, 6),
            ('✓ Message delivered — 2 blue ticks confirmed', 6, 8),
            ('$ orvima browse_navigate --url "https://github.com"', 8, 10),
            ('✓ Page loaded — DOM verified: true', 10, 12),
        ]
        
        scene_t = t - current_scene["start"]
        for cmd, start, end in commands:
            if scene_t >= start:
                progress = min(1, (scene_t - start) / (end - start))
                lines_to_show = int(progress * 3) if not cmd.startswith('✓') else (1 if progress > 0.5 else 0)
                if lines_to_show > 0 or (cmd.startswith('✓') and progress > 0.5):
                    y_pos = term_y + 60 + commands.index(cmd) * 50
                    color = GREEN_RGB if cmd.startswith('✓') else TEXT_RGB
                    if cmd.startswith('$'):
                        color = (150, 150, 150)
                    draw.text((term_x + 30, y_pos), cmd[:int(len(cmd) * progress)], font=font_mono, fill=color)
    
    elif current_scene["type"] == "features":
        # Feature badges
        badges = [
            ("🛡️", "Safety Gates", "Destructive actions → human approval"),
            ("✅", "Verified Badges", "Every step DOM-verified"),
            ("🏠", "Your Infra", "No cloud lock-in, self-hosted"),
        ]
        
        for i, (icon, title, desc) in enumerate(badges):
            x = WIDTH//2 - 450 + i * 450
            y = HEIGHT//2
            delay = i * 0.15
            b_progress = max(0, min(1, (scene_progress - delay) / 0.5))
            b_eased = ease_out_cubic(b_progress)
            
            scale = 0.3 + 0.7 * b_eased
            opacity = int(255 * b_eased)
            
            card_w, card_h = int(350 * scale), int(200 * scale)
            draw_rounded_rect(draw, (x - card_w//2, y - card_h//2, x + card_w//2, y + card_h//2), 
                            16, CARD_RGB, ACCENT_RGB if b_progress > 0.8 else BORDER_RGB, 2)
            
            draw.text((x - 80, y - 60), title, font=font_medium, fill=TEXT_RGB)
            draw.text((x - 120, y + 10), desc, font=font_small, fill=MUTED_RGB)
    
    elif current_scene["type"] == "cta":
        # CTA with pulse
        pulse = 1 + 0.1 * np.sin(t * 4)
        cta_text = "Get started free"
        bbox = draw.textbbox((0, 0), cta_text, font=font_large)
        w = bbox[2] - bbox[0]
        x = (WIDTH - w) // 2
        y = HEIGHT // 2 - 50
        
        # Button background with pulse
        btn_w, btn_h = int(w + 60 * pulse), int(80 * pulse)
        draw_rounded_rect(draw, (x - 30, y - 10, x + w + 30, y + 70), 16, ACCENT_RGB, None, 0)
        draw.text((x, y), cta_text, font=font_large, fill=BG_RGB)
        
        # URL
        url = "github.com/Sachitt-AV-08/orvima"
        bbox = draw.textbbox((0, 0), url, font=font_medium)
        w = bbox[2] - bbox[0]
        x = (WIDTH - w) // 2
        y = HEIGHT // 2 + 60
        draw.text((x, y), url, font=font_medium, fill=MUTED_RGB)
    
    # Save frame
    img.save(f"frames/frame_{frame_num:05d}.png")
    
    if frame_num % 30 == 0:
        print(f"Rendered frame {frame_num}/{TOTAL_FRAMES} ({t:.1f}s)")

print("All frames rendered!")
'''


async def main():
    print("=" * 60)
    print("Orvima Promo Video Generator")
    print("=" * 60)
    
    # Check dependencies
    for cmd in ["edge-tts", "ffmpeg"]:
        try:
            subprocess.run([cmd, "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"❌ {cmd} not found. Install with:")
            if cmd == "edge-tts":
                print("  pip install edge-tts")
            else:
                print("  apt-get install ffmpeg  # or winget install ffmpeg")
            return
    
    print("✅ Dependencies found")
    
    # Generate TTS audio
    print("\n🎙️  Generating voiceover...")
    full_text = " ".join(s["text"] for s in SCENES)
    await generate_tts(full_text, "voiceover.mp3")
    print("✅ Voiceover generated: voiceover.mp3")
    
    # Generate video frames
    print("\n🎬 Generating video frames...")
    frame_script = create_frame_script()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(frame_script)
        script_path = f.name
    
    try:
        # Run frame generation
        result = subprocess.run(["python3", script_path], capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"❌ Frame generation failed: {result.stderr}")
            return
        print("✅ Frames generated")
    finally:
        os.unlink(script_path)
    
    # Combine frames + audio with ffmpeg
    print("\n🎞️  Combining frames + audio...")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", "frames/frame_%05d.png",
        "-i", "voiceover.mp3",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "slow",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "orvima_promo_30s.mp4"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ FFmpeg failed: {result.stderr}")
        return
    
    print("✅ Video created: orvima_promo_30s.mp4")
    
    # Cleanup
    import shutil
    shutil.rmtree("frames", ignore_errors=True)
    os.remove("voiceover.mp3")
    
    print("\n" + "=" * 60)
    print("🎉 DONE! Video ready: orvima_promo_30s.mp4")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())