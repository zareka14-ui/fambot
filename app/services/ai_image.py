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

# ====== ГЕНЕРАЦИЯ (FLUX) - Оставляем как есть, она работает ======
async def generate_best(prompt: str):
    try:
        output_image = await client.text_to_image(prompt=prompt, model=GEN_MODEL)
        img_byte_arr = io.BytesIO()
        output_image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        logging.warning(f"⚠️ FLUX failed, using Pollinations")
        seed = random.randint(1, 999999)
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}&nologo=true"
        async with await get_session() as session:
            try:
                async with session.get(url, timeout=30) as r:
                    if r.status == 200: return await r.read()
            except: pass
        return None

# ====== НОВЫЙ МЕТОД ОБРАБОТКИ ЧЕРЕЗ TASK-BASED ROUTER ======

async def hf_task_query(image_bytes: bytes, task: str, model: str, prompt: str = None):
    """Запрос к роутеру через указание конкретной задачи (Task)"""
    if not HF_TOKEN: return None
    
    # Новый формат URL: /v1/{task}
    url = f"https://router.huggingface.co/hf-inference/v1/{task}"
    
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    # Упаковываем в FormData, так как новый роутер /v1/ ждет именно этот формат
    data = aiohttp.FormData()
    data.add_field('image', image_bytes, filename='input.jpg', content_type='image/jpeg')
    data.add_field('model', model)
    if prompt:
        data.add_field('prompt', prompt)

    async with await get_session() as session:
        try:
            async with session.post(url, headers=headers, data=data, timeout=60) as r:
                if r.status == 200:
                    return await r.read()
                
                err_text = await r.text()
                logging.error(f"❌ Task Error ({task}): {r.status} - {err_text[:100]}")
                return None
        except Exception as e:
            logging.error(f"❌ Task Exception: {e}")
            return None

# ====== ПУБЛИЧНЫЕ ФУНКЦИИ ======

async def hf_img2img(image_bytes: bytes, prompt: str):
    # Задача для стилизации - image-to-image
    return await hf_task_query(image_bytes, "image-to-image", IMG2IMG_MODEL, prompt)

async def hf_remove_bg(image_bytes: bytes):
    # Задача для удаления фона - image-segmentation
    return await hf_task_query(image_bytes, "image-segmentation", REMOVE_BG_MODEL)

async def hf_image_process(image_bytes: bytes, model: str):
    # Апскейл и лица тоже идут через image-to-image
    return await hf_task_query(image_bytes, "image-to-image", model, "masterpiece, high quality")
    
