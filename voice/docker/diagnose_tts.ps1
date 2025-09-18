param(
  [string]$Container = "voice_runner",
  [switch]$RunTTS    # optional: also test /app/run_tts.sh end-to-end
)

function Exec([string[]]$cmd) {
  $p = Start-Process -FilePath $cmd[0] -ArgumentList $cmd[1..($cmd.Count-1)] `
        -NoNewWindow -PassThru -RedirectStandardOutput out.txt `
        -RedirectStandardError err.txt; $p.WaitForExit() | Out-Null
  [pscustomobject]@{ Code=$p.ExitCode
    Out=(Get-Content out.txt -Raw -EA SilentlyContinue)
    Err=(Get-Content err.txt -Raw -EA SilentlyContinue) }
}

$checks = @()

# Docker present
$r = Exec @("docker","version","--format","{{.Server.Version}}")
$checks += [pscustomobject]@{Check="Docker available"; Pass=($r.Code -eq 0); Detail=$r.Out.Trim(); Hint=$r.Err.Trim()}

# Container running?
$r = Exec @("docker","ps","-q","-f","name=^$Container$")
$running = [bool]$r.Out.Trim()
$checks += [pscustomobject]@{Check="Container running"; Pass=$running; Detail=($running?"Up":"Not running"); Hint=""}
if (-not $running) { $checks | Format-Table -AutoSize; return }

# Mounts
$r = Exec @("docker","inspect","-f","{{json .Mounts }}",$Container)
$mounts = @()
try { $mounts = $r.Out | ConvertFrom-Json } catch {}
$bind = $mounts | Where-Object { $_.Destination -eq "/output" -and $_.Type -eq "bind" } | Select-Object -First 1
$checks += [pscustomobject]@{Check="Bind mount /output"; Pass=($null -ne $bind); Detail=($bind.Source); Hint=""}
$hostOut = $bind.Source

# Probe write to /output and host visibility
$probe = "_probe_$([DateTimeOffset]::Now.ToUnixTimeSeconds()).txt"
$r = Exec @("docker","exec",$Container,"/bin/bash","-lc","echo ok > /output/$probe && cat /output/$probe")
$okInCtr = ($r.Code -eq 0 -and $r.Out.Trim() -eq "ok")
$checks += [pscustomobject]@{Check="Write /output in container"; Pass=$okInCtr; Detail=$r.Out.Trim(); Hint=$r.Err.Trim()}
$hostProbe = Join-Path $hostOut $probe
$okOnHost = (Test-Path $hostProbe)
$checks += [pscustomobject]@{Check="Host sees /output"; Pass=$okOnHost; Detail=$hostProbe; Hint=""}
if ($okOnHost) { Remove-Item $hostProbe -Force -EA SilentlyContinue }

# Python venv present
$r = Exec @("docker","exec",$Container,"/bin/bash","-lc","test -x /app/venv/bin/python && /app/venv/bin/python -V")
$checks += [pscustomobject]@{Check="Python venv"; Pass=($r.Code -eq 0); Detail=$r.Out.Trim(); Hint=$r.Err.Trim()}

# PyYAML import
$r = Exec @("docker","exec",$Container,"/bin/bash","-lc","/app/venv/bin/python - <<'PY'
import sys
try:
  import yaml
  print('yaml ok')
except Exception as e:
  print('yaml fail:', e); sys.exit(2)
PY")
$checks += [pscustomobject]@{Check="PyYAML import"; Pass=($r.Out -match "yaml ok"); Detail=$r.Out.Trim(); Hint=$r.Err.Trim()}

# PiperVoice + model presence
$r = Exec @("docker","exec",$Container,"/bin/bash","-lc","/app/venv/bin/python - <<'PY'
import os, sys
from piper.voice import PiperVoice
m='/app/piper_models/en_US-lessac-medium.onnx'
c=m+'.json'
print('model exists', os.path.exists(m), os.path.exists(c))
v=PiperVoice.load(m,c); print('piper ok')
PY")
$checks += [pscustomobject]@{Check="PiperVoice + models"; Pass=($r.Out -match "piper ok"); Detail=$r.Out.Trim(); Hint=$r.Err.Trim()}

# Synthesize to /app/output_diag.wav and copy to /output (cleanup after)
$wav = "_diag_$([DateTimeOffset]::Now.ToUnixTimeSeconds()).wav"
$r = Exec @("docker","exec",$Container,"/bin/bash","-lc","/app/venv/bin/python - <<'PY'
from piper.voice import PiperVoice
m='/app/piper_models/en_US-lessac-medium.onnx'; c=m+'.json'
v=PiperVoice.load(m,c)
with open('/app/$wav','wb') as f: v.synthesize('diagnostic ok', f)
print('wav ok')
PY
cp -f /app/$wav /output/$wav && echo copied")
$okWavCtr = ($r.Out -match "wav ok" -and $r.Out -match "copied")
$checks += [pscustomobject]@{Check="Synthesize WAV"; Pass=$okWavCtr; Detail=$r.Out.Trim(); Hint=$r.Err.Trim()}
$hostWav = Join-Path $hostOut $wav
$checks += [pscustomobject]@{Check="Host sees WAV"; Pass=(Test-Path $hostWav); Detail=$hostWav; Hint=""}
if (Test-Path $hostWav) { Remove-Item $hostWav -Force -EA SilentlyContinue }
Exec @("docker","exec",$Container,"/bin/bash","-lc","rm -f /app/$wav") | Out-Null

# Optional: end-to-end /app/run_tts.sh
if ($RunTTS) {
  $r = Exec @("docker","exec",$Container,"/bin/bash","-lc","set -e; type /app/run_tts.sh | sed -n '1,120p'")
  $checks += [pscustomobject]@{Check="run_tts.sh present"; Pass=($r.Code -eq 0); Detail="ok"; Hint=""}
  $r = Exec @("docker","exec",$Container,"/bin/bash","-lc","/app/run_tts.sh 'end-to-end ok' && test -f /output/output.wav && echo present")
  $checks += [pscustomobject]@{Check="run_tts.sh end-to-end"; Pass=($r.Out -match "present"); Detail=$r.Out.Trim(); Hint=$r.Err.Trim()}
  if (Test-Path (Join-Path $hostOut "output.wav")) { Remove-Item (Join-Path $hostOut "output.wav") -Force -EA SilentlyContinue }
}

$checks | Format-Table -AutoSize
