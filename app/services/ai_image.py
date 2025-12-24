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

async def hf_img2img(image_bytes: bytes, prompt: str):
    """Стилизация (Img2Img) через Router"""
    if not HF_TOKEN: return None
    url = "https://router.huggingface.co/hf-inference/v1/image-to-image"
    
    data = aiohttp.FormData()
    data.add_field('image', image_bytes, filename='input.jpg', content_type='image/jpeg')
    data.add_field('prompt', prompt)
    data.add_field('model', IMG2IMG_MODEL)

    async with await get_session() as session:
        try:
            async with session.post(url, headers={"Authorization": f"Bearer {HF_TOKEN}"}, data=data) as r:
                if r.status == 200: return await r.read()
                logging.error(f"❌ Style Error: {r.status}")
                return None
        except Exception as e:
            logging.error(f"❌ Style Exception: {e}")
            return None

async def hf_remove_bg(image_bytes: bytes):
    """Удаление фона (Segmentation) через Router"""
    if not HF_TOKEN: return None
    url = "https://router.huggingface.co/hf-inference/v1/image-segmentation"
    
    data = aiohttp.FormData()
    data.add_field('image', image_bytes, filename='input.jpg', content_type='image/jpeg')
    data.add_field('model', REMOVE_BG_MODEL)

    async with await get_session() as session:
        try:
            async with session.post(url, headers={"Authorization": f"Bearer {HF_TOKEN}"}, data=data) as r:
                if r.status == 200: return await r.read()
                logging.error(f"❌ NoBG Error: {r.status}")
                return None
        except Exception as e:
            logging.error(f"❌ NoBG Exception: {e}")
            return None

async def hf_image_process(image_bytes: bytes, model: str):
    """Апскейл и Лица (через универсальный Image-to-Image эндпоинт)"""
    if not HF_TOKEN: return None
    # Важно: используем тот же роутер, так как старые эндпоинты могут выдать 410
    url = "https://router.huggingface.co/hf-inference/v1/image-to-image"
    
    data = aiohttp.FormData()
    data.add_field('image', image_bytes, filename='input.jpg', content_type='image/jpeg')
    data.add_field('model', model)
    data.add_field('prompt', "masterpiece, high quality, sharp focus")

    async with await get_session() as session:
        try:
            async with session.post(url, headers={"Authorization": f"Bearer {HF_TOKEN}"}, data=data) as r:
                if r.status == 200: return await r.read()
                logging.error(f"❌ Process Error: {r.status}")
                return None
        except Exception as e:
            logging.error(f"❌ Process Exception: {e}")
            return None
