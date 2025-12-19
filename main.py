import os
import asyncio
import logging
import sys
import atexit
import signal
from contextlib import asynccontextmanager

from flask import Flask
from threading import Thread, Lock

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramConflictError, TelegramRetryAfter, TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.strategy import FSMStrategy

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import create_engine

# Импорты из ваших модулей
from config.settings import config
from app.handlers.base import base_router, init_db
from app.handlers.base import send_daily_motivation, send_birthday_reminders

# --- SINGLE INSTANCE CHECKER (Улучшенный) ---
class SingleInstanceChecker:
    """Проверка единственного экземпляра с файловой блокировкой"""
    
    def __init__(self, lock_name="fambot.lock"):
        self.lock_file = f"/tmp/{lock_name}"
        self.lock_acquired = False
        self.file_handle = None
        
    def acquire_lock(self) -> bool:
        """Получение блокировки с использованием fcntl"""
        try:
            import fcntl
            
            self.file_handle = open(self.lock_file, 'w')
            
            # Пытаемся получить эксклюзивную блокировку
            try:
                fcntl.flock(self.file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.lock_acquired = True
                
                # Записываем PID текущего процесса
                self.file_handle.write(str(os.getpid()))
                self.file_handle.flush()
                
                # Регистрируем очистку
                def cleanup():
                    if self.lock_acquired:
                        fcntl.flock(self.file_handle, fcntl.LOCK_UN)
                        self.file_handle.close()
                        if os.path.exists(self.lock_file):
                            os.remove(self.lock_file)
                        logging.info("🔒 Блокировка освобождена")
                
                atexit.register(cleanup)
                
                # Обработка сигналов
                def signal_handler(signum, frame):
                    logging.info(f"📶 Получен сигнал {signum}")
                    cleanup()
                    sys.exit(0)
                
                signal.signal(signal.SIGTERM, signal_handler)
                signal.signal(signal.SIGINT, signal_handler)
                
                logging.info("✅ Эксклюзивная блокировка получена")
                return True
                
            except (IOError, BlockingIOError):
                # Файл уже заблокирован другим процессом
                self.file_handle.close()
                logging.error("❌ Бот уже запущен в другом процессе")
                return False
                
        except ImportError:
            # fallback для Windows или систем без fcntl
            return self._acquire_lock_fallback()
        except Exception as e:
            logging.error(f"Ошибка при получении блокировки: {e}")
            return False
    
    def _acquire_lock_fallback(self) -> bool:
        """Резервный метод блокировки для совместимости"""
        try:
            if os.path.exists(self.lock_file):
                with open(self.lock_file, 'r') as f:
                    old_pid = f.read().strip()
                
                # Проверяем, жив ли процесс
                try:
                    os.kill(int(old_pid), 0)
                    logging.error(f"⚠️ Бот уже запущен с PID {old_pid}")
                    return False
                except (OSError, ValueError):
                    os.remove(self.lock_file)
            
            with open(self.lock_file, 'w') as f:
                f.write(str(os.getpid()))
            
            self.lock_acquired = True
            
            def cleanup():
                if self.lock_acquired and os.path.exists(self.lock_file):
                    os.remove(self.lock_file)
                    logging.info("🔒 Блокировка освобождена (fallback)")
            
            atexit.register(cleanup)
            
            logging.info("✅ Блокировка получена (fallback)")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка fallback блокировки: {e}")
            return False
    
    def release_lock(self):
        """Освобождение блокировки"""
        if self.lock_acquired and self.file_handle:
            try:
                import fcntl
                fcntl.flock(self.file_handle, fcntl.LOCK_UN)
            except:
                pass
            self.file_handle.close()
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
            self.lock_acquired = False

# --- КОНФЛИКТЫ TELEGRAM ---
class TelegramConflictHandler:
    """Обработчик конфликтов Telegram с экспоненциальной backoff стратегией"""
    
    def __init__(self, max_retries=5):
        self.max_retries = max_retries
        self.conflict_count = 0
    
    async def execute_with_retry(self, coro_func, *args, **kwargs):
        """Выполнение с повторными попытками при конфликтах"""
        retry = 0
        
        while retry < self.max_retries:
            try:
                return await coro_func(*args, **kwargs)
                
            except TelegramConflictError as e:
                retry += 1
                self.conflict_count += 1
                
                logging.warning(
                    f"⚡ Конфликт Telegram (попытка {retry}/{self.max_retries}): {e}"
                )
                
                if retry >= self.max_retries:
                    logging.error("🚨 Превышен лимит попыток. Возможно, запущен другой бот")
                    if self.conflict_count > 3:
                        logging.critical("⚠️ Множественные конфликты - проверьте дублирующиеся процессы")
                    raise
                
                # Экспоненциальная задержка с jitter
                delay = min(2 ** retry + (retry * 0.5), 30)  # Макс 30 секунд
                logging.info(f"⏳ Ждем {delay:.1f} секунд...")
                await asyncio.sleep(delay)
                
            except TelegramRetryAfter as e:
                logging.warning(f"⏰ Telegram просит подождать {e.retry_after} сек")
                await asyncio.sleep(e.retry_after)
                
            except TelegramNetworkError as e:
                logging.warning(f"🌐 Сетевая ошибка: {e}, пробуем снова...")
                await asyncio.sleep(5)
        
        raise TelegramConflictError("Не удалось выполнить запрос после всех попыток")

# --- FLASK KEEP-ALIVE ---
app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Fambot is running"

@app.route('/health')
def health():
    """Health check для Render и мониторинга"""
    return {
        "status": "healthy",
        "service": "telegram-bot",
        "timestamp": asyncio.get_event_loop().time() if hasattr(asyncio, 'get_event_loop') else 0
    }, 200

@app.route('/status')
def status():
    """Статус бота для отладки"""
    try:
        import psutil
        import socket
        info = {
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "memory": psutil.Process().memory_info().rss / 1024 / 1024,  # MB
            "uptime": psutil.Process().create_time(),
            "conflict_count": getattr(main_bot, 'conflict_handler', None).conflict_count if 'main_bot' in globals() else 0
        }
        return info, 200
    except:
        return {"status": "running", "pid": os.getpid()}, 200

def run_flask():
    """Запуск Flask сервера в отдельном потоке"""
    port = int(os.environ.get('PORT', 8080))
    # Отключаем debug для продакшена
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# --- ОСНОВНОЙ БОТ ---
async def create_bot():
    """Создание и конфигурация бота"""
    # Инициализация базы данных
    await init_db()
    logging.info("✅ База данных инициализирована")
    
    # Создание бота
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=False
        )
    )
    
    # Настройка диспетчера с MemoryStorage
    storage = MemoryStorage()
    dp = Dispatcher(
        storage=storage,
        fsm_strategy=FSMStrategy.USER_IN_CHAT
    )
    
    # Подключаем роутеры
    dp.include_router(base_router)
    logging.info(f"✅ Загружено роутеров: 1 (base)")
    
    return bot, dp

