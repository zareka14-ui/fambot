import os
import io
import logging
from huggingface_hub import AsyncInferenceClient
from PIL import Image

HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

# Инициализируем клиент один раз
client = AsyncInferenceClient(token=HF_TOKEN)

# Модели
GEN_MODEL = "black-forest-labs/FLUX.1-dev"
IMG2IMG_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
GFPGAN_MODEL = "TencentARC/GFPGAN"

async def hf_img2img(image_bytes: bytes, prompt: str):
    """Стилизация через новый роутер HF"""
    if not HF_TOKEN: return None
    
    try:
        # Конвертируем байты в объект PIL Image (этого требует клиент)
        input_image = Image.open(io.BytesIO(image_bytes))
        
        # Вызов через официальный клиент (он сам найдет правильный URL)
        output_image = await client.image_to_image(
            image=input_image,
            prompt=prompt,
            model=IMG2IMG_MODEL,
            strength=0.5
        )
        
        # Конвертируем результат обратно в байты для отправки в Telegram
        img_byte_arr = io.BytesIO()
        output_image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
        
    except Exception as e:
        logging.error(f"❌ HF Router Error (Img2Img): {e}")
        return None

async def generate_best(prompt: str):
    """Генерация с нуля через FLUX (новый эндпоинт)"""
    try:
        output_image = await client.text_to_image(
            prompt=prompt,
            model=GEN_MODEL
        )
        img_byte_arr = io.BytesIO()
        output_image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        logging.error(f"❌ HF Router Error (Gen): {e}")
        # Здесь можно оставить ваш старый fallback на Pollinations
        return None

async def hf_image_process(image_bytes: bytes, model: str):
    """Для моделей апскейла и лиц"""
    try:
        # Клиент сам разберется, какой тип задачи вызвать по ID модели
        input_image = Image.open(io.BytesIO(image_bytes))
        output_image = await client.image_to_image(
            image=input_image,
            prompt="", # Для GFPGAN промпт не важен
            model=model
        )
        img_byte_arr = io.BytesIO()
        output_image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        logging.error(f"❌ HF Router Error (Process): {e}")
        return None
