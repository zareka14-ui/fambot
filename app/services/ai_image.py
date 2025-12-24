import os
import aiohttp
import logging
import urllib.parse
import random
import ssl
import socket

# Настройки SSL и IPv4 для Render
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

# Константы моделей
FLUX_MODEL = "black-forest-labs/FLUX.1-dev"
IMG2IMG_MODEL = "runwayml/stable-diffusion-v1-5" # Самая стабильная для бесплатных Img2Img
GFPGAN_MODEL = "TencentARC/GFPGAN"
ESRGAN_MODEL = "nightmareai/real-esrgan"

async def hf_img2img(image_bytes: bytes, prompt: str):
    if not HF_TOKEN: return None
    url = f"https://api-inference.huggingface.co/models/{IMG2IMG_MODEL}"
    
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "x-wait-for-model": "true"}
    connector = aiohttp.TCPConnector(family=socket.AF_INET, ssl=ssl_context)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            # Метод 1: Multipart FormData (стандарт для многих моделей)
            data = aiohttp.FormData()
            data.add_field('image', image_bytes, filename='image.jpg', content_type='image/jpeg')
            data.add_field('inputs', prompt)

            async with session.post(url, data=data, timeout=90) as r:
                if r.status == 200:
                    res = await r.read()
                    if len(res) > 1000: return res
                
                logging.warning(f"Multipart failed ({r.status}), trying direct bytes...")
                
                # Метод 2: Прямая отправка байтов с промптом в параметрах
                async with session.post(url, headers=headers, data=image_bytes, params={"prompt": prompt}, timeout=90) as r2:
                    if r2.status == 200:
                        res2 = await r2.read()
                        if len(res2) > 1000: return res2
                    
                    logging.error(f"❌ HF Img2Img Final Error: {r2.status}")
                    return None
        except Exception as e:
            logging.error(f"❗ Img2Img Exception: {e}")
            return None

async def hf_generate_flux(prompt: str):
    if not HF_TOKEN: return None
    url = f"https://api-inference.huggingface.co/models/{FLUX_MODEL}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "x-wait-for-model": "true"}
    payload = {"inputs": prompt, "parameters": {"guidance_scale": 3.5, "num_inference_steps": 28}}

    connector = aiohttp.TCPConnector(family=socket.AF_INET, ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=90) as r:
                if r.status == 200: return await r.read()
                return None
        except Exception as e:
            logging.error(f"FLUX Exception: {e}")
            return None

async def pollinations_generate(prompt: str):
    seed = random.randint(1, 999999)
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}&nologo=true"
    
    connector = aiohttp.TCPConnector(family=socket.AF_INET, ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.get(url, timeout=60) as r:
                if r.status == 200: return await r.read()
                return None
        except: return None

async def generate_best(prompt: str):
    img = await hf_generate_flux(prompt)
    if not img: img = await pollinations_generate(prompt)
    return img

async def hf_image_process(image_bytes: bytes, model: str):
    if not HF_TOKEN: return None
    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "x-wait-for-model": "true"}
    
    connector = aiohttp.TCPConnector(family=socket.AF_INET, ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.post(url, headers=headers, data=image_bytes, timeout=120) as r:
                if r.status == 200: return await r.read()
                return None
        except: return None
