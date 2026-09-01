<#
garden_triage.ps1 - "Common vs distinctive" failure triage across one or more PRs.

Mirrors how the kfd-dlog stack was resolved: gather every failing leaf job across the
PRs, then split them into
  * COMMON      - the same job fails across multiple PRs regardless of the diff
                  => environment / infra flake, not caused by any one code change
  * DISTINCTIVE - a job that fails on only one PR
                  => inspect closely; could be the diff. -Deep reads its first failing
                     step to hint infra (checkout/fetch/setup death, timeout gap) vs
                     code (CMake/compile/test assertion).

Aggregator jobs ("* CI Summary", "Output failed jobs", notifiers) are excluded so the
count reflects real leaf failures, not roll-ups (skill s10).

Read-only. Examples from today:
  # single PRs triaged together (shared infra shows up as COMMON):
  .\garden_triage.ps1 -Prs 10000,10802,10396 -Repo ROCm/rocm-systems
  # a stack, with first-failing-step hints:
  .\garden_triage.ps1 -Prs 10011,10012,10210 -Repo ROCm/rocm-systems -Deep
#>
param(
  [Parameter(Mandatory)][int[]]$Prs,
  [string]$Repo = 'ROCm/rocm-systems',
  [string]$Workflow = 'TheRock CI',
  [switch]$Deep
)
$env:GH_PAGER = ''

function Normalize($name){          # collapse shard/attempt/matrix noise so the same lane groups together
  $n = $name -replace '\(shard \d+ of \d+\)',''
  $n = $n -replace '\([^)]*\|\s*([^)]+)\)','($1)'   # (comp,comp,... | gfx94X-dcgpu) -> (gfx94X-dcgpu)
  ($n -replace '\s+',' ').Trim().TrimEnd('/').Trim()
}
function IsAggregator($name){
  $name -match 'CI Summary$' -or $name -match 'Output failed jobs' -or `
  $name -match 'Evaluate workflow results' -or $name -match 'notify|Notify'
}
function StepHint($repo,$jobId){     # cheap infra-vs-code hint from the first failing step
  $j = gh api "repos/$repo/actions/jobs/$jobId" | ConvertFrom-Json
  $bad = $j.steps | Where-Object { $_.conclusion -notin @('success','skipped',$null) } | Select-Object -First 1
  if (-not $bad) { return 'no-failed-step (cancelled/zero-signal)' }
  $s = $bad.name
  if ($s -match 'Set up job|Fetch sources|checkout|container|Driver|GPU sanity|download|Prepare') { return "infra? step='$s'" }
  if ($s -match 'Build|CMake|Compile|Test|cmake') {
    $dur = if ($bad.started_at -and $bad.completed_at) { [int](([datetime]$bad.completed_at)-([datetime]$bad.started_at)).TotalMinutes } else { $null }
    if ($dur -ge 29 -and $dur -le 31) { return "infra? step='$s' (~${dur}min timeout gap)" }
    return "code? step='$s'"
  }
  return "inspect step='$s'"
}

# 1. Collect failing leaf jobs per PR
$rows = @()
foreach ($pr in $Prs) {
  $sha = (gh pr view $pr --repo $Repo --json headRefOid | ConvertFrom-Json).headRefOid
  $runs = gh api "repos/$Repo/actions/runs?head_sha=$sha&per_page=100" --paginate | ConvertFrom-Json
  $run = $runs.workflow_runs | Where-Object { $_.name -eq $Workflow } | Sort-Object created_at -Descending | Select-Object -First 1
  if (-not $run) { Write-Warning "#${pr}: no '$Workflow' run on $sha"; continue }
  $jobs = (gh api "repos/$Repo/actions/runs/$($run.id)/jobs?per_page=100" --paginate | ConvertFrom-Json).jobs
  foreach ($j in $jobs | Where-Object { $_.conclusion -eq 'failure' }) {
    if (IsAggregator $j.name) { continue }
    $rows += [pscustomobject]@{ Pr=$pr; Job=(Normalize $j.name); JobId=$j.id; RunId=$run.id }
  }
}
if (-not $rows) { "No leaf job failures found across: $($Prs -join ', ')"; return }

# 2. Group by normalized job name; COMMON = appears on >1 PR
$groups = $rows | Group-Object Job | ForEach-Object {
  $prs = ($_.Group.Pr | Sort-Object -Unique)
  [pscustomobject]@{ Job=$_.Name; PrCount=$prs.Count; Prs=($prs -join ','); Kind = if ($prs.Count -gt 1) {'COMMON'} else {'DISTINCTIVE'}; Sample=$_.Group[0] }
} | Sort-Object @{e='Kind';Descending=$true}, @{e='PrCount';Descending=$true}, Job

"`n===== COMMON failures (same lane across >1 PR => environment/infra, not diff) ====="
$common = $groups | Where-Object Kind -eq 'COMMON'
if ($common) { $common | Format-Table @{n='PRs';e='PrCount'}, Prs, Job -Auto } else { "  (none)" }

"`n===== DISTINCTIVE failures (single PR => inspect for a code cause) ====="
$distinct = $groups | Where-Object Kind -eq 'DISTINCTIVE'
if ($distinct) {
  foreach ($g in $distinct) {
    $line = "  #$($g.Prs)  $($g.Job)"
    if ($Deep) { $line += "  ->  " + (StepHint $Repo $g.Sample.JobId) }
    $line
  }
} else { "  (none)" }

"`n----- verdict aid -----"
"  COMMON lanes are shared infra/environment noise (rule out the diff)."
"  DISTINCTIVE lanes are the ones to justify: -Deep hints infra vs code from the first failing step,"
"  but the final infra-vs-code call is the gardener's (read the log, not just the step name)."
