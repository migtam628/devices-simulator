#Requires -Version 5.1
# Experimental, requires Windows 11 with Add-Printer -IppURL support.
param([int]$Port = 8631)
$ErrorActionPreference = 'Stop'
$endpoint = "http://127.0.0.1:$Port/healthz"
try { $null = Invoke-RestMethod -Uri $endpoint -TimeoutSec 3 }
catch { throw 'Start lulwa-ipp on this PC first: py -3 -m lulwa_virtual_printer.ipp_server' }
$ippUrls = @(
  "http://127.0.0.1:$Port/ipp/brother",
  "http://127.0.0.1:$Port/ipp/zebra"
)
$command = Get-Command Add-Printer -ErrorAction Stop
if (-not $command.Parameters.ContainsKey('IppURL')) { throw 'Add-Printer -IppURL not available on this Windows build. Use Settings > Printers & scanners > Add manually > IPP Device.' }
foreach ($uri in $ippUrls) {
  Write-Host "Registering IPP device: $uri"
  try { Add-Printer -IppURL $uri -ErrorAction Stop }
  catch { Write-Warning "Automatic registration failed: $_. Open Settings > Bluetooth & devices > Printers & scanners > Add device > Add manually > IPP device. Use $uri" }
}
Get-Printer | Where-Object { $_.Name -like '*Lulwa*' -or $_.PortName -match '8631' } | Format-Table Name,DriverName,PortName
Write-Warning 'Experimental installation: confirm both printers are listed and print a test PDF. The service must remain running.'
