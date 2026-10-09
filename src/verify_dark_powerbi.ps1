param([Parameter(Mandatory=$true)][int]$Port)
$ErrorActionPreference='Stop'
$darkReportPath=Join-Path $PSScriptRoot '..\reports\powerbi_dark_engine_validation.json'
. (Join-Path $PSScriptRoot 'verify_powerbi.ps1') -Port $Port -OutputPath $darkReportPath
$darkCatalog=$database.ID
$connection=New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$Port;Initial Catalog=$darkCatalog")
$connection.Open()
$darkReport=Get-Content -LiteralPath $darkReportPath -Raw | ConvertFrom-Json -AsHashtable
$expectedDark=Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\reports\powerbi_dark_expected.json') -Raw | ConvertFrom-Json -AsHashtable
foreach($name in $expectedDark.Keys){
 $actual=$darkReport.overall[$name];$target=$expectedDark[$name]
 $darkReport.checks['Decision measure '+$name]=if($target -is [string]){$actual -ceq $target}else{[math]::Abs([double]$actual-[double]$target) -le 0.000001}
}
$changes=Read-Dax 'EVALUATE SELECTCOLUMNS(SUMMARIZECOLUMNS(Product[category], "MayAmount", [May 1-29 Value], "JuneAmount", [June 1-29 Value], "Difference", [Comparable Value Change], "NegativeAmount", [Category decline (lakh)], "PositiveAmount", [Category growth (lakh)]), "Category", Product[category], "May", [MayAmount], "June", [JuneAmount], "Change", [Difference], "Negative", [NegativeAmount], "Positive", [PositiveAmount])'
$sqlChanges=Import-Csv (Join-Path $PSScriptRoot '..\reports\sql_results\category_decline_contribution.csv')
foreach($row in $changes){
 $expectedRow=$sqlChanges | Where-Object category -CEQ $row.Category
 $darkReport.checks['Category comparison '+$row.Category]=($null -ne $expectedRow -and [math]::Abs([double]$row.May-[double]$expectedRow.may_value) -le 0.000001 -and [math]::Abs([double]$row.June-[double]$expectedRow.june_value) -le 0.000001 -and [math]::Abs([double]$row.Change-[double]$expectedRow.value_change) -le 0.000001)
 $negativeBlank=($null -eq $row.Negative -or [Convert]::IsDBNull($row.Negative))
 $positiveBlank=($null -eq $row.Positive -or [Convert]::IsDBNull($row.Positive))
 $negativeAmount=if($negativeBlank){0}else{[double]$row.Negative}
 $positiveAmount=if($positiveBlank){0}else{[double]$row.Positive}
 $darkReport.checks['Diverging chart '+$row.Category]=([math]::Abs($negativeAmount-[math]::Min([double]$expectedRow.value_change,0)/100000) -le 0.000001 -and [math]::Abs($positiveAmount-[math]::Max([double]$expectedRow.value_change,0)/100000) -le 0.000001 -and $negativeBlank -eq ([double]$expectedRow.value_change -ge 0) -and $positiveBlank -eq ([double]$expectedRow.value_change -le 0))
}
$daily=Read-Dax 'EVALUATE SELECTCOLUMNS(SUMMARIZECOLUMNS(\u0027Date\u0027[day_of_month], "MayAmount", [May daily value], "JuneAmount", [June daily value]), "Day", \u0027Date\u0027[day_of_month], "May", [MayAmount], "June", [JuneAmount])'.Replace('\u0027',"'")
$expectedDaily=Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\reports\powerbi_daily_expected.json') -Raw | ConvertFrom-Json
foreach($row in $daily){
 $expectedRow=$expectedDaily | Where-Object day -EQ $row.Day
 $darkReport.checks['Aligned daily values '+$row.Day]=($null -ne $expectedRow -and [math]::Abs([double]$row.May-[double]$expectedRow.may) -le 0.000001 -and [math]::Abs([double]$row.June-[double]$expectedRow.june) -le 0.000001)
}
$darkReport.checks['29 comparable days']=$daily.Count -eq 29
$darkReport.comparison_categories=$changes
$darkReport.comparison_daily=$daily
$darkReport.passed=-not ($darkReport.checks.Values -contains $false)
$darkReport | ConvertTo-Json -Depth 14 | Set-Content -LiteralPath $darkReportPath -Encoding utf8
$connection.Close()
Write-Output "Dark dashboard: $($darkReport.measures_evaluated) compiled measures; $($darkReport.checks.Count) checks; passed: $($darkReport.passed)"
if(-not $darkReport.passed){throw 'Dark dashboard reconciliation failed'}
