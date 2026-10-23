$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::NotSet, [System.Speech.Synthesis.VoiceAge]::NotSet, 0, [Globalization.CultureInfo]::GetCultureInfo('zh-CN'))
$scenes = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'scenes.json') -Raw -Encoding UTF8 | ConvertFrom-Json
try {
    for ($i = 0; $i -lt $scenes.Count; $i++) {
        $speaker.SetOutputToWaveFile((Join-Path $PSScriptRoot "voice-$i.wav"))
        $speaker.Speak($scenes[$i].voice)
    }
} finally { $speaker.Dispose() }
