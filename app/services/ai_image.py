import os
import io
import logging
import random
import urllib.parse
import aiohttp
import socket
import ssl
from huggingface_hub import AsyncInferenceClient
from PIL import Image

logging.basicConfig(level=logging.INFO)

HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
client = AsyncInferenceClient(token=HF_TOKEN)

# Константы моделей
GEN_MODEL = "black-forest-labs/FLUX.1-dev"
IMG2IMG_MODEL = "runwayml/stable-diffusion-v1-5" 
REMOVE_BG_MODEL = "briaai/RMBG-1.4"
GFPGAN_MODEL = "TencentARC/GFPGAN"
ESRGAN_MODEL = "nightmareai/real-esrgan"

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

async def get_session():
    connector = aiohttp.TCPConnector(family=socket.AF_INET, ssl=ssl_context)
    return aiohttp.ClientSession(connector=connector)

async def pollinations_generate(prompt: str):
    seed = random.randint(1, 999999)
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}&nologo=true"
    async with await get_session() as session:
        try:
            async with session.get(url, timeout=30) as r:
                if r.status == 200: return await r.read()
        except Exception as e:
            logging.error(f"Pollinations Error: {e}")
    return None

async def generate_best(prompt: str):
    """Генерация текста в картинку (FLUX)"""
    try:
        output_image = await client.text_to_image(prompt=prompt, model=GEN_MODEL)
        img_byte_arr = io.BytesIO()
        output_image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        logging.warning(f"⚠️ FLUX busy, using Pollinations: {e}")
        return await pollinations_generate(prompt)

# ====== STYLE (IMAGE TO IMAGE) ======
async def hf_img2img(image_bytes: bytes, prompt: str):
    if not HF_TOKEN: return None
    # Возвращаемся к классическому Inference API
    url = f"https://api-inference.huggingface.co/models/{IMG2IMG_MODEL}"
    
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "image/jpeg"
    }
    
    # Для бесплатного API промпт передается в заголовке или параметрах URL
    params = {"inputs": prompt}

    async with await get_session() as session:
        try:
            async with session.post(url, headers=headers, data=image_bytes, params=params, timeout=60) as r:
                if r.status == 200:
                    return await r.read()
                
                # Если 503 — модель грузится, это нормально
                err_info = await r.text()
                logging.error(f"❌ HF API Style Error: {r.status} - {err_info}")
                return None
        except Exception as e:
            logging.error(f"❌ Style Exception: {e}")
            return None

# ====== REMOVE BACKGROUND ======
async def hf_remove_bg(image_bytes: bytes):
    if not HF_TOKEN: return None
    url = f"https://api-inference.huggingface.co/models/{REMOVE_BG_MODEL}"
    
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "image/jpeg"
    }

    async with await get_session() as session:
        try:
            async with session.post(url, headers=headers, data=image_bytes, timeout=60) as r:
                if r.status == 200:
                    return await r.read()
                logging.error(f"❌ HF API NoBG Status: {r.status}")
                return None
        except Exception as e:
            logging.error(f"❌ NoBG Exception: {e}")
            return None

# ====== FACEFIX / UPSCALE ======
async def hf_image_process(image_bytes: bytes, model: str):
    if not HF_TOKEN: return None
    url = f"https://api-inference.huggingface.co/models/{model}"
    
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "image/jpeg"
    }

    async with await get_session() as session:
        try:
            async with session.post(url, headers=headers, data=image_bytes, timeout=60) as r:
                if r.status == 200:
                    return await r.read()
                return None
        except Exception as e:
            logging.error(f"❌ Process Exception: {e}")
            return None

