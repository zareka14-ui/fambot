import os
import aiohttp
import logging
import urllib.parse
import random
import ssl
import socket

# Отключаем проверку SSL для пробива handshake
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
GFPGAN_MODEL = "TencentARC/GFPGAN"
ESRGAN_MODEL = "nightmareai/real-esrgan"

async def get_session():
    # Используем Trust DNS (Cloudflare) для резолва имен, если системный DNS на Render сбоит
    connector = aiohttp.TCPConnector(
        family=socket.AF_INET, 
        ssl=ssl_context,
        use_dns_cache=False # Отключаем кэш, чтобы форсировать новый поиск IP
    )
    return aiohttp.ClientSession(connector=connector)

async def pollinations_generate(prompt: str):
    seed = random.randint(1, 999999)
    encoded = urllib.parse.quote(prompt)
    
    # Пытаемся использовать альтернативный домен-зеркало или прямой вызов
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}&nologo=true"
    
    async with await get_session() as session:
        try:
            # Увеличиваем таймаут и добавляем User-Agent, чтобы запрос выглядел как от браузера
            headers = {'User-Agent': 'Mozilla/5.0'}
            async with session.get(url, timeout=60, headers=headers) as r:
                if r.status == 200:
                    data = await r.read()
                    logging.info(f"✅ Картинка получена! ({len(data)} байт)")
                    return data
                logging.error(f"❌ Ошибка сервиса: {r.status}")
                return None
        except Exception as e:
            logging.error(f"❗ Ошибка DNS/Сети: {e}")
            return None

async def hf_generate(prompt: str):
    if not HF_TOKEN: return None
    url = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    async with await get_session() as session:
        try:
            async with session.post(url, headers=headers, json={"inputs": prompt}, timeout=35) as r:
                if r.status == 200: return await r.read()
                return None
        except: return None

async def generate_best(prompt: str):
    # Пробуем HF, затем Pollinations
    img = await hf_generate(prompt)
    if not img:
        img = await pollinations_generate(prompt)
    return img

async def hf_image_process(image_bytes: bytes, model: str):
    if not HF_TOKEN: return None
    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    async with await get_session() as session:
        try:
            async with session.post(url, headers=headers, data=image_bytes, timeout=60) as r:
                if r.status == 200: return await r.read()
                return None
        except: return None