async def setup_scheduler(bot: Bot):
    """Настройка планировщика задач"""
    # Используем SQLAlchemy для хранения задач
    jobstores = {
        'default': SQLAlchemyJobStore(
            engine=create_engine('sqlite:///jobs.sqlite'),
            tablename='apscheduler_jobs'
        )
    }
    
    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        timezone="Europe/Moscow",
        job_defaults={
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 300  # 5 минут
        }
    )
    
    # Ежедневная мотивация
    scheduler.add_job(
        send_daily_motivation,
        'cron',
        hour=7,
        minute=30,
        args=[bot],
        id='daily_motivation',
        replace_existing=True,
        name='Ежедневная мотивация'
    )
    
    # Напоминания о днях рождения
    scheduler.add_job(
        send_birthday_reminders,
        'cron',
        hour=8,
        minute=30,
        args=[bot],
        id='birthday_reminders',
        replace_existing=True,
        name='Напоминания о ДР'
    )
    
    scheduler.start()
    logging.info("✅ Планировщик запущен")
    logging.info(f"   - Мотивация: 7:30 MSK")
    logging.info(f"   - Дни рождения: 8:30 MSK")
    
    return scheduler

@asynccontextmanager
async def bot_lifespan():
    """Контекстный менеджер для управления жизненным циклом бота"""
    # Инициализация
    checker = SingleInstanceChecker()
    if not checker.acquire_lock():
        raise RuntimeError("Бот уже запущен в другом процессе")
    
    bot = None
    scheduler = None
    
    try:
        # Создание бота и планировщика
        bot, dp = await create_bot()
        scheduler = await setup_scheduler(bot)
        
        # Удаляем старые вебхуки
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("✅ Вебхуки очищены")
        
        yield bot, dp, scheduler
        
    finally:
        # Завершение работы
        logging.info("🔄 Завершение работы бота...")
        
        if scheduler and scheduler.running:
            scheduler.shutdown(wait=False)
            logging.info("✅ Планировщик остановлен")
        
        if bot:
            await bot.session.close()
            logging.info("✅ Сессия бота закрыта")
        
        checker.release_lock()
        logging.info("✅ Ресурсы освобождены")

async def main():
    """Основная асинхронная функция"""
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('/tmp/fambot.log', encoding='utf-8')
        ]
    )
    logging.getLogger('apscheduler').setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    
    # Запуск Flask в отдельном потоке
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"🌐 Flask сервер запущен на порту {os.environ.get('PORT', 8080)}")
    
    # Обработчик конфликтов
    conflict_handler = TelegramConflictHandler(max_retries=5)
    
    try:
        async with bot_lifespan() as (bot, dp, scheduler):
            logger.info("🚀 Бот запущен и готов к работе!")
            
            # Основной цикл обработки
            while True:
                try:
                    await conflict_handler.execute_with_retry(
                        dp.start_polling,
                        bot,
                        allowed_updates=dp.resolve_used_update_types(),
                        polling_timeout=30,
                        backoff_config=None
                    )
                except TelegramConflictError as e:
                    logger.critical(f"💥 Критический конфликт: {e}")
                    break
                except Exception as e:
                    logger.error(f"⚠️ Ошибка в основном цикле: {e}")
                    await asyncio.sleep(5)  # Пауза перед перезапуском
    
    except RuntimeError as e:
        logger.error(f"❌ Ошибка запуска: {e}")
    except KeyboardInterrupt:
        logger.info("👋 Завершение по запросу пользователя")
    except Exception as e:
        logger.error(f"💥 Непредвиденная ошибка: {e}", exc_info=True)
    finally:
        logger.info("✅ Бот завершил работу")

if __name__ == '__main__':
    try:
        # Проверка переменных окружения
        required_vars = ['BOT_TOKEN']
        missing = [var for var in required_vars if not os.getenv(var)]
        
        if missing:
            logging.error(f"❌ Отсутствуют переменные окружения: {missing}")
            sys.exit(1)
        
        # Запуск
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logging.info("👋 Завершено пользователем")
    except SystemExit:
        pass
    except Exception as e:
        logging.critical(f"💥 Критическая ошибка при запуске: {e}", exc_info=True)
        sys.exit(1)
