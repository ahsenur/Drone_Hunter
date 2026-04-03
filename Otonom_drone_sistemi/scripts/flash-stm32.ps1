param(
    [string]$ElfPath = "build/Debug/Otonom_drone_sistemi.elf"
)

$ErrorActionPreference = "Stop"

function Find-ProgrammerCli {
    $candidates = @(
        (Get-Command STM32_Programmer_CLI.exe -ErrorAction SilentlyContinue).Source,
        (Get-Command STM32_Programmer_CLI -ErrorAction SilentlyContinue).Source,
        (Get-ChildItem "$env:LOCALAPPDATA\stm32cube\bundles\programmer" -Recurse -Filter STM32_Programmer_CLI.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName | Select-Object -First 1),
        "C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe",
        "C:\Program Files\STMicroelectronics\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe"
    ) | Where-Object { $_ -and (Test-Path $_) }

    return $candidates | Select-Object -First 1
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$elfFullPath = Join-Path $projectRoot $ElfPath

if (-not (Test-Path $elfFullPath)) {
    throw "Firmware dosyasi bulunamadi: $elfFullPath`nOnce 'Build Debug' gorevini calistirin."
}

$programmerCli = Find-ProgrammerCli
if (-not $programmerCli) {
    throw @"
STM32_Programmer_CLI bulunamadi.

Kurulum:
1. STM32CubeProgrammer yukleyin.
2. Asagidaki klasorlerden biri olusmali:
   - C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin
   - C:\Program Files\STMicroelectronics\STM32CubeProgrammer\bin
3. ST-LINK ile karti USB'den baglayin.

Ardindan bu gorevi yeniden calistirin.
"@
}

Write-Host "Using programmer:" $programmerCli
Write-Host "Flashing firmware:" $elfFullPath

& $programmerCli -c port=SWD -w $elfFullPath -v -rst

if ($LASTEXITCODE -ne 0) {
    throw "Flash islemi basarisiz oldu. ST-LINK baglantisini, hedef karti ve suruculeri kontrol edin."
}

Write-Host "Flash tamamlandi."
