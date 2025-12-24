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

# Настройки логирования
logging.basicConfig(level=logging.INFO)

# Токен и клиент Hugging Face
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
client = AsyncInferenceClient(token=HF_TOKEN)

# Константы моделей (актуальные на конец 2025 года)
GEN_MODEL = "black-forest-labs/FLUX.1-dev"
IMG2IMG_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
GFPGAN_MODEL = "TencentARC/GFPGAN"
ESRGAN_MODEL = "nightmareai/real-esrgan"
REMOVE_BG_MODEL = "briaai/RMBG-1.4"

# Настройки SSL для aiohttp (нужны для Render)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

async def get_session():
    """Создает сессию с принудительным IPv4"""
    connector = aiohttp.TCPConnector(family=socket.AF_INET, ssl=ssl_context)
    return aiohttp.ClientSession(connector=connector)

async def pollinations_generate(prompt: str):
    """Резервный генератор (Fallback), если Hugging Face недоступен"""
    seed = random.randint(1, 999999)
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}&nologo=true"
    
    async with await get_session() as session:
        try:
            async with session.get(url, timeout=30) as r:
                if r.status == 200:
                    return await r.read()
        except Exception as e:
            logging.error(f"Pollinations Error: {e}")
    return None

async def generate_best(prompt: str):
    """Генерация изображения: сначала FLUX, затем Pollinations"""
    try:
        # Прямой вызов через новый роутер HF
        output_image = await client.text_to_image(
            prompt=prompt,
            model=GEN_MODEL
        )
        img_byte_arr = io.BytesIO()
        output_image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        logging.warning(f"⚠️ FLUX failed/busy, switching to Pollinations: {e}")
        return await pollinations_generate(prompt)

async def hf_img2img(image_bytes: bytes, prompt: str):
    if not HF_TOKEN: return None
    try:
        input_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # Явно указываем задачу 'image-to-image'
        output_image = await client.image_to_image(
            image=input_image,
            prompt=prompt,
            model=IMG2IMG_MODEL,
            strength=0.5,
            task="image-to-image" # <--- Добавляем явное указание задачи
        )
        
        img_byte_arr = io.BytesIO()
        output_image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        # Если SDXL не тянет, пробуем более легкую модель
        logging.error(f"❌ HF Router Error (Img2Img): {e}")
        return None

async def hf_remove_bg(image_bytes: bytes):
    if not HF_TOKEN: return None
    try:
        input_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # Для сегментации тоже указываем задачу явно
        output_image = await client.image_segmentation(
            image=input_image,
            model="briaai/RMBG-1.4",
            task="image-segmentation" # <--- Явное указание
        )
        
        img_byte_arr = io.BytesIO()
        output_image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        logging.error(f"❌ HF Remove BG Error: {e}")
        return None

async def hf_image_process(image_bytes: bytes, model: str):
    """Улучшение лица (GFPGAN) или Апскейл (ESRGAN)"""
    if not HF_TOKEN: return None
    try:
        input_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # Для большинства моделей обработки лиц на HF используется image_to_image
        output_image = await client.image_to_image(
            image=input_image,
            prompt="high quality, masterpiece, sharp focus",
            model=model
        )
        
        img_byte_arr = io.BytesIO()
        output_image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        logging.error(f"❌ HF Router Error (Process): {e}")
        return None

async def hf_remove_bg(image_bytes: bytes):
    """Удаление фона через сегментацию"""
    if not HF_TOKEN: return None
    try:
        input_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        output_image = await client.image_segmentation(
            image=input_image,
            model=REMOVE_BG_MODEL
        )
        
        img_byte_arr = io.BytesIO()
        output_image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        logging.error(f"❌ HF Remove BG Error: {e}")
        return None
