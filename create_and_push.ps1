# Скрипт для создания репозитория и загрузки кода на GitHub
# Использование: .\create_and_push.ps1 -GitHubUsername "ваш_username" [-GitHubToken "ваш_токен"]

param(
    [Parameter(Mandatory=$true)]
    [string]$GitHubUsername,
    
    [string]$GitHubToken = "",
    [string]$RepoName = "trubabot"
)

Write-Host "=== Создание репозитория на GitHub ===" -ForegroundColor Green

# Если токен не предоставлен, используем альтернативный метод
if ([string]::IsNullOrWhiteSpace($GitHubToken)) {
    Write-Host "`nТокен не предоставлен. Используем метод с ручным созданием репозитория." -ForegroundColor Yellow
    Write-Host "`nИнструкция:" -ForegroundColor Cyan
    Write-Host "1. Откройте https://github.com/new" -ForegroundColor White
    Write-Host "2. Название репозитория: $RepoName" -ForegroundColor White
    Write-Host "3. Выберите Public или Private" -ForegroundColor White
    Write-Host "4. НЕ добавляйте README, .gitignore или лицензию" -ForegroundColor White
    Write-Host "5. Нажмите 'Create repository'" -ForegroundColor White
    Write-Host "`nПосле создания репозитория нажмите Enter..." -ForegroundColor Yellow
    Read-Host
    
    if ([string]::IsNullOrWhiteSpace($GitHubUsername)) {
        $GitHubUsername = Read-Host "Введите ваш GitHub username"
    }
    
    $repoUrl = "https://github.com/$GitHubUsername/$RepoName.git"
} else {
    # Используем токен для создания репозитория через API
    if ([string]::IsNullOrWhiteSpace($GitHubUsername)) {
        $GitHubUsername = Read-Host "Введите ваш GitHub username"
    }
    
    Write-Host "Создаю репозиторий через GitHub API..." -ForegroundColor Cyan
    
    $headers = @{
        "Authorization" = "token $GitHubToken"
        "Accept" = "application/vnd.github.v3+json"
    }
    
    $body = @{
        name = $RepoName
        description = "Telegram bot for downloading YouTube video fragments"
        private = $false
    } | ConvertTo-Json
    
    try {
        $response = Invoke-RestMethod -Uri "https://api.github.com/user/repos" -Method Post -Headers $headers -Body $body
        $repoUrl = $response.clone_url
        Write-Host "✅ Репозиторий создан: $repoUrl" -ForegroundColor Green
    } catch {
        Write-Host "❌ Ошибка при создании репозитория: $_" -ForegroundColor Red
        exit 1
    }
}

# Добавляем remote
Write-Host "`nДобавляю remote origin..." -ForegroundColor Cyan
git remote remove origin 2>$null

if (-not [string]::IsNullOrWhiteSpace($GitHubToken)) {
    # Используем токен в URL для авторизации
    $repoUrlWithToken = $repoUrl -replace "https://", "https://$GitHubToken@"
    git remote add origin $repoUrlWithToken
} else {
    git remote add origin $repoUrl
}

# Получаем текущую ветку
$currentBranch = git branch --show-current
if ([string]::IsNullOrWhiteSpace($currentBranch)) {
    $currentBranch = "main"
}

Write-Host "Текущая ветка: $currentBranch" -ForegroundColor Cyan

# Пушим код
Write-Host "`nЗагружаю код на GitHub..." -ForegroundColor Cyan
git push -u origin $currentBranch

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Код успешно загружен на GitHub!" -ForegroundColor Green
    Write-Host "Репозиторий: $repoUrl" -ForegroundColor Green
} else {
    Write-Host "`n❌ Ошибка при загрузке кода." -ForegroundColor Red
    Write-Host "Попробуйте запушить вручную:" -ForegroundColor Yellow
    Write-Host "git push -u origin $currentBranch" -ForegroundColor Gray
    exit 1
}

