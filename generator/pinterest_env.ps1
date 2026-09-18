# 촬영/리허설용 Pinterest env 입력. 반드시 같은 창에서 dot-source로 실행:
#     . .\generator\pinterest_env.ps1
# 값은 프롬프트에 붙여넣습니다(우클릭 또는 Ctrl+V). 클립보드를 직접 읽지 않으므로
# 이 명령을 채팅/문서에서 복사한 뒤에 값을 복사해도 됩니다. 붙여넣은 값이 화면에
# 보이므로 잘못 들어간 것을 바로 알 수 있고, 확인이 끝나면 화면을 지웁니다.

if ($MyInvocation.InvocationName -ne '.') {
    Write-Host "env가 이 창에 남으려면 dot-source로 실행해야 합니다:   . .\generator\pinterest_env.ps1" -ForegroundColor Red
    return
}

function Read-Value([string]$Label, [string]$Default = "") {
    $prompt = if ($Default) { "$Label (Enter = $Default)" } else { $Label }
    $v = (Read-Host $prompt).Trim()
    if (-not $v) { $v = $Default }
    return $v
}

$env:PINTEREST_APP_ID           = Read-Value "App ID" "1594725"
$env:PINTEREST_APP_SECRET       = Read-Value "App secret (포털에서 복사 후 붙여넣기)"
$env:PINTEREST_TOKEN_PASSPHRASE = Read-Value "토큰 passphrase"
$env:PINTEREST_SANDBOX_TOKEN    = Read-Value "Sandbox 토큰 (포털 Generate Access Tokens → Sandbox → 복사; 없으면 Enter)"

function Show-Check([string]$Name, [string]$Value, [string]$Prefix = "", [switch]$ShowHead) {
    if (-not $Value) {
        Write-Host ("  {0,-26} (비어 있음)" -f $Name) -ForegroundColor Yellow
        return
    }
    $head = if ($ShowHead) { $Value.Substring(0, [Math]::Min(5, $Value.Length)) + "... " } else { "" }
    $ok = (-not $Prefix) -or $Value.StartsWith($Prefix)
    $note = if ($ok) { "" } else { "   <- '$Prefix'로 시작해야 합니다. 클립보드에 다른 것이 있었습니다" }
    $color = if ($ok) { "Green" } else { "Red" }
    Write-Host ("  {0,-26} {1}{2}자{3}" -f $Name, $head, $Value.Length, $note) -ForegroundColor $color
}

Write-Host ""
Write-Host "입력 확인 (길이만 표시; sandbox 토큰은 접두어도 표시):"
Show-Check "PINTEREST_APP_ID"           $env:PINTEREST_APP_ID -ShowHead
Show-Check "PINTEREST_APP_SECRET"       $env:PINTEREST_APP_SECRET
Show-Check "PINTEREST_TOKEN_PASSPHRASE" $env:PINTEREST_TOKEN_PASSPHRASE
Show-Check "PINTEREST_SANDBOX_TOKEN"    $env:PINTEREST_SANDBOX_TOKEN "pina_" -ShowHead
Write-Host "  (참고: OAuth code는 40자, 채팅에서 복사한 명령줄은 보통 50~90자입니다)"
Read-Host "이상 없으면 Enter (화면을 지웁니다). 틀렸으면 Ctrl+C 후 다시 실행" | Out-Null
Clear-Host
Write-Host "env 준비 완료. 리허설:  python generator/pinterest_publish.py --whoami" -ForegroundColor Green
