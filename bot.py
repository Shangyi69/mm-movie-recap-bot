import subprocess
import os
import asyncio
import edge_tts
import uuid
import random
from openai import OpenAI
import whisper
import re
import glob
import shutil
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import logging

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load Whisper
logger.info("🔄 Loading Whisper model...")
whisper_model = whisper.load_model("tiny", device="cpu")
logger.info("✅ Whisper model loaded")

# API Keys
API_KEYS = [k for k in [os.getenv(f"GEMINI_API_KEY_{i}") for i in range(1, 6)] if k]
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not API_KEYS:
    raise ValueError("At least one GEMINI_API_KEY is required")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is required")

def get_ds_client():
    return OpenAI(
        api_key=random.choice(API_KEYS),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        timeout=600.0
    )

def cleanup_old_files():
    for pattern in ["final_*.mp4", "temp_*", "telegram_*.mp4", "list.txt"]:
        for f in glob.glob(pattern):
            try:
                (shutil.rmtree if os.path.isdir(f) else os.remove)(f)
            except: pass

def get_duration(file_path):
    try:
        result = subprocess.run(
            f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{file_path}"',
            shell=True, capture_output=True, text=True
        )
        return float(result.stdout.strip())
    except: return 0

def smart_text_processor(full_text):
    clean = re.sub(r'\(.*?\d+.*?\)|#+.*?\d+.*?-.*?\d+|\d+[:\.]\d+[:\.]\d+|\d+[:\.]\d+|#+.*?\d+[:\.]\d+', '', full_text)
    clean = re.sub(r'[a-zA-Z]|\(|\)|\[|\]|\.|\.\.\.|\-|\!|\#', '', clean)
    sentences = [s.strip() for s in re.split(r'[။।\.]', clean) if s.strip()]
    return [" ".join(sentences[i:i+3]).replace("။", "") + "။" for i in range(0, len(sentences), 3)]

def generate_draft(video_path, voice_choice):
    if not video_path: return "Error: No Video", ""
    particle = "ရှင်" if voice_choice == "Female" else "ဗျာ"
    prompt = f"""Translate to Burmese storytelling style. Remove timelines. No English. Use {particle} naturally. No intro/outro."""
    
    try:
        text = whisper_model.transcribe(video_path, fp16=False)['text']
        client = get_ds_client()
        
        script = client.chat.completions.create(
            model="gemini-2.5-flash-lite",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text}],
            max_tokens=8192
        ).choices[0].message.content.strip()
        
        title = client.chat.completions.create(
            model="gemini-2.5-flash-lite",
            messages=[{"role": "user", "content": f"Viral Burmese title + 5 hashtags: {text}"}],
            max_tokens=200
        ).choices[0].message.content.strip()
        
        return script, title
    except Exception as e:
        logger.error(f"Draft error: {e}")
        return f"Error: {e}", ""

async def final_production(video_path, script, title, voice, speed, watermark):
    if not script: return None, "Error: No Script"
    cleanup_old_files()
    
    task_id = uuid.uuid4().hex[:8]
    temp_dir = f"temp_{task_id}"
    os.makedirs(temp_dir, exist_ok=True)
    output = f"final_{task_id}.mp4"
    audio_out = f"{temp_dir}/combined.mp3"
    
    try:
        # TTS
        paragraphs = smart_text_processor(script)
        voice_name = "my-MM-NilarNeural" if voice == "Female" else "my-MM-ThihaNeural"
        rate = f"+{int(speed)}%"
        
        audio_parts = []
        for i, text in enumerate(paragraphs):
            path = f"{temp_dir}/p_{i:03d}.mp3"
            await edge_tts.Communicate(text, voice_name, rate=rate).save(path)
            audio_parts.append(path)
        
        # Combine audio
        list_file = f"{temp_dir}/list.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for a in audio_parts:
                f.write(f"file '{os.path.abspath(a)}'\n")
        
        subprocess.run(
            f'ffmpeg -f concat -safe 0 -i "{list_file}" '
            f'-af "silenceremove=start_periods=1:stop_periods=-1:stop_duration=0.1:stop_threshold=-50dB" '
            f'-c:a libmp3lame -q:a 2 "{audio_out}"',
            shell=True, check=True
        )
        
        # Video processing
        v_dur = get_duration(video_path)
        a_dur = get_duration(audio_out)
        ratio = a_dur / v_dur if v_dur > 0 else 1
        
        filters = [
            f"setpts={ratio}*PTS",
            "crop=iw:ih*0.82:0:0,scale=iw:ih",
            "hflip",
            "eq=brightness=0.06:contrast=1.2:saturation=1.4"
        ]
        
        v_filter = ",".join(filters)
        
        if watermark:
            v_filter += f",drawtext=text='{watermark.replace(chr(39), '')}':x=w-tw-40:y=40:fontsize=35:fontcolor=white:shadowcolor=black:shadowx=2:shadowy=2"
        
        v_filter += "[outv]"
        a_filter = "[1:a]volume=9.0[outa]"
        
        cmd = f'ffmpeg -y -i "{video_path}" -i "{audio_out}" -filter_complex "{v_filter};{a_filter}" -map "[outv]" -map "[outa]" -c:v libx264 -crf 23 -preset fast -shortest "{output}"'
        subprocess.run(cmd, shell=True, check=True)
        
        return output, "Success"
    except Exception as e:
        logger.error(f"Production error: {e}")
        return None, f"Error: {e}"

