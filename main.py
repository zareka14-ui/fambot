import os
import asyncio
import logging
import sys
import atexit
import signal
from flask import Flask
from threading import Thread, Lock
from functools import wraps

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramConflictError, TelegramRetryAfter
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Импорты из ваших модулей
from config.settings import config
from app.handlers.base import base_router, init_db
from app.handlers.base import send_daily_motivation, send_birthday_reminders

# --- SINGLE INSTANCE CHECKER ---
class SingleInstanceChecker:
    """Проверка, что запущен только один экземпляр бота"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.lock_acquired = False
                cls._instance.lock_file = "/tmp/fambot.lock"
                cls._instance.initialized = False
            return cls._instance
    
    def __init__(self):
        if not self.initialized:
            self.initialized = True
    
    def acquire_lock(self) -> bool:
        """Пытается получить блокировку, возвращает True если успешно"""
        try:
            # Проверяем существующий lock-файл
            if os.path.exists(self.lock_file):
                with open(self.lock_file, 'r') as f:
                    old_pid = f.read().strip()
                
                # Проверяем, жив ли процесс
                try:
                    os.kill(int(old_pid), 0)
                    logging.error(f"⚠️ Бот уже запущен с PID {old_pid}")
                    return False
                except (OSError, ValueError):
                    # Процесс не существует - удаляем старый файл
                    os.remove(self.lock_file)
            
            # Создаем новый lock-файл
            with open(self.lock_file, 'w') as f:
                f.write(str(os.getpid()))
            
            self.lock_acquired = True
            
            # Автоматическое удаление при завершении
            def cleanup():
                if self.lock_acquired and os.path.exists(self.lock_file):
                    os.remove(self.lock_file)
                    logging.info("Lock файл удален")
            
            atexit.register(cleanup)
            
            # Обработка сигналов для корректного завершения
            def signal_handler(signum, frame):
                logging.info(f"Получен сигнал {signum}, завершаем работу...")
                if self.lock_acquired and os.path.exists(self.lock_file):
                    os.remove(self.lock_file)
                sys.exit(0)
            
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
            
            logging.info("✅ Блокировка получена, запускаем бота...")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при получении блокировки: {e}")
            return False
    
    def release_lock(self):
        """Освобождает блокировку"""
        if self.lock_acquired and os.path.exists(self.lock_file):
            os.remove(self.lock_file)
            self.lock_acquired = False

# --- CONFLICT HANDLING DECORATOR ---
def handle_telegram_conflict(max_retries: int = 3):
    """Декоратор для обработки конфликтов Telegram в асинхронных функциях"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retry_count = 0
            base_delay = 1
            
            while retry_count < max_retries:
                try:
                    return await func(*args, **kwargs)
                except TelegramConflictError as e:
                    retry_count += 1
                    logging.warning(
                        f"Конфликт с другим экземпляром бота "
                        f"(попытка {retry_count}/{max_retries}): {e}"
                    )
                    
                    if retry_count >= max_retries:
                        logging.error(
                            "🚨 Достигнут лимит попыток. "
                            "Возможно, запущен другой экземпляр бота."
                        )
                        logging.error("Завершаем работу...")
                        sys.exit(1)
                    
                    # Экспоненциальная задержка с джиттером
                    delay = base_delay * (2 ** retry_count) + (retry_count * 0.1)
                    logging.info(f"Ждем {delay:.2f} секунд перед повторной попыткой...")
                    await asyncio.sleep(delay)
                    
                except TelegramRetryAfter as e:
                    logging.warning(f"Telegram просит подождать: {e} секунд")
                    await asyncio.sleep(e.retry_after)
                    continue
                    
                except Exception as e:
                    logging.error(f"Ошибка в функции {func.__name__}: {e}")
                    raise
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# --- ВЕБ-СЕРВЕР (KEEP ALIVE) ---
app = Flask('')

@app.route('/')
def home():
    return "OK"

