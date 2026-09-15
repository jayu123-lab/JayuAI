# Jayu - Setup de Ollama (Windows)
# Descarga los modelos que necesita Jayu. Idempotente y seguro.
$ErrorActionPreference = "Stop"

# 1) Verificar que Ollama esté instalado
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host "[1/4] ERROR: Ollama no está instalado." -ForegroundColor Red
    Write-Host "       Descárgalo desde https://ollama.com/download/windows" -ForegroundColor Yellow
    Write-Host "       e instálalo. Luego vuelve a ejecutar este script." -ForegroundColor Yellow
    exit 1
}

# 2) Verificar que el servidor responda en 127.0.0.1:11434
Write-Host "[2/4] Verificando que Ollama responda en 127.0.0.1:11434 ..."
$tcp = Test-NetConnection -ComputerName 127.0.0.1 -Port 11434 -WarningAction SilentlyContinue
if (-not $tcp.TcpTestSucceeded) {
    Write-Host "       El servidor no responde. Asegúrate de que la app 'Ollama'" -ForegroundColor Yellow
    Write-Host "       esté corriendo (icono en la bandeja del sistema)." -ForegroundColor Yellow
    exit 1
}
Write-Host "       OK: Ollama corriendo en 127.0.0.1:11434" -ForegroundColor Green

# 3) Descargar modelos
Write-Host "[3/4] Descargando modelos (puede tardar varios GB)..."
Write-Host "   - Principal: qwen2.5-coder:14b-instruct-q4_K_M"
ollama pull qwen2.5-coder:14b-instruct-q4_K_M
Write-Host "   - Rapido: qwen2.5:7b-instruct-q4_K_M"
ollama pull qwen2.5:7b-instruct-q4_K_M
Write-Host "   - Embeddings: nomic-embed-text"
ollama pull nomic-embed-text

# 4) Resumen
Write-Host "[4/4] Modelos disponibles:" -ForegroundColor Green
ollama list

Write-Host ""
Write-Host "Importante: Ollama debe escuchar SOLO en 127.0.0.1." -ForegroundColor Cyan
Write-Host "Si alguna vez lo cambiaste, restáuralo con:" -ForegroundColor Cyan
Write-Host '   setx OLLAMA_HOST "127.0.0.1:11434"' -ForegroundColor Cyan
Write-Host "y reinicia el servicio de Ollama." -ForegroundColor Cyan