import os
import aiohttp
import logging
import urllib.parse
import random
import ssl
import socket
import io

# Настройки SSL и IPv4 для стабильности на Render
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

# Константы моделей
FLUX_MODEL = "black-forest-labs/FLUX.1-dev"
IMG2IMG_MODEL = "black-forest-labs/FLUX.1-schnell" 
GFPGAN_MODEL = "TencentARC/GFPGAN"
ESRGAN_MODEL = "nightmareai/real-esrgan"

async def get_session():
    connector = aiohttp.TCPConnector(family=socket.AF_INET, ssl=ssl_context)
    return aiohttp.ClientSession(connector=connector)

async def hf_generate_flux(prompt: str):
    if not HF_TOKEN: return None
    url = f"https://api-inference.huggingface.co/models/{FLUX_MODEL}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "x-wait-for-model": "true"}
    payload = {"inputs": prompt, "parameters": {"guidance_scale": 3.5, "num_inference_steps": 28}}

    async with await get_session() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=90) as r:
                if r.status == 200: return await r.read()
                logging.warning(f"FLUX Error: {r.status}")
                return None
        except Exception as e:
            logging.error(f"FLUX Exception: {e}")
            return None

async def hf_img2img(image_bytes: bytes, prompt: str):
    """ Перерисовывает фото. Для HF API часто используется передача промпта в заголовке или параметрах при отправке байтов """
    if not HF_TOKEN: return None
    url = f"https://api-inference.huggingface.co/models/{IMG2IMG_MODEL}"
    # Передаем промпт в заголовке, чтобы не мучаться с JSON/Base64, так как API HF это поддерживает
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "x-wait-for-model": "true",
        "x-use-cache": "false"
    }
    
    # Для Img2Img часто лучше работает передача промпта как параметра URL или части данных
    async with await get_session() as session:
        try:
            # Отправляем байты изображения напрямую, промпт передаем через параметры
            async with session.post(url, headers=headers, data=image_bytes, params={"prompt": prompt}, timeout=90) as r:
                if r.status == 200:
                    data = await r.read()
                    logging.info("✅ Img2Img success")
                    return data
                logging.error(f"❌ Img2Img Error: {r.status}")
                return None
        except Exception as e:
            logging.error(f"❗ Img2Img Exception: {e}")
            return None

async def pollinations_generate(prompt: str):
    seed = random.randint(1, 999999)
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}&nologo=true"
    async with await get_session() as session:
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
    async with await get_session() as session:
        try:
            async with session.post(url, headers=headers, data=image_bytes, timeout=120) as r:
                if r.status == 200: return await r.read()
                return None
        except: return None
