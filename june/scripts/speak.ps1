$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Speech
$synth = New-Object -ComObject SAPI.SpVoice
if ($env:JUNE_SPEECH_OUTPUT) {
    $found = $false
    foreach ($device in $synth.GetAudioOutputs()) {
        if ($device.GetDescription() -eq $env:JUNE_SPEECH_OUTPUT) { $synth.AudioOutput = $device; $found = $true; break }
    }
    if (-not $found) { throw 'Selected speech output device is unavailable' }
}
if ($env:JUNE_SPEECH_VOICE) {
    $found = $false
    foreach ($voice in $synth.GetVoices()) {
        if ($voice.GetDescription() -eq $env:JUNE_SPEECH_VOICE) { $synth.Voice = $voice; $found = $true; break }
    }
    if (-not $found) { throw 'Selected speech voice is unavailable' }
}
[Console]::Out.WriteLine('ready')
[Console]::Out.Flush()
Add-Type 'public static class JuneInput { public static System.Threading.Tasks.Task<string> Next() { return System.Threading.Tasks.Task.Run<string>(() => System.Console.ReadLine()); } }'
$reading = [JuneInput]::Next()
$wasSpeaking = $false
while ($true) {
    if ($reading.IsCompleted) {
        $line = $reading.Result
        if ($null -eq $line) { break }
        $message = $line | ConvertFrom-Json
        if ($message.command -eq 'speak') { [void]$synth.Speak([string]$message.text, 3) }
        if ($message.command -eq 'stop') { [void]$synth.Speak('', 3) }
        $reading = [JuneInput]::Next()
    }
    $speaking = ($synth.Status.RunningState -eq 2)
    if ($speaking -ne $wasSpeaking) {
        [Console]::Out.WriteLine((@{speaking=$speaking} | ConvertTo-Json -Compress))
        [Console]::Out.Flush()
        $wasSpeaking = $speaking
    }
    Start-Sleep -Milliseconds 40
}
[void]$synth.Speak('', 3)