# ==================== TELEGRAM BOT HANDLERS ====================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 **MM Movie Recap Bot**\n\n"
        "📹 **အသုံးပြုနည်း:**\n"
        "Video file ပို့ပါ → Myanmar အသံနဲ့ Recap ရမယ်\n\n"
        "⚙️ **Commands:**\n"
        "/voice male/female - အသံရွေးမယ်\n"
        "/speed 0-50 - အမြန်သတ်မှတ်မယ်\n"
        "/watermark <text> - Watermark ထည့်မယ်\n"
        "/settings - လက်ရှိ settings\n"
        "/help - အကူအညီ\n\n"
        "📤 Video ပို့ပါ!",
        parse_mode='Markdown'
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **လမ်းညွှန်**\n\n"
        "1. Video file ပို့ပါ\n"
        "2. Bot က processing လုပ်မယ် (2-5 min)\n"
        "3. Myanmar recap video ရမယ်\n\n"
        "⚙️ /voice, /speed, /watermark နဲ့ customize လုပ်လို့ရ",
        parse_mode='Markdown'
    )

async def voice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0].lower() not in ['male', 'female']:
        await update.message.reply_text("❌ /voice male သို့ /voice female")
        return
    context.user_data['voice'] = context.args[0].capitalize()
    await update.message.reply_text(f"✅ အသံ: {context.user_data['voice']}")

async def speed_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        speed = int(context.args[0])
        if 0 <= speed <= 50:
            context.user_data['speed'] = speed
            await update.message.reply_text(f"✅ အမြန်: {speed}%")
        else:
            await update.message.reply_text("❌ 0-50 အတွင်း")
    except:
        await update.message.reply_text("❌ /speed 30")

async def watermark_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        context.user_data['watermark'] = ' '.join(context.args)
        await update.message.reply_text(f"✅ Watermark: {context.user_data['watermark']}")
    else:
        await update.message.reply_text("❌ /watermark MM RECAP")

async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚙️ **Settings**\n\n"
        f"🗣️ Voice: {context.user_data.get('voice', 'Male')}\n"
        f"⏩ Speed: {context.user_data.get('speed', 30)}%\n"
        f"🏷️ Watermark: {context.user_data.get('watermark', 'MM RECAP')}",
        parse_mode='Markdown'
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    settings = {
        'voice': context.user_data.get('voice', 'Male'),
        'speed': context.user_data.get('speed', 30),
        'watermark': context.user_data.get('watermark', 'MM RECAP')
    }
    
    await update.message.reply_text("📥 Video လက်ခံရရှိပါပြီ... Processing ⏳")
    
    try:
        video = update.message.video
        file = await context.bot.get_file(video.file_id)
        video_path = f"telegram_{user_id}_{uuid.uuid4().hex[:8]}.mp4"
        await file.download_to_drive(video_path)
        
        await update.message.reply_text("🎙️ STEP 1: Script generation...")
        script, title = generate_draft(video_path, settings['voice'])
        
        if script.startswith("Error"):
            await update.message.reply_text(f"❌ {script}")
            os.remove(video_path)
            return
        
        await update.message.reply_text(
            f"📝 **{title}**\n\n"
            f"_STEP 2: Video rendering... (2-3 minutes)_",
            parse_mode='Markdown'
        )
        
        output, status = await final_production(
            video_path, script, title,
            settings['voice'], settings['speed'], settings['watermark']
        )
        
        if status == "Success" and output:
            await update.message.reply_text("✅ အောင်မြင်ပါပြီ! ပို့နေပါသည်...")
            
            with open(output, 'rb') as vf:
                await update.message.reply_video(
                    video=vf,
                    caption=f"🎬 **{title}**\n\n"
                           f"⚙️ Voice: {settings['voice']} | Speed: {settings['speed']}%",
                    parse_mode='Markdown'
                )
            
            # Cleanup
            os.remove(video_path)
            os.remove(output)
            cleanup_old_files()
        else:
            await update.message.reply_text(f"❌ {status}")
    
    except Exception as e:
        logger.error(f"Video processing error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ==================== MAIN ====================

async def main():
    """Run the bot"""
    logger.info("🤖 Starting Telegram Bot...")
    
    # Build application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("voice", voice_cmd))
    app.add_handler(CommandHandler("speed", speed_cmd))
    app.add_handler(CommandHandler("watermark", watermark_cmd))
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    
    logger.info("✅ Bot started successfully - Polling mode")
    
    # Start polling
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    asyncio.run(main())
