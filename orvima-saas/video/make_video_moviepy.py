#!/usr/bin/env python3
"""
Generate 30-second Orvima promo video using MoviePy 2.x.
Simplified version without complex effects.
"""

from moviepy import VideoClip, CompositeVideoClip, TextClip, AudioFileClip
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

# Video specs
WIDTH = 1920
HEIGHT = 1080
FPS = 30
DURATION = 33  # Match faster voiceover

# Orvima colors
BG = "#0D1117"
ACCENT = "#F5A524"
ACCENT_HOVER = "#FFB84D"
CARD = "#161B22"
BORDER = "#30363D"
TEXT = "#E6EDF3"
MUTED = "#8B949E"
GREEN = "#3FB950"
RED = "#F85149"

def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

BG_RGB = hex_to_rgb(BG)
ACCENT_RGB = hex_to_rgb(ACCENT)
CARD_RGB = hex_to_rgb(CARD)
BORDER_RGB = hex_to_rgb(BORDER)
TEXT_RGB = hex_to_rgb(TEXT)
MUTED_RGB = hex_to_rgb(MUTED)
GREEN_RGB = hex_to_rgb(GREEN)
RED_RGB = hex_to_rgb(RED)

def make_bg(duration):
    """Create animated background."""
    def make_frame(t):
        img = Image.new('RGB', (WIDTH, HEIGHT), BG_RGB)
        draw = ImageDraw.Draw(img)
        
        # Subtle grid pattern
        for i in range(0, WIDTH, 100):
            alpha = int(15 * (0.5 + 0.5 * np.sin(t + i * 0.01)))
            draw.line([(i, 0), (i, HEIGHT)], fill=(*ACCENT_RGB, alpha), width=1)
        for i in range(0, HEIGHT, 100):
            alpha = int(15 * (0.5 + 0.5 * np.cos(t + i * 0.01)))
            draw.line([(0, i), (WIDTH, i)], fill=(*ACCENT_RGB, alpha), width=1)
        
        return np.array(img)
    
    return VideoClip(make_frame, duration=duration)

def ease_out_cubic(t):
    return 1 - (1 - t) ** 3

def ease_out_elastic(t):
    if t == 0: return 0
    if t == 1: return 1
    return 2 ** (-10 * t) * np.sin((t * 10 - 0.75) * 2 * np.pi / 0.3) + 1

