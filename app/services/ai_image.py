import os
import io
import logging
import random
import urllib.parse
import aiohttp
import socket
import ssl
from huggingface_hub import AsyncInferenceClient

logging.basicConfig(level=logging.INFO)

HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
client = AsyncInferenceClient(token=HF_TOKEN)

# Модели
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
    try:
        output_image = await client.text_to_image(prompt=prompt, model=GEN_MODEL)
        img_byte_arr = io.BytesIO()
        output_image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        logging.warning(f"⚠️ FLUX busy: {e}")
        return await pollinations_generate(prompt)

async def hf_router_query(image_bytes: bytes, model: str, prompt: str = "process image"):
    """Универсальная функция для нового Router API"""
    if not HF_TOKEN: return None
    
    # Эндпоинт, который HF просит использовать вместо старого
    url = f"https://router.huggingface.co/hf-inference/models/{model}"
    
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    # Router теперь часто требует multipart даже для простых моделей
    data = aiohttp.FormData()
    data.add_field('image', image_bytes, filename='input.jpg', content_type='image/jpeg')
    data.add_field('inputs', prompt) 

    async with await get_session() as session:
        try:
            async with session.post(url, headers=headers, data=data, timeout=60) as r:
                if r.status == 200:
                    return await r.read()
                
                # Если multipart не помог, пробуем отправить как raw binary (fallback)
                if r.status in [400, 415]:
                    async with session.post(url, headers=headers, data=image_bytes, params={"inputs": prompt}) as r2:
                        if r2.status == 200: return await r2.read()
                
                logging.error(f"❌ Router Error for {model}: {r.status}")
                return None
        except Exception as e:
            logging.error(f"❌ Router Exception: {e}")
            return None

# Привязываем функции к универсальному роутеру
async def hf_img2img(image_bytes: bytes, prompt: str):
    return await hf_router_query(image_bytes, IMG2IMG_MODEL, prompt)

async def hf_remove_bg(image_bytes: bytes):
    # Для удаления фона промпт формален, но он нужен роутеру
    return await hf_router_query(image_bytes, REMOVE_BG_MODEL, "transparent background")

async def hf_image_process(image_bytes: bytes, model: str):
    return await hf_router_query(image_bytes, model, "enhance quality")
