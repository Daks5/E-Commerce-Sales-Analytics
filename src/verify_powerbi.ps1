param(
 [Parameter(Mandatory=$true)][int]$Port,
 [string]$SdkRoot=(Join-Path $PSScriptRoot '..\.setup\as_sdk'),
 [string]$OutputPath=(Join-Path $PSScriptRoot '..\reports\powerbi_engine_validation.json')
)
# Read-only verification of a local Desktop model with Microsoft's TOM/ADOMD APIs.
$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tomRoot=Join-Path $SdkRoot 'microsoft.analysisservices\lib\net8.0'
foreach($assemblyName in @('Microsoft.AnalysisServices.Runtime.Core.dll','Microsoft.AnalysisServices.Runtime.Windows.dll','Microsoft.AnalysisServices.Core.dll','Microsoft.AnalysisServices.Tabular.dll')) {
 [void][System.Reflection.Assembly]::LoadFrom((Join-Path $tomRoot $assemblyName))
}
[void][System.Reflection.Assembly]::LoadFrom((Join-Path $SdkRoot 'microsoft.analysisservices.adomdclient\lib\net8.0\Microsoft.AnalysisServices.AdomdClient.dll'))
$server=New-Object Microsoft.AnalysisServices.Tabular.Server
$server.Connect("Data Source=localhost:$Port")
if($server.Databases.Count -ne 1){throw 'Expected one local model'}
$database=$server.Databases[0]
foreach($name in @('Sales','Date','Product','Geography','Status')){
 if($null -eq $database.Model.Tables.Find($name)){throw "Missing project table: $name"}
}
$measures=$database.Model.Tables['Sales'].Measures
$errors=@($measures | Where-Object ErrorMessage | Select-Object Name,ErrorMessage)
if($errors.Count){$errors | ConvertTo-Json;throw 'DAX engine errors found'}
$connection=New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$Port;Initial Catalog=$($database.ID)")
$connection.Open()
function Read-Dax([string]$Query){
 $command=$connection.CreateCommand();$command.CommandText=$Query
 $reader=$command.ExecuteReader();$rows=@()
 try {
  while($reader.Read()){
   $row=[ordered]@{}
   for($i=0;$i -lt $reader.FieldCount;$i++){$row[$reader.GetName($i).Trim('[',']')]=$reader.GetValue($i)}
   $rows+=[pscustomobject]$row
  }
 } finally{$reader.Close();$command.Dispose()}
 return $rows
}
$pairs=@($measures | ForEach-Object {'"'+$_.Name+'", ['+$_.Name+']'})
$overall=Read-Dax ('EVALUATE ROW('+($pairs -join ', ')+')')
$checks=[ordered]@{}
$expected=Get-Content (Join-Path $projectRoot 'reports\dax_expected.json') -Raw | ConvertFrom-Json
foreach($property in $expected.PSObject.Properties){
 $actual=[double]$overall.($property.Name);$target=[double]$property.Value
 $checks[$property.Name]=[math]::Abs($actual-$target) -le 0.000001
}
$categories=Read-Dax 'EVALUATE SUMMARIZECOLUMNS(Product[category], "Shipped Value", [Shipped Sales Value])'
$categorySql=Import-Csv (Join-Path $projectRoot 'reports\sql_results\category_performance.csv')
foreach($row in $categories){
 $target=$categorySql | Where-Object category -EQ $row.'Product[category'
 $checks['Category '+$row.'Product[category']=($null -ne $target -and [math]::Abs([double]$row.'Shipped Value'-[double]$target.shipped_value) -le 0.000001)
}
$states=Read-Dax 'EVALUATE SUMMARIZECOLUMNS(Geography[ship_state], "Shipped Value", [Shipped Sales Value])'
$stateSql=Import-Csv (Join-Path $projectRoot 'reports\sql_results\state_performance.csv')
foreach($row in $states){
 $target=$stateSql | Where-Object ship_state -EQ $row.'Geography[ship_state'
 $checks['State '+$row.'Geography[ship_state']=($null -ne $target -and [math]::Abs([double]$row.'Shipped Value'-[double]$target.shipped_value) -le 0.000001)
}
$fulfillment=Read-Dax 'EVALUATE SUMMARIZECOLUMNS(Sales[fulfillment], "Shipped Value", [Shipped Sales Value], "Cancelled Lines", [Cancelled Lines], "Line Rate", [Cancelled Line Rate])'
$fulfillmentSql=Import-Csv (Join-Path $projectRoot 'reports\sql_results\fulfillment_operations.csv')
foreach($row in $fulfillment){
 $target=$fulfillmentSql | Where-Object fulfillment -EQ $row.'Sales[fulfillment'
 $checks['Fulfillment '+$row.'Sales[fulfillment']=($null -ne $target -and [math]::Abs([double]$row.'Shipped Value'-[double]$target.shipped_value) -le 0.000001 -and [double]$row.'Cancelled Lines' -eq [double]$target.cancelled_lines)
}
$passed=-not ($checks.Values -contains $false)
$report=[ordered]@{passed=$passed;measures_evaluated=$measures.Count;engine_errors=$errors;checks=$checks;overall=$overall;categories=$categories;states=$states;fulfillment=$fulfillment}
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputPath -Encoding utf8
$connection.Close();$server.Disconnect()
Write-Output "Power BI engine checks: $($checks.Count), passed: $passed; measures evaluated: $($measures.Count)"
if(-not $passed){throw 'Power BI / SQL reconciliation failed; inspect validation report'}
