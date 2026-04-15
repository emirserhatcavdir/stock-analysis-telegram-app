Write-Host "Starting FastAPI Backend on port 8000..." -ForegroundColor Green
$BackendJob = Start-Job -ScriptBlock {
    Set-Location "C:\Users\SERO\Desktop\python for finance.py"
    python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
}

Write-Host "Starting Vite Frontend on port 5173..." -ForegroundColor Green
$FrontendJob = Start-Job -ScriptBlock {
    Set-Location "C:\Users\SERO\Desktop\python for finance.py\apps\miniapp"
    npm run dev
}

Write-Host ""
Write-Host "Serverlar arka planda başlatıldı!" -ForegroundColor Yellow
Write-Host "1. FastAPI Backend -> http://127.0.0.1:8000"
Write-Host "2. Vite Frontend   -> http://localhost:5173"
Write-Host ""
Write-Host "!!! DİKKAT !!!" -ForegroundColor Red
Write-Host "Telegram Mini App'i dışa açmak için geçerli bir Ngrok Authtoken girmelisiniz."
Write-Host "Lütfen şu adımları izleyin:"
Write-Host "1. https://dashboard.ngrok.com/get-started/your-authtoken adresinden token'ınızı alın."
Write-Host "2. Terminalde şunu çalıştırın: npx ngrok config add-authtoken BURAYA_TOKEN_YAPIŞTIR"
Write-Host "3. Son olarak tüneli başlatmak için: npx ngrok http 5173"
Write-Host ""
Write-Host "Çıkış yapmak veya sunucuları durdurmak isterseniz terminali kapatabilir veya 'Get-Job | Remove-Job -Force' yapabilirsiniz."

Receive-Job -Job $BackendJob
Receive-Job -Job $FrontendJob
