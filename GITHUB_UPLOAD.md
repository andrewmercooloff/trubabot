# Инструкция по загрузке на GitHub

## Вариант 1: Через веб-интерфейс GitHub (самый простой)

1. Откройте https://github.com и войдите в аккаунт
2. Нажмите кнопку **"+"** в правом верхнем углу → **"New repository"**
3. Заполните:
   - **Repository name:** `trubabot` (или любое другое имя)
   - **Description:** "Telegram bot for downloading YouTube video fragments"
   - Выберите **Public** или **Private**
   - **НЕ** ставьте галочки на "Add a README file", "Add .gitignore", "Choose a license" (все уже есть)
4. Нажмите **"Create repository"**
5. GitHub покажет инструкции. Выполните команды в терминале:

```bash
cd c:\trubabot
git remote add origin https://github.com/ВАШ_USERNAME/trubabot.git
git push -u origin main
```

Замените `ВАШ_USERNAME` на ваш username на GitHub.

## Вариант 2: Через командную строку (если уже есть репозиторий)

Если вы уже создали репозиторий на GitHub, выполните:

```bash
cd c:\trubabot
git remote add origin https://github.com/ВАШ_USERNAME/trubabot.git
git push -u origin main
```

## Вариант 3: Через SSH (если настроен SSH ключ)

```bash
cd c:\trubabot
git remote add origin git@github.com:ВАШ_USERNAME/trubabot.git
git push -u origin main
```

## После загрузки

После успешного push ваш код будет на GitHub и готов к деплою на Railway!

