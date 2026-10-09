$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
    Add-Type -AssemblyName System.Speech
    $recognizer = [System.Speech.Recognition.SpeechRecognitionEngine]::new()
    $recognizer.LoadGrammar([System.Speech.Recognition.DictationGrammar]::new())
    if ($env:JUNE_INPUT_STREAM -eq '1') {
        $format = [System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
        $recognizer.SetInputToAudioStream([Console]::OpenStandardInput(), $format)
    } else {
        $recognizer.SetInputToDefaultAudioDevice()
    }
    $queue = [System.Collections.Concurrent.ConcurrentQueue[object]]::new()
    $heard = Register-ObjectEvent -InputObject $recognizer -EventName SpeechRecognized -MessageData $queue -Action {
        $Event.MessageData.Enqueue(@{text=$Event.SourceEventArgs.Result.Text;confidence=$Event.SourceEventArgs.Result.Confidence})
    }
    $detected = Register-ObjectEvent -InputObject $recognizer -EventName SpeechDetected -MessageData $queue -Action {
        $Event.MessageData.Enqueue(@{speech_detected=$true})
    }
    $meter = Register-ObjectEvent -InputObject $recognizer -EventName AudioLevelUpdated -MessageData $queue -Action {
        $Event.MessageData.Enqueue(@{audio_level=$Event.SourceEventArgs.AudioLevel})
    }
    $recognizer.RecognizeAsync([System.Speech.Recognition.RecognizeMode]::Multiple)
    [Console]::WriteLine('{"status":"ready"}')
    while ($true) {
        Start-Sleep -Milliseconds 100
        $item = $null
        while ($queue.TryDequeue([ref]$item)) {
            [Console]::WriteLine(($item | ConvertTo-Json -Compress))
        }
    }
} catch {
    [Console]::WriteLine((@{error=$_.Exception.Message} | ConvertTo-Json -Compress))
    exit 1
} finally {
    if ($null -ne $heard) { Unregister-Event -SourceIdentifier $heard.Name -ErrorAction SilentlyContinue }
    if ($null -ne $detected) { Unregister-Event -SourceIdentifier $detected.Name -ErrorAction SilentlyContinue }
    if ($null -ne $meter) { Unregister-Event -SourceIdentifier $meter.Name -ErrorAction SilentlyContinue }
    if ($null -ne $recognizer) { $recognizer.Dispose() }
}
