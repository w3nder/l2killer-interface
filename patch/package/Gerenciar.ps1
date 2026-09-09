param([ValidateSet('Install', 'Restore')][string]$Action = 'Install')
$ErrorActionPreference = 'Stop'
$package = Split-Path -Parent $MyInvocation.MyCommand.Path
$system = Split-Path -Parent $package
$target = Join-Path $system 'NWindow.dll'
$backup = Join-Path $system 'NWindow.dll.c4bars-original'
$helper = Join-Path $system 'C4Bars.dll'
$originalHash = '07af3e21bac5ba335d6d08317361e012c15a514b8d846a0a57508da46d282d0e'

function FileHash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    } finally { $stream.Dispose(); $sha.Dispose() }
}

try {
    if (!(Test-Path -LiteralPath (Join-Path $system 'L2.exe')) -or !(Test-Path -LiteralPath $target)) {
        throw 'Coloque a pasta C4Bars-teste-01 DENTRO da pasta system do jogo e execute novamente.'
    }
    if (Get-Process -Name 'L2' -ErrorAction SilentlyContinue) {
        throw 'Feche o Lineage 2 antes de instalar ou restaurar.'
    }
    $patch = Join-Path $package 'bin\NWindow.dll'
    $dll = Join-Path $package 'bin\C4Bars.dll'
    # Expected build hashes are embedded by build_patch.py, not trusted from the target.
    $patchHash = '__PATCH_SHA256__'
    $dllHash = '__DLL_SHA256__'
    $currentHash = FileHash $target

    if ($Action -eq 'Restore') {
        if ($currentHash -eq $originalHash) {
            Write-Host 'A NWindow.dll original ja esta em uso.'
            exit 0
        }
        if ($currentHash -ne $patchHash) {
            throw 'A NWindow.dll atual foi alterada por outro patch. Restauracao automatica cancelada.'
        }
        if (!(Test-Path -LiteralPath $backup) -or (FileHash $backup) -ne $originalHash) {
            throw 'Backup original ausente ou diferente. Nenhum arquivo foi alterado.'
        }
        Copy-Item -LiteralPath $backup -Destination $target -Force
        if ((FileHash $target) -ne $originalHash) { throw 'Falha ao verificar a restauracao.' }
        Write-Host 'Original restaurada. C4Bars.dll, configuracao e log podem permanecer; nao serao carregados.'
        exit 0
    }

    if ((FileHash $patch) -ne $patchHash -or (FileHash $dll) -ne $dllHash) {
        throw 'Pacote incompleto ou alterado. Extraia novamente o ZIP original.'
    }
    if ($currentHash -ne $originalHash -and $currentHash -ne $patchHash) {
        throw 'Esta system tem uma NWindow.dll diferente da analisada. Instalacao cancelada, sem substituir arquivos.'
    }
    if (Test-Path -LiteralPath $backup) {
        if ((FileHash $backup) -ne $originalHash) { throw 'Ja existe um backup diferente. Nada foi substituido.' }
    } elseif ($currentHash -eq $originalHash) {
        Copy-Item -LiteralPath $target -Destination $backup
        if ((FileHash $backup) -ne $originalHash) { throw 'Falha ao verificar o backup.' }
    } else {
        throw 'O patch esta instalado mas o backup original esta ausente.'
    }
    if ((Test-Path -LiteralPath $helper) -and (FileHash $helper) -ne $dllHash) {
        throw 'Ja existe outra C4Bars.dll. Nada foi substituido.'
    }
    $config = Join-Path $system 'C4Bars.ini'
    Copy-Item -LiteralPath $dll -Destination $helper -Force
    if (!(Test-Path -LiteralPath $config)) {
        Copy-Item -LiteralPath (Join-Path $package 'C4Bars.ini') -Destination $config
    }
    try {
        Copy-Item -LiteralPath $patch -Destination $target -Force
        if ((FileHash $target) -ne $patchHash) { throw 'Falha ao verificar DLL instalada.' }
    } catch {
        Copy-Item -LiteralPath $backup -Destination $target -Force
        throw
    }
    Write-Host 'Teste 01 instalado. Abra o jogo pelo seu atalho normal.'
    Write-Host 'Se precisar desfazer, feche o jogo e execute Restaurar.bat.'
} catch {
    Write-Host ('ERRO: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
