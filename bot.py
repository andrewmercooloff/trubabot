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
    Пытается использовать download_sections для скачивания только нужного фрагмента
    """
    import subprocess
    
    # Формируем имя файла (безопасное для файловой системы)
    safe_timestamp = f"{start_time.replace(':', '-')}_{end_time.replace(':', '-')}"
    output_path = DOWNLOAD_DIR / f"video_{safe_timestamp}"
    
    # Вычисляем длительность для download_sections
    start_seconds = sum(int(x) * 60 ** (2 - i) for i, x in enumerate(start_time.split(':')))
    end_seconds = sum(int(x) * 60 ** (2 - i) for i, x in enumerate(end_time.split(':')))
    duration = end_seconds - start_seconds
    
    # Опции для yt-dlp - пытаемся скачать только нужный фрагмент
    # download_sections работает с форматами, которые поддерживают сегментированную загрузку
    ydl_opts = {
        'format': 'bv+ba/b',  # Лучшее видео + лучшее аудио
        'outtmpl': str(output_path) + '.%(ext)s',
        'merge_output_format': 'mp4',  # Используем mp4 для совместимости с мобильными устройствами
        'download_sections': f'*{start_time}-{end_time}',  # Пытаемся скачать только сегмент
        'quiet': False,
        'no_warnings': False,
        'extract_flat': False,
        # Опции для обхода блокировок YouTube
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'referer': 'https://www.youtube.com/',
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],  # Пробуем разные клиенты
            }
        },
    }
    
    try:
        logger.info(f"Пытаюсь скачать только фрагмент: URL={url}, сегмент={start_time}-{end_time}")
        
        # Пытаемся скачать только нужный фрагмент
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        logger.info(f"Скачивание завершено, ищу файл: {output_path}")
        
        # Проверяем, что файл создан (yt-dlp может добавить расширение)
        # Сначала проверяем mp4 (merge_output_format)
        expected_path = output_path.with_suffix('.mp4')
        if expected_path.exists():
            file_size = expected_path.stat().st_size
            logger.info(f"Фрагмент скачан напрямую: {expected_path}, размер: {file_size / 1024 / 1024:.2f} MB")
            
            # Проверяем размер - если файл слишком большой, значит скачался весь файл
            # Примерно: 30 секунд видео в максимальном качестве должно быть < 100 MB
            # Если файл > 500 MB, вероятно скачался весь файл
            if file_size > 500 * 1024 * 1024:  # Больше 500 MB
                logger.warning(f"Файл слишком большой ({file_size / 1024 / 1024:.2f} MB), возможно скачался весь файл")
                logger.info("Обрезаю и перекодирую через ffmpeg для совместимости...")
                # Обрезаем и перекодируем через ffmpeg в совместимый формат
                final_path = DOWNLOAD_DIR / f"video_{safe_timestamp}.mp4"
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-i', str(expected_path),
                    '-ss', start_time,
                    '-t', str(duration),
                    '-c:v', 'libx264',  # Перекодируем видео в H.264
                    '-preset', 'medium',
                    '-crf', '18',  # Высокое качество
                    '-c:a', 'aac',  # Перекодируем аудио в AAC
                    '-b:a', '192k',
                    '-movflags', '+faststart',  # Для стриминга и мобильных устройств
                    '-pix_fmt', 'yuv420p',  # Совместимость с iPhone и другими устройствами
                    '-y',
                    str(final_path)
                ]
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=600)
                if result.returncode == 0 and final_path.exists():
                    expected_path.unlink()  # Удаляем большой файл
                    logger.info(f"Фрагмент обрезан и перекодирован: {final_path}")
                    return final_path
                else:
                    logger.error(f"Ошибка при перекодировании: {result.stderr}")
            
            # Если файл нормального размера, все равно перекодируем для совместимости
            logger.info("Перекодирую в совместимый формат для мобильных устройств...")
            final_path = DOWNLOAD_DIR / f"video_{safe_timestamp}_final.mp4"
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', str(expected_path),
                '-c:v', 'libx264',  # H.264 для совместимости
                '-preset', 'medium',
                '-crf', '18',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-movflags', '+faststart',
                '-pix_fmt', 'yuv420p',  # Обязательно для iPhone
                '-y',
                str(final_path)
            ]
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=600)
            if result.returncode == 0 and final_path.exists():
                expected_path.unlink()  # Удаляем исходный файл
                logger.info(f"Фрагмент перекодирован: {final_path}")
                return final_path
            else:
                logger.warning(f"Перекодирование не удалось, используем исходный файл: {result.stderr}")
                return expected_path
        
        # Ищем файл с любым расширением и перекодируем в совместимый формат
        for ext in ['.mp4', '.mkv', '.webm', '.m4a']:
            alt_path = output_path.with_suffix(ext)
            if alt_path.exists():
                file_size = alt_path.stat().st_size
                logger.info(f"Найден файл: {alt_path}, размер: {file_size / 1024 / 1024:.2f} MB")
                
                # Перекодируем в совместимый MP4 формат
                final_path = DOWNLOAD_DIR / f"video_{safe_timestamp}_final.mp4"
                logger.info("Перекодирую в совместимый формат для мобильных устройств...")
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-i', str(alt_path),
                    '-c:v', 'libx264',
                    '-preset', 'medium',
                    '-crf', '18',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-movflags', '+faststart',
                    '-pix_fmt', 'yuv420p',
                    '-y',
                    str(final_path)
                ]
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=600)
                if result.returncode == 0 and final_path.exists():
                    alt_path.unlink()  # Удаляем исходный файл
                    logger.info(f"Файл перекодирован: {final_path}")
                    return final_path
                else:
                    logger.warning(f"Перекодирование не удалось: {result.stderr}")
                    return alt_path
        
        # Ищем файлы, начинающиеся с нашего имени
        found_files = list(DOWNLOAD_DIR.glob(f"video_{safe_timestamp}*"))
        logger.info(f"Найдено файлов с паттерном: {len(found_files)}")
        for file in found_files:
            if file.is_file():
                file_size = file.stat().st_size
                logger.info(f"Найден файл: {file}, размер: {file_size / 1024 / 1024:.2f} MB")
                return file
        
        logger.warning(f"Файл не найден после скачивания. Искал: {output_path}")
        logger.warning(f"Содержимое директории downloads: {list(DOWNLOAD_DIR.iterdir())}")
        return None
            
    except subprocess.TimeoutExpired:
        logger.error("Таймаут при обрезке видео")
        return None
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Ошибка yt-dlp при скачивании: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при скачивании: {e}", exc_info=True)
        raise


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
        f"⏳ Скачиваю и обрабатываю фрагмент {start_time}-{end_time}...\n\n"
        f"⏱ Пожалуйста, подождите. Это может занять некоторое время."
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
            error_details = "Не удалось скачать или найти файл после загрузки."
            logger.error(f"Ошибка скачивания: URL={url}, start={start_time}, end={end_time}")
            await status_msg.edit_text(
                f"❌ Ошибка при скачивании видео.\n\n"
                f"Возможные причины:\n"
                f"• Неверный URL или видео недоступно\n"
                f"• Временной сегмент выходит за пределы видео\n"
                f"• Проблемы с доступом к YouTube\n\n"
                f"Попробуйте еще раз с другими параметрами."
            )
    
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        logger.error(f"Ошибка yt-dlp: {error_msg}")
        await status_msg.edit_text(
            f"❌ Ошибка при скачивании:\n{error_msg[:200]}\n\n"
            f"Проверьте URL и попробуйте еще раз."
        )
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ Произошла ошибка: {str(e)[:200]}\n\n"
            f"Попробуйте еще раз или обратитесь к администратору."
        )
    
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

