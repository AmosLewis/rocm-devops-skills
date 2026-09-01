<#
garden_bypass_single.ps1 - Bypass-merge one APPROVED single (non-stacked) PR whose
only required-gate failures are known infra flakes. Posts a rationale comment, then
admin-merges, then verifies. Read-only until -Go is passed.

  Single PR  -> gh pr merge --admin           (this script; no browser needed)
  Stacked    -> enqueue_bypass.py <PR> --go    (CDP; bottom->top; NOT this script)

Example (today):
  .\garden_bypass_single.ps1 -Pr 10000 -Repo ROCm/rocm-systems `
    -Unrelated 'the rocshmem reduce change' `
    -Fails 'Linux MI455 Build (gfx125X-dcgpu) / Build Linux Packages: Fetch-sources network timeout' `
    -Note "@kesag: Manually verified for CI run on ``ubuntu24-therock && 16gfx90a-infiniband``" -Go
#>
param(
  [Parameter(Mandatory)][int]$Pr,
  [string]$Repo = 'ROCm/rocm-systems',
  [Parameter(Mandatory)][string]$Unrelated,           # e.g. "the one-file rocblit.cpp change"
  [Parameter(Mandatory)][string[]]$Fails,             # one "Job name: reason" per required-gate failure
  [string]$Note = '',                                 # optional author/owner quote to include
  [ValidateSet('merge','squash','rebase')][string]$Method = 'merge',
  [switch]$AckBuildFailureIsInfra,                    # required to proceed if a reason reads as a compile error
  [switch]$Go
)
$env:GH_PAGER = ''

# 1. Gate: must be OPEN + APPROVED + BLOCKED (a required check failing, nothing else to do)
$v = gh pr view $Pr --repo $Repo --json state,mergeStateStatus,reviewDecision,baseRefName,isDraft | ConvertFrom-Json
"PR #$Pr  state=$($v.state) base=$($v.baseRefName) merge=$($v.mergeStateStatus) review=$($v.reviewDecision) draft=$($v.isDraft)"
if ($v.state -ne 'OPEN')            { throw "not OPEN" }
if ($v.isDraft)                     { throw "is DRAFT - author marks ready" }

# Approval detection: reviewDecision alone is NOT reliable. GitHub returns an
# empty/null reviewDecision even when code owners HAVE approved (e.g. CODEOWNERS
# spanning several owner teams: some approve while others stay auto-requested).
# check_approval.py resolves the real state from latestOpinionatedReviews +
# outstanding codeowner reviewRequests. Only a true APPROVED (all required owners
# satisfied, no changes requested) is bypass-eligible on the review axis;
# PARTIAL/NOT_APPROVED/CHANGES_REQUESTED route to CODEOWNERS (never bypass review).
$approvalOut = python "$PSScriptRoot\check_approval.py" $Pr --repo $Repo 2>&1
$approvalOut | ForEach-Object { "  $_" }
$approvalRc = $LASTEXITCODE
if ($approvalRc -ne 0) {
  throw "review not fully APPROVED (check_approval verdict rc=$approvalRc) - route the outstanding code owners; a gardener bypass is for infra/flaky CI, not for unmet code review."
}

# 1b. HARD RULE guard: a failing build/compile step is never bypass-eligible unless it is proven infra.
# Inspect each failure REASON (the text after the first ':'), not the job name - job names legitimately
# contain "Build". Flag genuine compile-error signatures; refuse unless the operator has read the build
# log and explicitly asserts it is infra via -AckBuildFailureIsInfra. See SKILL.md "Hard rule" (#10179).
$compilePat = 'compil|static[ _]assert|undefined reference|\bld:|\blink error\b|cmake error|error:|build failed'
$flagged = @()
foreach ($f in $Fails) {
  $reason = if ($f.Contains(':')) { $f.Substring($f.IndexOf(':') + 1) } else { $f }
  if ($reason -match $compilePat) { $flagged += $f.Trim() }
}
if ($flagged.Count -gt 0) {
  "`n*** BUILD/COMPILE FAILURE DETECTED in a failure reason ***"
  $flagged | ForEach-Object { "  - $_" }
  "A failure inside the build/compile step is presumed CODE and is NOT bypass-eligible unless you have"
  "proven from the build log it died before the compiler ran (fetch/network/toolchain/runner). Do not"
  "take the author's word that it is 'unrelated' or 'script failures' - open the build log yourself."
  if (-not $AckBuildFailureIsInfra) {
    throw "Refusing to bypass a build/compile failure. If the log truly shows an infra cause, re-run with -AckBuildFailureIsInfra; otherwise route to CODEOWNERS / get a revert."
  }
  "-AckBuildFailureIsInfra set: proceeding on your explicit assertion that the build log shows infra."
}

# 2. Build the #10579-style rationale comment
$sb = New-Object System.Text.StringBuilder
if ($Note) { [void]$sb.AppendLine("Will merge given code owner approval and the author's note that"); [void]$sb.AppendLine("> $Note"); [void]$sb.AppendLine() }
else       { [void]$sb.AppendLine("Will merge given code owner approval.") }
[void]$sb.AppendLine("The TheRock CI failures are only known infra issues, unrelated to ${Unrelated}:")
foreach ($f in $Fails) { [void]$sb.AppendLine("- ``$($f.Split(':')[0].Trim())``: $($f.Substring($f.IndexOf(':')+1).Trim())") }
$body = $sb.ToString().TrimEnd()
"`n--- comment preview ---`n$body`n-----------------------"

if (-not $Go) { "`nDRY RUN - pass -Go to post the comment and admin-merge."; return }

# 3. Post comment, then admin-merge (bypasses the failing required gate; token auth, no browser)
$tmp = New-TemporaryFile
Set-Content -Path $tmp -Value $body -Encoding utf8 -NoNewline
$curl = gh pr comment $Pr --repo $Repo --body-file $tmp
Remove-Item $tmp -ErrorAction SilentlyContinue
"comment posted: $curl"

gh pr merge $Pr --repo $Repo --$Method --admin | Out-Null
Start-Sleep -Seconds 3

# 4. Verify + emit Teams paste-ready line
$m = gh pr view $Pr --repo $Repo --json state,mergedBy | ConvertFrom-Json
"result: #$Pr state=$($m.state) by=$($m.mergedBy.login)"
if ($m.state -eq 'MERGED') { "`nTeams reply -> Merged! $curl" } else { throw "merge did not complete - re-check state" }
