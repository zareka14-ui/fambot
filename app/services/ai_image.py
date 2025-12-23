import os
import aiohttp
import logging

HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

HF_HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type": "application/json"
}

SDXL_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
FLUX_MODEL = "black-forest-labs/FLUX.1-dev"
GFPGAN_MODEL = "TencentARC/GFPGAN"
ESRGAN_MODEL = "nightmareai/real-esrgan"

async def hf_generate(prompt: str, model=SDXL_MODEL):
    url = f"https://api-inference.huggingface.co/models/{model}"
    payload = {
        "inputs": prompt,
        "parameters": {
            "guidance_scale": 7.5,
            "num_inference_steps": 30,
            "negative_prompt": "blurry, low quality, bad anatomy"
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=HF_HEADERS, json=payload, timeout=120) as r:
            if r.status == 200:
                return await r.read()
            logging.error(f"HF error {r.status}")
            return None

async def hf_image_process(image_bytes: bytes, model: str):
    url = f"https://api-inference.huggingface.co/models/{model}"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            headers=HF_HEADERS,
            data=image_bytes,
            timeout=120
        ) as r:
            if r.status == 200:
                return await r.read()
            logging.error(f"HF process error {r.status}")
            return None

async def generate_best(prompt: str):
    # 1) SDXL
    img = await hf_generate(prompt, SDXL_MODEL)
    if img:
        return img
    # 2) Flux fallback
    return await hf_generate(prompt, FLUX_MODEL)
