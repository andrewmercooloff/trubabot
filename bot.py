import os
import re
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
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

# Состояния для диалога
WAITING_FOR_URL, WAITING_FOR_START_TIME, WAITING_FOR_END_TIME = range(3)


def normalize_time(time_str: str) -> str | None:
    """
    Нормализует время до формата HH:MM:SS
    Возвращает None если формат неверный
    """
    # Убираем пробелы
    time_str = time_str.strip()
    
    # Проверяем формат HH:MM:SS
    time_pattern = r'^(\d{1,2}):(\d{2}):(\d{2})$'
    match = re.match(time_pattern, time_str)
    
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        
        # Проверяем валидность
        if minutes >= 60 or seconds >= 60:
            return None
        
        # Форматируем с ведущими нулями
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    # Проверяем формат MM:SS
    time_pattern_mmss = r'^(\d{1,2}):(\d{2})$'
    match = re.match(time_pattern_mmss, time_str)
    
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        
        # Проверяем валидность
        if minutes >= 60 or seconds >= 60:
            return None
        
        # Форматируем как 00:MM:SS
        return f"00:{minutes:02d}:{seconds:02d}"
    
    return None


def is_valid_youtube_url(text: str) -> bool:
    """
    Проверяет, является ли текст валидным URL YouTube
    """
    url_pattern = r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s]+'
    return bool(re.match(url_pattern, text.strip()))


def download_video_segment(url: str, start_time: str, end_time: str) -> Path | None:
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
    """Обработчик команды /start - сразу начинает диалог"""
    await update.message.reply_text(
        "🤖 Привет! Я бот для скачивания фрагментов видео с YouTube."
    )
    # Сразу переходим к запросу URL
    await update.message.reply_text("📎 Отправь ссылку на YouTube видео:")
    return WAITING_FOR_URL


async def download_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало диалога скачивания"""
    await update.message.reply_text("📎 Отправь ссылку на YouTube видео:")
    return WAITING_FOR_URL


async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение URL от пользователя"""
    url = update.message.text.strip()
    
    if not is_valid_youtube_url(url):
        await update.message.reply_text("❌ Это не похоже на ссылку YouTube. Попробуй еще раз:")
        return WAITING_FOR_URL
    
    # Сохраняем URL в контексте
    context.user_data['url'] = url
    
    await update.message.reply_text("⏱️ Отправь время начала в формате 00:00:00:")
    return WAITING_FOR_START_TIME


async def receive_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение времени начала"""
    time_str = update.message.text.strip()
    normalized_time = normalize_time(time_str)
    
    if not normalized_time:
        await update.message.reply_text("❌ Неверный формат времени. Используй формат 00:00:00 (например, 02:21:15):")
        return WAITING_FOR_START_TIME
    
    # Сохраняем время начала
    context.user_data['start_time'] = normalized_time
    
    await update.message.reply_text("⏱️ Отправь время конца в формате 00:00:00:")
    return WAITING_FOR_END_TIME


async def receive_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение времени конца и начало скачивания"""
    time_str = update.message.text.strip()
    normalized_time = normalize_time(time_str)
    
    if not normalized_time:
        await update.message.reply_text("❌ Неверный формат времени. Используй формат 00:00:00 (например, 02:21:50):")
        return WAITING_FOR_END_TIME
    
    # Получаем сохраненные данные
    url = context.user_data.get('url')
    start_time = context.user_data.get('start_time')
    end_time = normalized_time
    
    # Проверяем, что время конца больше времени начала
    start_seconds = sum(int(x) * 60 ** (2 - i) for i, x in enumerate(start_time.split(':')))
    end_seconds = sum(int(x) * 60 ** (2 - i) for i, x in enumerate(end_time.split(':')))
    
    if end_seconds <= start_seconds:
        await update.message.reply_text("❌ Время конца должно быть больше времени начала. Попробуй еще раз:")
        return WAITING_FOR_END_TIME
    
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
    
    # Очищаем данные пользователя
    context.user_data.clear()
    
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена диалога"""
    context.user_data.clear()
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END




def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        return
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Создаем ConversationHandler для диалога скачивания
    download_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("download", download_start)
        ],
        states={
            WAITING_FOR_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_url)],
            WAITING_FOR_START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_start_time)],
            WAITING_FOR_END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_end_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Регистрируем обработчики
    application.add_handler(download_handler)
    
    # Запускаем бота
    logger.info("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

