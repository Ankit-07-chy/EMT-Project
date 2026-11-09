# Export the deck to PDF (and optionally PNG slide images) with the installed PowerPoint.
#   powershell -ExecutionPolicy Bypass -File presentation\export_pdf.ps1 [-Images]
param([switch]$Images, [string]$Deck = "$PSScriptRoot\TDR_Cable_Fault_Detection.pptx")
$ErrorActionPreference = "Stop"
$deck = (Resolve-Path $Deck).Path
$pdf = [System.IO.Path]::ChangeExtension($deck, ".pdf")
$pp = New-Object -ComObject PowerPoint.Application
try {
    # Open(FileName, ReadOnly, Untitled, WithWindow)
    $p = $pp.Presentations.Open($deck, $true, $false, $false)
    $p.SaveAs($pdf, 32)          # 32 = ppSaveAsPDF
    Write-Output "PDF: $pdf"
    if ($Images) {
        $dir = Join-Path $PSScriptRoot "render"
        if (Test-Path $dir) { Remove-Item -Recurse -Force $dir -Confirm:$false }
        New-Item -ItemType Directory -Force $dir | Out-Null
        $p.Export($dir, "PNG", 1600, 900)
        Write-Output "PNG slides: $dir"
    }
    $p.Close()
} finally {
    $pp.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($pp) | Out-Null
}
