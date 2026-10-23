param(
    [Parameter(Mandatory=$true)][string]$JdkHome,
    [Parameter(Mandatory=$true)][string]$BuildTools,
    [Parameter(Mandatory=$true)][string]$AndroidJar,
    [string]$KeyStore,
    [string]$PasswordFile,
    [string]$KeyAlias = 'personal',
    [string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $PSScriptRoot 'output' }
$output = [IO.Path]::GetFullPath($OutputDirectory)
$app = Join-Path $PSScriptRoot 'app'
foreach ($path in @($JdkHome, $BuildTools, $AndroidJar)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing build dependency: $path" }
}
New-Item -ItemType Directory -Path $output,(Join-Path $output 'classes'),(Join-Path $output 'dex') -Force | Out-Null
function Invoke-Checked([string]$program, [string[]]$arguments) {
    & $program @arguments
    if ($LASTEXITCODE -ne 0) { throw "Build step failed: $program ($LASTEXITCODE)" }
}
Invoke-Checked (Join-Path $JdkHome 'bin/javac.exe') @('-encoding','UTF-8','-source','8','-target','8','-classpath',$AndroidJar,'-d',(Join-Path $output 'classes'),(Join-Path $app 'src/com/noticehub/personal/MainActivity.java'))
$classFiles = @(Get-ChildItem -LiteralPath (Join-Path $output 'classes') -Filter '*.class' -Recurse | Select-Object -ExpandProperty FullName)
Invoke-Checked (Join-Path $JdkHome 'bin/java.exe') (@('-cp',(Join-Path $BuildTools 'lib/d8.jar'),'com.android.tools.r8.D8','--lib',$AndroidJar,'--min-api','23','--output',(Join-Path $output 'dex')) + $classFiles)
Invoke-Checked (Join-Path $BuildTools 'aapt2.exe') @('compile','--dir',(Join-Path $app 'res'),'-o',(Join-Path $output 'resources.zip'))
Invoke-Checked (Join-Path $BuildTools 'aapt2.exe') @('link','-o',(Join-Path $output 'unsigned.apk'),'-I',$AndroidJar,'--manifest',(Join-Path $app 'AndroidManifest.xml'),'-R',(Join-Path $output 'resources.zip'),'--min-sdk-version','23','--target-sdk-version','35','--version-code','10003','--version-name','1.0.2-personal')
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::Open((Join-Path $output 'unsigned.apk'), [IO.Compression.ZipArchiveMode]::Update)
try {
    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, (Join-Path $output 'dex/classes.dex'), 'classes.dex') | Out-Null
} finally { $zip.Dispose() }
Invoke-Checked (Join-Path $BuildTools 'zipalign.exe') @('-f','-p','4',(Join-Path $output 'unsigned.apk'),(Join-Path $output 'aligned.apk'))
if (-not $KeyStore) {
    $KeyStore = Join-Path $output 'local-signing.p12'
    $PasswordFile = Join-Path $output 'signing-password.txt'
    if (-not (Test-Path -LiteralPath $KeyStore)) {
        $random = New-Object byte[] 32
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($random) } finally { $rng.Dispose() }
        [IO.File]::WriteAllText($PasswordFile, [Convert]::ToBase64String($random), [Text.UTF8Encoding]::new($false))
        Invoke-Checked (Join-Path $JdkHome 'bin/keytool.exe') @('-genkeypair','-keystore',$KeyStore,'-storetype','PKCS12','-storepass:file',$PasswordFile,'-alias',$KeyAlias,'-keyalg','RSA','-keysize','2048','-validity','3650','-dname','CN=NoticeHub Personal Build','-noprompt')
    }
}
if (-not $PasswordFile -or -not (Test-Path -LiteralPath $PasswordFile)) { throw 'Provide the signing PasswordFile' }
$apk = Join-Path $output 'notice-hub-personal.apk'
Invoke-Checked (Join-Path $JdkHome 'bin/java.exe') @('-jar',(Join-Path $BuildTools 'lib/apksigner.jar'),'sign','--ks',$KeyStore,'--ks-key-alias',$KeyAlias,'--ks-pass',('file:'+$PasswordFile),'--out',$apk,(Join-Path $output 'aligned.apk'))
Invoke-Checked (Join-Path $JdkHome 'bin/java.exe') @('-jar',(Join-Path $BuildTools 'lib/apksigner.jar'),'verify','--verbose',$apk)
Invoke-Checked (Join-Path $BuildTools 'aapt2.exe') @('dump','badging',$apk)
Write-Output "Built $apk"
