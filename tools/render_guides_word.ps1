param([string]$Only = '')
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$qaDir = Join-Path $projectDir 'artifacts\word-qa'
New-Item -ItemType Directory -Force -Path $qaDir | Out-Null
# Отдельный COM-экземпляр Word; открываются только созданные нами документы.
$wordApp = New-Object -ComObject Word.Application
$wordApp.Visible = $false
$wordApp.DisplayAlerts = 0
try {
    $documents = @(
        @('Руководство_по_защите_byVanoGame.docx', 'handbook'),
        @('Короткая_речь_и_шпаргалка_byVanoGame.docx', 'speech')
    )
    foreach ($entry in $documents) {
        if ($Only -and $Only -ne $entry[1]) { continue }
        $source = Join-Path $projectDir ('submission\' + $entry[0])
        $pdfPath = Join-Path $qaDir ($entry[1] + '.pdf')
        $openedDoc = $wordApp.Documents.Open($source, $false, $true, $false)
        try {
            $openedDoc.Repaginate()
            $pages = $openedDoc.ComputeStatistics(2)
            $openedDoc.ExportAsFixedFormat($pdfPath, 17)
            Write-Output ($entry[1] + ': ' + $pages + ' pages -> ' + $pdfPath)
        }
        finally { $openedDoc.Close(0) }
    }
}
finally {
    $wordApp.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp) | Out-Null
}
