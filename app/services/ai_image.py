import os
import aiohttp
import logging
import urllib.parse
import random
import ssl

# Конфигурация для Render (IPv4 + SSL bypass)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

# Константы моделей, которые просит твой base.py
GFPGAN_MODEL = "TencentARC/GFPGAN"
ESRGAN_MODEL = "nightmareai/real-esrgan"

async def get_session():
    connector = aiohttp.TCPConnector(family=2, ssl=ssl_context)
    return aiohttp.ClientSession(connector=connector)

async def hf_generate(prompt: str):
    if not HF_TOKEN: return None
    url = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    async with await get_session() as session:
        try:
            async with session.post(url, headers=headers, json={"inputs": prompt}, timeout=40) as r:
                if r.status == 200: return await r.read()
                return None
        except: return None

async def pollinations_generate(prompt: str):
    seed = random.randint(1, 999999)
    encoded = urllib.parse.quote(prompt)
    url = f"https://pollinations.ai/p/{encoded}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
    async with await get_session() as session:
        try:
            async with session.get(url, timeout=40) as r:
                if r.status == 200: return await r.read()
                return None
        except: return None

async def generate_best(prompt: str):
    img = await hf_generate(prompt)
    if not img: img = await pollinations_generate(prompt)
    return img

# Функция для кнопок "FaceFix" и "Upscale"
async def hf_image_process(image_bytes: bytes, model: str):
    if not HF_TOKEN: return None
    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    async with await get_session() as session:
        try:
            async with session.post(url, headers=headers, data=image_bytes, timeout=60) as r:
                if r.status == 200: return await r.read()
                logging.error(f"Image process error: {r.status}")
                return None
        except Exception as e:
            logging.error(f"Image process exception: {e}")
            return None
