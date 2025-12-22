import os
import re
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Создаем директорию для загрузок
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Получаем токен бота
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен в переменных окружения")


def normalize_time(time_str: str) -> str:
    """
    Нормализует время до формата HH:MM:SS
    """
    parts = time_str.split(':')
    if len(parts) == 2:
        # MM:SS -> 00:MM:SS
        return f"00:{parts[0]}:{parts[1]}"
    elif len(parts) == 3:
        # HH:MM:SS -> HH:MM:SS (уже нормализовано)
        return time_str
    return time_str


def parse_time_segment(text: str) -> tuple[str, str] | None:
    """
    Парсит временной сегмент из текста.
    Форматы: "02:21:15-02:21:50" или "2:21:15-2:21:50" или "141:15-141:50"
    Возвращает (start_time, end_time) в формате HH:MM:SS или None
    """
    # Паттерн для времени в формате HH:MM:SS или MM:SS
    time_pattern = r'(\d{1,2}:\d{2}(?::\d{2})?)-(\d{1,2}:\d{2}(?::\d{2})?)'
    match = re.search(time_pattern, text)
    
    if match:
        start = normalize_time(match.group(1))
        end = normalize_time(match.group(2))
        return (start, end)
    return None


def extract_url(text: str) -> str | None:
    """
    Извлекает URL YouTube из текста
    """
    url_pattern = r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s]+'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None


async def download_video_segment(url: str, start_time: str, end_time: str) -> Path | None:
    """
    Скачивает фрагмент видео с YouTube
    """
    # Формируем имя файла (безопасное для файловой системы)
    safe_timestamp = f"{start_time.replace(':', '-')}_{end_time.replace(':', '-')}"
    output_path = DOWNLOAD_DIR / f"video_{safe_timestamp}"
    
    # Опции для yt-dlp
    ydl_opts = {
        'format': 'bv+ba/b',
        'outtmpl': str(output_path) + '.%(ext)s',
        'merge_output_format': 'mkv',
        'download_sections': f'*{start_time}-{end_time}',
        'quiet': False,
        'no_warnings': False,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Проверяем, что файл создан (yt-dlp может добавить расширение)
        expected_path = output_path.with_suffix('.mkv')
        if expected_path.exists():
            return expected_path
        
        # Ищем файл с любым расширением
        for ext in ['.mkv', '.mp4', '.webm', '.m4a']:
            alt_path = output_path.with_suffix(ext)
            if alt_path.exists():
                return alt_path
        
        # Ищем файлы, начинающиеся с нашего имени
        for file in DOWNLOAD_DIR.glob(f"video_{safe_timestamp}*"):
            if file.is_file():
                return file
        
        logger.warning(f"Файл не найден после скачивания: {output_path}")
        return None
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Ошибка yt-dlp при скачивании: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка при скачивании: {e}", exc_info=True)
        return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    welcome_message = """
🤖 Привет! Я бот для скачивания фрагментов видео с YouTube.

📝 Как использовать:
Отправь мне сообщение в формате:
```
URL время_начала-время_конца
```

Пример:
```
https://www.youtube.com/live/oxfbPqnuYac?si=DoEWSHVspA4YwhS 02:21:15-02:21:50
```

Или просто отправь команду /download с URL и временными метками.

⏱️ Формат времени: HH:MM:SS или MM:SS
"""
    await update.message.reply_text(welcome_message)


async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /download"""
    if not context.args:
        await update.message.reply_text(
            "❌ Использование: /download <URL> <время_начала-время_конца>\n"
            "Пример: /download https://youtube.com/watch?v=... 02:21:15-02:21:50"
        )
        return
    
    # Объединяем все аргументы
    text = ' '.join(context.args)
    await process_download_request(update, text)


async def process_download_request(update: Update, text: str):
    """Обрабатывает запрос на скачивание"""
    # Извлекаем URL и временной сегмент
    url = extract_url(text)
    time_segment = parse_time_segment(text)
    
    if not url:
        await update.message.reply_text("❌ Не найден URL YouTube в сообщении")
        return
    
    if not time_segment:
        await update.message.reply_text(
            "❌ Не найден временной сегмент. Формат: HH:MM:SS-HH:MM:SS\n"
            "Пример: 02:21:15-02:21:50"
        )
        return
    
    start_time, end_time = time_segment
    
    # Отправляем сообщение о начале загрузки
    status_msg = await update.message.reply_text(
        f"⏳ Начинаю скачивание фрагмента {start_time}-{end_time}...\n"
        f"🔗 {url}"
    )
    
    try:
        # Скачиваем видео
        video_path = await asyncio.to_thread(
            download_video_segment, url, start_time, end_time
        )
        
        if video_path and video_path.exists():
            # Отправляем видео
            await status_msg.edit_text("✅ Видео скачано! Отправляю...")
            
            file_size = video_path.stat().st_size
            max_size = 50 * 1024 * 1024  # 50 MB - лимит Telegram для видео
            
            if file_size > max_size:
                await status_msg.edit_text(
                    f"❌ Файл слишком большой ({file_size / 1024 / 1024:.1f} MB). "
                    f"Максимальный размер: 50 MB"
                )
            else:
                with open(video_path, 'rb') as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption=f"📹 Фрагмент {start_time}-{end_time}",
                        supports_streaming=True
                    )
                await status_msg.delete()
            
            # Удаляем файл после отправки
            try:
                video_path.unlink()
            except Exception as e:
                logger.warning(f"Не удалось удалить файл {video_path}: {e}")
        else:
            await status_msg.edit_text("❌ Ошибка при скачивании видео. Проверьте URL и временные метки.")
    
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await status_msg.edit_text(f"❌ Произошла ошибка: {str(e)}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик обычных сообщений"""
    text = update.message.text
    if text and (extract_url(text) or parse_time_segment(text)):
        await process_download_request(update, text)
    else:
        await update.message.reply_text(
            "📝 Отправь мне URL YouTube и временной сегмент в формате:\n"
            "URL время_начала-время_конца\n\n"
            "Пример:\n"
            "https://youtube.com/watch?v=... 02:21:15-02:21:50"
        )


def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        return
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("download", download_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    logger.info("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

