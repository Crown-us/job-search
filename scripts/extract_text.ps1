param(
    [Parameter(Mandatory = $true)][string[]]$Files,
    [Parameter(Mandatory = $true)][string]$OutDir
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force $OutDir | Out-Null

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$word.AutomationSecurity = 3

try {
    foreach ($file in $Files) {
        $base = [IO.Path]::GetFileNameWithoutExtension($file)
        $out = Join-Path $OutDir ($base + '.txt')
        try {
            $doc = $word.Documents.Open($file, $false, $true)
            $doc.SaveAs2($out, 2)          # wdFormatText
            $pages = $doc.ComputeStatistics(2)  # wdStatisticPages
            $words = $doc.ComputeStatistics(0)  # wdStatisticWords
            $doc.Close($false)
            $text = [IO.File]::ReadAllText($out, [Text.Encoding]::Default)
            [IO.File]::WriteAllText($out, $text, [Text.UTF8Encoding]::new($false))
            "OK   $base  pages=$pages words=$words chars=$($text.Length)"
        }
        catch {
            "FAIL $base  $($_.Exception.Message)"
        }
    }
}
finally {
    $word.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word)
}
