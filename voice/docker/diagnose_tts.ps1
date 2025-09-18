param(
  [string]$Container = "voice_runner",
  [switch]$RunTTS
)

function Run([string[]]$a) {
  try {
    $tf=[IO.Path]::GetTempFileName(); $ef=[IO.Path]::GetTempFileName()
    $p = Start-Process -FilePath $a[0] -ArgumentList ($a[1..($a.Count-1)]) `
         -PassThru -NoNewWindow -Wait -RedirectStandardOutput $tf `
         -RedirectStandardError $ef
    $o = (Get-Content $tf -Raw -EA SilentlyContinue); $e = (Get-Content $ef -Raw -EA SilentlyContinue)
    Remove-Item $tf,$ef -Force -EA SilentlyContinue
    [pscustomobject]@{ Code=$p.ExitCode; Out=$o; Err=$e }
  } catch {
    [pscustomobject]@{ Code=997; Out=""; Err=$_.Exception.Message }
  }
}

$checks = @()

# Docker available
$r = Run @("docker","version","--format","{{.Server.Version}}")
$dockerOk = ($r.Code -eq 0)
$checks += [pscustomobject]@{
  Check="Docker available"; Pass=$dockerOk; Detail="$($r.Out)".Trim(); Hint="$($r.Err)".Trim()
}
if (-not $dockerOk) { $checks | Format-Table -AutoSize; exit 1 }

# Container running?
$r = Run @("docker","ps","-q","-f","name=^$Container$")
$running = -not [string]::IsNullOrWhiteSpace("$($r.Out)")
$detail  = if ($running) { "Up" } else { "Not running" }
$checks += [pscustomobject]@{ Check="Container running"; Pass=$running; Detail=$detail; Hint="" }
if (-not $running) { $checks | Format-Table -AutoSize; exit 0 }

# Bind mount present?
$r = Run @("docker","inspect","-f","{{json .Mounts }}",$Container)
$mounts = @(); try { $mounts = $r.Out | ConvertFrom-Json } catch {}
$bind = $mounts | Where-Object { $_.Destination -eq "/output" -and $_.Type -eq "bind" } | Select-Object -First 1
$checks += [pscustomobject]@{ Check="Bind mount /output"; Pass=($null -ne $bind); Detail=$bind.Source; Hint="" }
$hostOut = $bind.Source

# Probe write to /output and host visibility
$probe = "_probe_$([DateTimeOffset]::Now.ToUnixTimeSeconds()).txt"
$lc = 'echo ok > /output/{0} && cat /output/{0}' -f $probe
$r = Run @("docker","exec",$Container,"/bin/bash","-lc",$lc)
$okCtr = ($r.Code -eq 0 -and "$($r.Out)".Trim() -eq "ok")
$checks += [pscustomobject]@{ Check="Write /output in container"; Pass=$okCtr; Detail="$($r.Out)".Trim(); Hint="$($r.Err)".Trim() }
$hostProbe = Join-Path $hostOut $probe
$okHost = Test-Path $hostProbe
$checks += [pscustomobject]@{ Check="Host sees /output"; Pass=$okHost; Detail=$hostProbe; Hint="" }
if ($okHost) { Remove-Item $hostProbe -Force -EA SilentlyContinue }

# Python venv present
$r = Run @("docker","exec",$Container,"/bin/bash","-lc","/app/venv/bin/python -V")
$checks += [pscustomobject]@{ Check="Python venv"; Pass=($r.Code -eq 0); Detail="$($r.Out)".Trim(); Hint="$($r.Err)".Trim() }

# PyYAML import
$pyyaml = '/app/venv/bin/python -c "import yaml,sys; sys.stdout.write(\"yaml ok\")"'
$r = Run @("docker","exec",$Container,"/bin/bash","-lc",$pyyaml)
$checks += [pscustomobject]@{ Check="PyYAML import"; Pass=($r.Code -eq 0 -and "$($r.Out)".Contains('yaml ok')); Detail="$($r.Out)".Trim(); Hint="$($r.Err)".Trim() }

# Models present
$models = 'm=/app/piper_models/en_US-lessac-medium.onnx; c=$m.json; if [ -f $m ] && [ -f $c ]; then echo exists; else echo missing; fi'
$r = Run @("docker","exec",$Container,"/bin/bash","-lc",$models)
$checks += [pscustomobject]@{ Check="Models present"; Pass=($r.Code -eq 0 -and "$($r.Out)".Contains('exists')); Detail="$($r.Out)".Trim(); Hint="$($r.Err)".Trim() }

# Synthesize WAV and copy to /output
$wav = "_diag_$([DateTimeOffset]::Now.ToUnixTimeSeconds()).wav"
$sy = ('/app/venv/bin/python -c "from piper.voice import PiperVoice as V; ' +
       'm=\"/app/piper_models/en_US-lessac-medium.onnx\"; c=m+\".json\"; ' +
       'v=V.load(m,c); f=open(\"/app/{0}\",\"wb\"); v.synthesize(\"diagnostic ok\", f); ' +
       'f.close(); print(\"wav ok\")"; cp -f /app/{0} /output/{0} && echo copied') -f $wav
$r = Run @("docker","exec",$Container,"/bin/bash","-lc",$sy)
$okWav = ($r.Code -eq 0 -and "$($r.Out)".Contains('wav ok') -and "$($r.Out)".Contains('copied'))
$checks += [pscustomobject]@{ Check="Synthesize WAV"; Pass=$okWav; Detail="$($r.Out)".Trim(); Hint="$($r.Err)".Trim() }
$hostWav = Join-Path $hostOut $wav
$checks += [pscustomobject]@{ Check="Host sees WAV"; Pass=(Test-Path $hostWav); Detail=$hostWav; Hint="" }
if (Test-Path $hostWav) { Remove-Item $hostWav -Force -EA SilentlyContinue }
Run @("docker","exec",$Container,"/bin/bash","-lc",("rm -f /app/{0}" -f $wav)) | Out-Null

# Optional end-to-end /app/run_tts.sh
if ($RunTTS) {
  $r = Run @("docker","exec",$Container,"/bin/bash","-lc","type /app/run_tts.sh | head -n 60 || true")
  $checks += [pscustomobject]@{ Check="run_tts.sh present"; Pass=($r.Code -eq 0); Detail="ok"; Hint="" }
  $e2e = "/app/run_tts.sh ''end-to-end ok'' && test -f /output/output.wav && echo present"
  $r = Run @("docker","exec",$Container,"/bin/bash","-lc",$e2e)
  $checks += [pscustomobject]@{ Check="run_tts.sh end-to-end"; Pass=($r.Code -eq 0 -and "$($r.Out)".Contains('present')); Detail="$($r.Out)".Trim(); Hint="$($r.Err)".Trim() }
  $o = Join-Path $hostOut "output.wav"; if (Test-Path $o) { Remove-Item $o -Force -EA SilentlyContinue }
}

$checks | Format-Table -AutoSize
