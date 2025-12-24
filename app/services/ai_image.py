import os
import io
import logging
import random
import urllib.parse
import aiohttp
import socket
import ssl
from huggingface_hub import AsyncInferenceClient

# Настройки логирования
logging.basicConfig(level=logging.INFO)

# Токен и клиент
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
client = AsyncInferenceClient(token=HF_TOKEN)

# Константы моделей
GEN_MODEL = "black-forest-labs/FLUX.1-dev"
IMG2IMG_MODEL = "runwayml/stable-diffusion-v1-5" 
REMOVE_BG_MODEL = "briaai/RMBG-1.4"
GFPGAN_MODEL = "TencentARC/GFPGAN"
ESRGAN_MODEL = "nightmareai/real-esrgan"

# Настройки SSL
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

async def get_session():
    connector = aiohttp.TCPConnector(family=socket.AF_INET, ssl=ssl_context)
    return aiohttp.ClientSession(connector=connector)

# ====== ЗАПАСНОЙ ГЕНЕРАТОР (Pollinations) ======
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

# ====== ГЕНЕРАЦИЯ (FLUX) - РАБОТАЕТ ХОРОШО ======
async def generate_best(prompt: str):
    try:
        output_image = await client.text_to_image(prompt=prompt, model=GEN_MODEL)
        img_byte_arr = io.BytesIO()
        output_image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        logging.warning(f"⚠️ FLUX failed: {e}")
        return await pollinations_generate(prompt)

# ====== ОБРАБОТКА (КЛАССИЧЕСКИЙ API) - ИСПРАВЛЕНИЕ 404 ======
async def hf_classic_query(image_bytes: bytes, model: str, prompt: str = None):
    """Используем классический Inference API, так как роутер не видит бесплатные модели"""
    if not HF_TOKEN: return None
    
    # Прямой путь к модели (наиболее надежный для бесплатных задач)
    url = f"https://api-inference.huggingface.co/models/{model}"
    
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "x-use-cache": "false"
    }

    async with await get_session() as session:
        try:
            # Для SD 1.5 нужен промпт, для RMBG и апскейла - только байты
            params = {"inputs": prompt} if prompt else {}
            
            async with session.post(url, headers=headers, data=image_bytes, params=params, timeout=60) as r:
                if r.status == 200:
                    res = await r.read()
                    if len(res) > 500: return res
                
                # Если 503 - модель "спит", нужно подождать
                if r.status == 503:
                    logging.info(f"⏳ Модель {model} просыпается...")
                
                logging.error(f"❌ HF API Error ({model}): {r.status}")
                return None
        except Exception as e:
            logging.error(f"❌ HF API Exception ({model}): {e}")
            return None

# ====== ПУБЛИЧНЫЕ ФУНКЦИИ ======

async def hf_img2img(image_bytes: bytes, prompt: str):
    return await hf_classic_query(image_bytes, IMG2IMG_MODEL, prompt)

async def hf_remove_bg(image_bytes: bytes):
    return await hf_classic_query(image_bytes, REMOVE_BG_MODEL)

async def hf_image_process(image_bytes: bytes, model: str):
    return await hf_classic_query(image_bytes, model)
