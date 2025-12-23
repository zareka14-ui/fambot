import os
import aiohttp
import logging
import urllib.parse
import random
import ssl

# Отключаем проверку SSL, если она блокирует соединение
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

async def get_session():
    # family=2 принудительно заставляет использовать IPv4
    connector = aiohttp.TCPConnector(family=2, ssl=ssl_context)
    return aiohttp.ClientSession(connector=connector)

async def hf_generate(prompt: str):
    if not HF_TOKEN:
        return None
    
    url = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": prompt}

    async with await get_session() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=40) as r:
                if r.status == 200:
                    return await r.read()
                return None
        except Exception as e:
            logging.error(f"HF Connection Error: {e}")
            return None

async def pollinations_generate(prompt: str):
    seed = random.randint(1, 999999)
    encoded = urllib.parse.quote(prompt)
    url = f"https://pollinations.ai/p/{encoded}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
    
    async with await get_session() as session:
        try:
            async with session.get(url, timeout=40) as r:
                if r.status == 200:
                    return await r.read()
                logging.error(f"Pollinations returned status: {r.status}")
                return None
        except Exception as e:
            logging.error(f"Pollinations Connection Error: {e}")
            return None

async def generate_best(prompt: str):
    # Пытаемся получить картинку из любого источника
    img = await hf_generate(prompt)
    if not img:
        logging.info("Switching to fallback (Pollinations)...")
        img = await pollinations_generate(prompt)
    return img
