# Быстрая загрузка на GitHub

## Шаг 1: Создайте репозиторий на GitHub

Я открыл страницу создания репозитория в браузере. Если не открылась, перейдите: https://github.com/new

Заполните:
- **Repository name:** `trubabot`
- **Description:** "Telegram bot for downloading YouTube video fragments"  
- Выберите **Public** или **Private**
- **НЕ** ставьте галочки на README, .gitignore, license
- Нажмите **"Create repository"**

## Шаг 2: После создания репозитория

Выполните в терминале (замените YOUR_USERNAME на ваш GitHub username):

```powershell
cd c:\trubabot
.\create_and_push.ps1 -GitHubUsername "YOUR_USERNAME"
```

Или вручную:

```powershell
cd c:\trubabot
git remote add origin https://github.com/YOUR_USERNAME/trubabot.git
git push -u origin main
```

При первом push GitHub запросит логин и пароль (или токен) - введите их.

## Альтернатива: Использовать Personal Access Token (безопаснее)

1. Создайте токен: https://github.com/settings/tokens
2. Выберите scope: `repo`
3. Скопируйте токен
4. Используйте токен вместо пароля при push

