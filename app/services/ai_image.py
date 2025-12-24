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

# Константы моделей
GEN_MODEL = "black-forest-labs/FLUX.1-dev"
IMG2IMG_MODEL = "runwayml/stable-diffusion-v1-5" # Самая стабильная для Img2Img
GFPGAN_MODEL = "TencentARC/GFPGAN"
ESRGAN_MODEL = "nightmareai/real-esrgan"
REMOVE_BG_MODEL = "briaai/RMBG-1.4"

# Настройки SSL для aiohttp
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
    try:
        output_image = await client.text_to_image(prompt=prompt, model=GEN_MODEL)
        img_byte_arr = io.BytesIO()
        output_image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        logging.warning(f"⚠️ FLUX failed, switching to Pollinations: {e}")
        return await pollinations_generate(prompt)

async def hf_img2img(image_bytes: bytes, prompt: str):
    if not HF_TOKEN: return None
    try:
        # Используем прямой post, чтобы обойти ошибки провайдеров типа 'nscale'
        response = await client.post(
            data=image_bytes,
            model=IMG2IMG_MODEL,
            task="image-to-image",
            params={"prompt": prompt, "strength": 0.5}
        )
        # Если пришел ответ в байтах, возвращаем его
        if isinstance(response, bytes): return response
        
        # Если пришел PIL Image, сохраняем в байты
        img_byte_arr = io.BytesIO()
        response.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        logging.error(f"❌ HF Router Error (Img2Img): {e}")
        return None

async def hf_remove_bg(image_bytes: bytes):
    if not HF_TOKEN: return None
    try:
        # Для сегментации тоже используем прямой post
        response = await client.post(
            data=image_bytes,
            model=REMOVE_BG_MODEL,
            task="image-segmentation"
        )
        if isinstance(response, bytes): return response
        
        img_byte_arr = io.BytesIO()
        response.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        logging.error(f"❌ HF Remove BG Error: {e}")
        return None

async def hf_image_process(image_bytes: bytes, model: str):
    if not HF_TOKEN: return None
    try:
        input_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
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
