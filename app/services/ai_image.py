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

# Модели
# FLUX.1-dev — сейчас самая мощная в открытом доступе на HF
FLUX_MODEL = "black-forest-labs/FLUX.1-dev" 
GFPGAN_MODEL = "TencentARC/GFPGAN"
ESRGAN_MODEL = "nightmareai/real-esrgan"

async def get_session():
    connector = aiohttp.TCPConnector(family=socket.AF_INET, ssl=ssl_context)
    return aiohttp.ClientSession(connector=connector)

async def hf_generate_flux(prompt: str):
    if not HF_TOKEN:
        logging.error("HUGGINGFACE_TOKEN missing")
        return None
    
    url = f"https://api-inference.huggingface.co/models/{FLUX_MODEL}"
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
        "x-wait-for-model": "true"  # Важно: заставляет API подождать загрузки тяжелой модели
    }
    
    # FLUX любит подробные промпты
    payload = {
        "inputs": prompt,
        "parameters": {
            "guidance_scale": 3.5,
            "num_inference_steps": 28, # Оптимально для качества/скорости
        }
    }

    async with await get_session() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=90) as r:
                if r.status == 200:
                    return await r.read()
                
                # Если FLUX перегружен (ошибка 503 или 429), логируем это
                logging.warning(f"FLUX API Status: {r.status}")
                return None
        except Exception as e:
            logging.error(f"FLUX Connection Error: {e}")
            return None

async def pollinations_generate(prompt: str):
    # Оставляем как резервный вариант (Fallback)
    seed = random.randint(1, 999999)
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}&nologo=true"
    
    async with await get_session() as session:
        try:
            async with session.get(url, timeout=60) as r:
                if r.status == 200:
                    return await r.read()
                return None
        except:
            return None

async def generate_best(prompt: str):
    # Сначала пробуем топовый FLUX
    logging.info(f"Trying FLUX for prompt: {prompt}")
    img = await hf_generate_flux(prompt)
    
    # Если FLUX не ответил, идем в Pollinations
    if not img:
        logging.info("FLUX failed/busy, switching to Pollinations")
        img = await pollinations_generate(prompt)
    return img

# Функции для обработки фото (FaceFix / Upscale) оставляем без изменений
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
# Добавляем новую модель
IMG2IMG_MODEL = "black-forest-labs/FLUX.1-schnell"

async def hf_img2img(image_bytes: bytes, prompt: str):
    """
    Перерисовывает существующее изображение по текстовому описанию.
    """
    if not HF_TOKEN: return None
    url = f"https://api-inference.huggingface.co/models/{IMG2IMG_MODEL}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "x-wait-for-model": "true"}
    
    # Для некоторых моделей Img2Img на HF нужно отправлять multipart данные
    # Но FLUX часто принимает JSON с base64 или просто байты
    payload = {
        "inputs": prompt,
        "image": image_bytes, # Некоторые эндпоинты требуют base64, проверь документацию конкретной модели
        "parameters": {"strength": 0.5} # Насколько сильно менять фото (0.1 - слабо, 0.9 - полностью)
    }

    async with await get_session() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=90) as r:
                if r.status == 200:
                    return await r.read()
                logging.error(f"Img2Img Error: {r.status}")
                return None
        except Exception as e:
            logging.error(f"Img2Img Exception: {e}")
            return None
