import os
import aiohttp
import logging
import urllib.parse
import random
import ssl
import socket

# Глобальные настройки SSL для пробива блокировок
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
GFPGAN_MODEL = "TencentARC/GFPGAN"
ESRGAN_MODEL = "nightmareai/real-esrgan"

async def pollinations_generate(prompt: str):
    seed = random.randint(1, 999999)
    encoded = urllib.parse.quote(prompt)
    url = f"https://pollinations.ai/p/{encoded}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
    
    # Решаем проблему EAI_NONAME и IPv6 через принудительный IPv4 и доверенный DNS
    connector = aiohttp.TCPConnector(family=socket.AF_INET, ssl=ssl_context)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as r:
                if r.status == 200:
                    return await r.read()
                logging.error(f"Pollinations error status: {r.status}")
                return None
        except Exception as e:
            logging.error(f"Pollinations Connection Error: {e}")
            return None

async def hf_generate(prompt: str):
    if not HF_TOKEN: return None
    url = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    connector = aiohttp.TCPConnector(family=socket.AF_INET, ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.post(url, headers=headers, json={"inputs": prompt}, timeout=30) as r:
                if r.status == 200: return await r.read()
                return None
        except: return None

async def generate_best(prompt: str):
    # План А: HF
    img = await hf_generate(prompt)
    if img: return img
    # План Б: Pollinations
    return await pollinations_generate(prompt)

async def hf_image_process(image_bytes: bytes, model: str):
    if not HF_TOKEN: return None
    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    connector = aiohttp.TCPConnector(family=socket.AF_INET, ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.post(url, headers=headers, data=image_bytes, timeout=60) as r:
                if r.status == 200: return await r.read()
                return None
        except: return None