@app.route('/health')
def health_check():
    """Эндпоинт для health checks на Render"""
    return {"status": "ok", "service": "fambot"}, 200

def run_flask():
    """Запуск Flask в отдельном потоке"""
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    """Запуск веб-сервера для keep-alive"""
    t = Thread(target=run_flask, daemon=True)
    t.start()
    logging.info(f"Flask keep-alive сервер запущен на порту 8080")

# --- ОСНОВНАЯ ЛОГИКА БОТА ---
@handle_telegram_conflict(max_retries=3)
async def safe_start_polling(dp: Dispatcher, bot: Bot):
    """Безопасный запуск polling с обработкой конфликтов"""
    await dp.start_polling(bot)

async def main():
    # 1. НАСТРОЙКА ЛОГИРОВАНИЯ
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )
    logger = logging.getLogger(__name__)
    
    # 2. ПРОВЕРКА ЕДИНСТВЕННОГО ЭКЗЕМПЛЯРА
    instance_checker = SingleInstanceChecker()
    if not instance_checker.acquire_lock():
        logger.error("Не удалось получить блокировку. Бот уже запущен!")
        sys.exit(1)
    
    try:
        # 3. ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
        try:
            await init_db()
            logger.info("✅ База данных успешно инициализирована")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации базы данных: {e}")
            return

        # 4. ИНИЦИАЛИЗАЦИЯ БОТА
        if not config.bot_token:
            logger.error("❌ BOT_TOKEN не найден в конфигурации!")
            sys.exit(1)
            
        bot = Bot(
            token=config.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        dp = Dispatcher()
        dp.include_router(base_router)

        # 5. НАСТРОЙКА ПЛАНИРОВЩИКА
        scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
        
        # Ежедневная мотивация с красивым фото и свежей цитатой — в 7:30 утра
        scheduler.add_job(
            send_daily_motivation,
            trigger="cron",
            hour=7,
            minute=30,
            args=[bot],
            id="daily_motivation",
            replace_existing=True,
            misfire_grace_time=300  # 5 минут допустимой задержки
        )
        
        # Напоминание о днях рождения — в 8:30 утра
        scheduler.add_job(
            send_birthday_reminders,
            trigger="cron",
            hour=8,
            minute=30,
            args=[bot],
            id="birthday_reminders",
            replace_existing=True,
            misfire_grace_time=300
        )
        
        scheduler.start()
        logger.info("✅ Планировщик запущен: мотивация в 7:30, напоминания о ДР в 8:30")

        # 6. ЗАПУСК БОТА
        logger.info("🚀 Запуск бота на Render...")
        
        # Удаляем вебхук если он был (для чистого старта)
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Вебхук удален, начинаем polling...")
        
        # Запускаем polling с обработкой ошибок
        await safe_start_polling(dp, bot)
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал KeyboardInterrupt")
    except SystemExit:
        logger.info("Получен сигнал SystemExit")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в main(): {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    finally:
        # 7. КОРРЕКТНОЕ ЗАВЕРШЕНИЕ
        logger.info("Завершение работы бота...")
        
        try:
            # Закрываем сессию бота
            await bot.session.close()
            logger.info("✅ Сессия бота закрыта")
        except:
            pass
            
        try:
            # Останавливаем планировщик
            if 'scheduler' in locals() and scheduler.running:
                scheduler.shutdown()
                logger.info("✅ Планировщик остановлен")
        except:
            pass
            
        # Освобождаем блокировку
        instance_checker.release_lock()
        logger.info("✅ Блокировка освобождена")
        
        # Даем время на завершение асинхронных операций
        await asyncio.sleep(1)

if __name__ == '__main__':
    # Запускаем Flask для keep-alive (только для Web Services на Render)
    keep_alive()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
    except SystemExit:
        logging.info("Бот завершил работу")
    except Exception as e:
        logging.error(f"Непредвиденная ошибка: {e}")
        import traceback
        logging.error(traceback.format_exc())