def create_video():
    print("Creating Orvima promo video...")
    
    clips = []
    
    # Background
    bg_clip = make_bg(DURATION)
    clips.append(bg_clip)
    
    # Scene 1: Hook (0-5s)
    hook_text = "Your AI agent can browse.\nBut can it send emails?\nWhatsApp? Speak?"
    txt1 = TextClip(None, hook_text, font_size=72, color=TEXT, method='caption', size=(WIDTH-200, None))
    txt1 = txt1.with_duration(5).with_start(0).with_position('center')
    clips.append(txt1)
    
    # Scene 2: Problem (5-10s) - Red X animation
    def make_x_frame(t):
        img = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        progress = min(1, t / 5)
        eased = ease_out_elastic(progress)
        size = int(150 * eased)
        cx, cy = WIDTH // 2, HEIGHT // 2 - 50
        draw.line([cx-size, cy-size, cx+size, cy+size], fill=RED_RGB, width=12)
        draw.line([cx+size, cy-size, cx-size, cy+size], fill=RED_RGB, width=12)
        return np.array(img)
    
    x_clip = VideoClip(make_x_frame, duration=5).with_start(5)
    clips.append(x_clip)
    
    txt2 = TextClip(None, "Most agents hit a wall — no email, no messaging, no voice.", 
                    font_size=48, color=MUTED, method='caption', size=(WIDTH-200, None))
    txt2 = txt2.with_duration(5).with_start(5).with_position('center')
    clips.append(txt2)
    
    # Scene 3: Solution (10-15s) - Orvima logo + feature cards
    def make_solution_frame(t):
        img = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        progress = min(1, t / 5)
        eased = ease_out_cubic(progress)
        
        try:
            font_large = ImageFont.truetype("DejaVuSans-Bold.ttf", 100)
            font_small = ImageFont.truetype("DejaVuSans.ttf", 36)
        except:
            font_large = font_small = ImageFont.load_default()
        
        # Orvima logo
        logo_y = int(HEIGHT * 0.2)
        draw.text((WIDTH//2 - 200, logo_y), "ORVIMA", font=font_large, fill=ACCENT_RGB)
        
        # Feature cards
        features = ["Browser", "Mail", "WhatsApp", "Voice", "Math", "Science"]
        for i, feat in enumerate(features):
            row = i // 3
            col = i % 3
            delay = i * 0.1
            feat_progress = max(0, min(1, (progress - delay) / 0.8))
            feat_eased = ease_out_elastic(feat_progress)
            scale = 0.3 + 0.7 * feat_eased
            
            x = WIDTH//2 - 300 + col * 300
            y = HEIGHT//2 + row * 120
            card_w, card_h = int(250 * scale), int(90 * scale)
            
            draw.rounded_rectangle([x - card_w//2, y - card_h//2, x + card_w//2, y + card_h//2], 
                                 radius=12, fill=CARD_RGB, outline=BORDER_RGB, width=2)
            bbox = draw.textbbox((0, 0), feat, font=font_small)
            w = bbox[2] - bbox[0]
            draw.text((x - w//2, y - 18), feat, font=font_small, fill=TEXT_RGB)
        
        return np.array(img)
    
    sol_clip = VideoClip(make_solution_frame, duration=5).with_start(10)
    clips.append(sol_clip)
    
    # Scene 4: Demo (15-22s) - Terminal animation
    def make_demo_frame(t):
        img = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        scene_t = t  # 0-7 seconds
        
        # Terminal
        term_x, term_y = 100, 150
        term_w, term_h = WIDTH - 200, HEIGHT - 300
        
        draw.rounded_rectangle([term_x, term_y, term_x + term_w, term_y + term_h], 
                             radius=12, fill=(13, 17, 23), outline=BORDER_RGB, width=2)
        draw.rounded_rectangle([term_x, term_y, term_x + term_w, term_y + 40], 
                             radius=12, fill=CARD_RGB, outline=BORDER_RGB, width=2)
        for i, color in enumerate([(255, 95, 86), (255, 189, 46), (40, 205, 65)]):
            draw.ellipse([term_x + 20 + i * 18, term_y + 10, term_x + 32 + i * 18, term_y + 22], fill=color)
        
        commands = [
            ('$ orvima mail_send --to "hr@company.com" --subject "Application"', 0, 2),
            ('✓ Email sent — Message-ID: <20261021.12345@smtp.mailin.fr>', 2, 3.5),
            ('$ orvima whatsapp_send --to "+15551234567" --text "Ready for demo?"', 3.5, 5),
            ('✓ Message delivered — 2 blue ticks confirmed', 5, 6.5),
            ('$ orvima browse_navigate --url "https://github.com"', 6.5, 7.5),
        ]
        
        try:
            font_mono = ImageFont.truetype("DejaVuSansMono.ttf", 28)
        except:
            font_mono = ImageFont.load_default()
        
        for idx, (cmd, start, end) in enumerate(commands):
            if scene_t >= start:
                prog = min(1, (scene_t - start) / (end - start))
                y_pos = term_y + 60 + idx * 55
                color = GREEN_RGB if cmd.startswith('✓') else (TEXT_RGB if not cmd.startswith('$') else (150, 150, 150))
                visible = cmd[:int(len(cmd) * prog)] if not cmd.startswith('✓') else (cmd if prog > 0.3 else "")
                if visible:
                    draw.text((term_x + 30, y_pos), visible, font=font_mono, fill=color)
        
        return np.array(img)
    
    demo_clip = VideoClip(make_demo_frame, duration=7).with_start(15)
    clips.append(demo_clip)
    
    # Scene 5: Features (22-27s) - Badges
    def make_features_frame(t):
        img = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        progress = min(1, t / 5)
        
        badges = [
            ("🛡️", "Safety Gates", "Destructive actions → human approval"),
            ("✅", "Verified Badges", "Every step DOM-verified"),
            ("🏠", "Your Infra", "No cloud lock-in, self-hosted"),
        ]
        
        try:
            font_m = ImageFont.truetype("DejaVuSans.ttf", 42)
            font_s = ImageFont.truetype("DejaVuSans.ttf", 28)
        except:
            font_m = font_s = ImageFont.load_default()
        
        for i, (icon, title, desc) in enumerate(badges):
            delay = i * 0.15
            b_progress = max(0, min(1, (progress - delay) / 0.6))
            b_eased = ease_out_cubic(b_progress)
            scale = 0.2 + 0.8 * b_eased
            x = WIDTH//2 - 450 + i * 450
            y = HEIGHT//2
            card_w, card_h = int(380 * scale), int(220 * scale)
            
            border_color = ACCENT_RGB if b_progress > 0.8 else BORDER_RGB
            draw.rounded_rectangle([x - card_w//2, y - card_h//2, x + card_w//2, y + card_h//2], 
                                 radius=16, fill=CARD_RGB, outline=border_color, width=3)
            draw.text((x - 80, y - 70), title, font=font_m, fill=TEXT_RGB)
            draw.text((x - 150, y + 20), desc, font=font_s, fill=MUTED_RGB)
        
        return np.array(img)
    
    feat_clip = VideoClip(make_features_frame, duration=5).with_start(22)
    clips.append(feat_clip)
    
    # Scene 6: CTA (27-30s)
    def make_cta_frame(t):
        img = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        scene_t = t  # 0-3 seconds
        pulse = 1 + 0.1 * np.sin(scene_t * 4)
        
        try:
            font_l = ImageFont.truetype("DejaVuSans-Bold.ttf", 80)
            font_m = ImageFont.truetype("DejaVuSans.ttf", 48)
        except:
            font_l = font_m = ImageFont.load_default()
        
        cta = "Get started free"
        bbox = draw.textbbox((0, 0), cta, font=font_l)
        w = bbox[2] - bbox[0]
        x = (WIDTH - w) // 2
        y = HEIGHT // 2 - 50
        
        # Pulsing button
        btn_w, btn_h = int((w + 60) * pulse), int(90 * pulse)
        draw.rounded_rectangle([x - 30, y - 10, x + w + 30, y + 80], 
                             radius=16, fill=ACCENT_RGB)
        draw.text((x, y + 10), cta, font=font_l, fill=BG_RGB)
        
        url = "github.com/Sachitt-AV-08/orvima"
        bbox = draw.textbbox((0, 0), url, font=font_m)
        w = bbox[2] - bbox[0]
        x = (WIDTH - w) // 2
        y = HEIGHT // 2 + 80
        draw.text((x, y), url, font=font_m, fill=MUTED_RGB)
        
        return np.array(img)
    
    cta_clip = VideoClip(make_cta_frame, duration=3).with_start(27)
    clips.append(cta_clip)
    
    # Composite all clips
    print("Compositing video...")
    final = CompositeVideoClip(clips, size=(WIDTH, HEIGHT))
    
    # Add audio
    print("Adding voiceover...")
    audio = AudioFileClip("voiceover_fast.mp3")
    final = final.with_audio(audio)
    
    # Write video
    print("Rendering video (this may take a minute)...")
    final.write_videofile(
        "orvima_promo_30s.mp4",
        fps=FPS,
        codec='libx264',
        audio_codec='aac',
        bitrate='8000k',
        preset='medium',
        threads=4,
        logger=None
    )
    
    print("Video created: orvima_promo_30s.mp4")

if __name__ == "__main__":
    create_video()