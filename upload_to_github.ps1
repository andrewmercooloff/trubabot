# Скрипт для загрузки кода на GitHub
# Запустите этот скрипт после создания репозитория на GitHub

Write-Host "=== Загрузка проекта на GitHub ===" -ForegroundColor Green

# Проверяем, что мы в правильной директории
if (-not (Test-Path ".git")) {
    Write-Host "Ошибка: .git директория не найдена. Убедитесь, что вы в корне проекта." -ForegroundColor Red
    exit 1
}

# Запрашиваем URL репозитория
Write-Host "`nВведите URL вашего GitHub репозитория:" -ForegroundColor Yellow
Write-Host "Пример: https://github.com/username/trubabot.git" -ForegroundColor Gray
$repoUrl = Read-Host "URL репозитория"

if ([string]::IsNullOrWhiteSpace($repoUrl)) {
    Write-Host "Ошибка: URL не может быть пустым." -ForegroundColor Red
    exit 1
}

# Добавляем remote
Write-Host "`nДобавляю remote origin..." -ForegroundColor Cyan
git remote remove origin 2>$null
git remote add origin $repoUrl

if ($LASTEXITCODE -ne 0) {
    Write-Host "Ошибка при добавлении remote." -ForegroundColor Red
    exit 1
}

# Проверяем текущую ветку
$currentBranch = git branch --show-current
Write-Host "Текущая ветка: $currentBranch" -ForegroundColor Cyan

# Пушим код
Write-Host "`nЗагружаю код на GitHub..." -ForegroundColor Cyan
git push -u origin $currentBranch

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Код успешно загружен на GitHub!" -ForegroundColor Green
    Write-Host "Репозиторий: $repoUrl" -ForegroundColor Green
} else {
    Write-Host "`n❌ Ошибка при загрузке кода." -ForegroundColor Red
    Write-Host "Возможные причины:" -ForegroundColor Yellow
    Write-Host "1. Репозиторий не существует или URL неверный" -ForegroundColor Gray
    Write-Host "2. Нет прав доступа к репозиторию" -ForegroundColor Gray
    Write-Host "3. Требуется авторизация (GitHub откроет браузер для входа)" -ForegroundColor Gray
    exit 1
}

