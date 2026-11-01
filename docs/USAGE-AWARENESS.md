# Usage awareness: Knowing when to stop, without lying about it

<a id="tldrbluf"></a>

A usage hook should warn a session before its plan pool runs out. These eight rules define what it
must check and when it must refuse to report a number.

Each rule came from a tool that looked healthy but answered the wrong question. No hook ships here:
it would depend on changing internals and could fail without warning.

Use these rules when building your own hook. [Why you want this at all](#why-you-want-this-at-all) explains the purpose behind them.

---

## Why you want this at all

Warn before a hard cutoff causes lost work. That purpose sets different requirements from budgeting.

A budgeting tool can be inaccurate without warning. A lost-work warning must arrive before a session
runs out mid-refactor with nothing committed.

The hook must refuse to report an uncertain reading, because someone will act on it. When it warns,
protect the work:

1. Commit what exists, even if partial. A checkpoint commit beats a clean tree you no longer have.
2. Push branches, or otherwise get the work somewhere that survives the session ending.
3. Write a handoff for whoever picks it up, including yourself in four hours.

## Rule 1: A percentage is meaningless without its account

An early hook hardcoded an account and reported 93 percent weekly usage. The session's actual pool
was at 5 percent; both the displayed number and account were wrong.

> **A hook that is confidently wrong is worse than no hook. It converts "I should check" into
> "I already know."**

Changing the hardcoded account leaves the same defect. No constant can identify every session's pool
across several logins or remain correct after an account switch.

Resolve each session's pool from its config root. Each login has its own root; the path identifies
the account ([Desktop accounts](DESKTOP-ACCOUNTS.md)). Say when you cannot resolve it.

## Rule 2: Several signals look authoritative and are wrong

Checks found that each signal below failed to answer the question it appeared to answer:

| Signal | Why it is wrong |
|---|---|
| The CLI's stored login | It is the *CLI's* login. A desktop session can bill a different account entirely, and did. |
| A cached utilization figure beside it | Wrong account **and** hours stale. Two independent defects in one field. |
| The CLI's credentials file | The CLI again. Same category error. |
| The per-session liveness record on disk (pid, start time, session id, cwd) | Carries no account field, so the file's *contents* name no login. Its path does ([Token accounting](TOKEN-ACCOUNTING.md)). |
| Token-file modification times | They track whichever account the tool last polled, so they point at its own most recent behavior. **A signal derived from your own tool's activity is a mirror, not a measurement.** |

Polling activity cannot independently identify the account. It only shows what your tool last
polled.

## Rule 3: Cross-check against an independent sample, and refuse when they disagree

The reading must be checked against an independent sample for the same organization. If the samples
disagree, report **UNKNOWN**.

Apply both conditions:

- Check a slow-moving figure. The weekly one moves single points per hour, and would have caught
  the 93-against-5 bug on its first run. The short-window figure, while one existed, dropped to near
  zero when its window rolled -- 22 percent to 2 percent in one sample -- so it disagreed constantly.
- Sample age is a validity condition. Past a few missed sampling intervals the second source is no
  longer evidence, and the result is **UNKNOWN** with staleness as the reason. It never falls back
  to the unchecked number, which would look exactly like a passed check.

## Rule 4: Never print a band beside an account unless you established all three

An UNKNOWN result must identify the pool with an opaque identifier and say usage is undetermined. A
token file alone cannot establish that a login belongs to this session.

Report only what you established. If the account is known but usage is not, say so; a number without
a known account must not appear beside a login name.

If the account and usage are known but the reset time is not, report that missing time. Rule 8
cannot be applied without it.

## Rule 5: The diagnostics are the payload when something fails

A filter kept only lines naming the two windows. It dropped every refusal message, leaving UNKNOWN
results with no reason.

Check a failing run's output before choosing a filter. A filter designed only for success can remove
the reasons a reading failed.

## Rule 6: A warning path must not be able to kill itself

Keep these three constraints:

- Never block or error a prompt. Every path exits 0. A usage warning that breaks a session is worse
  than the cutoff it warns about.
- **ASCII output only.** A `UnicodeEncodeError` on print gets swallowed by the never-throw guard, so the
  warning vanishes *exactly when it was needed*. See [TIPS-AND-TRICKS.md](TIPS-AND-TRICKS.md) for why this is a general rule
  and not a style preference.
- Persist the failure state too, with a short TTL. An earlier version re-ran a 25-second subprocess
  on every prompt during an upstream outage, inside a hook with a 30-second budget. The failure mode
  of "retry until it works" is a hook that times out forever.

## Rule 7: Cache per pool, never in one unlabeled slot

Key the cache by pool. With one unlabeled slot, the first writer decides what every later reader
sees during that refresh window, regardless of the account requested.

## Rule 8: A threshold is not a decision

A session here paused work after reading a percentage without checking the reset time.

Seven percent remaining with 7 minutes to reset can be plenty. The same 7 percent with four hours
left may require a handoff.

A threshold alone can pause work too early or miss a risk before a distant reset. These examples
show percent remaining; the other figures on this page show percent consumed.

A peer withdrew a threshold-based pause after checking the clock: the window would reset within
minutes, making the remaining budget effectively unlimited. The peer wrote:

> The priority was right for a different reason than the one I gave. I conflated a genuine loss risk
> with a usage threshold and used the threshold to justify the priority.

Evaluate usage together with time to reset, and state which drove the decision. A useful reading
needs the number, its pool, and the window's reset time.

---

## On Windows, one interpreter can see a directory that another cannot

On Windows, an interpreter launched by full path can see a directory hidden from its app-execution
alias. Installer-level AppData virtualization causes this difference.

Wire hooks with the full interpreter path. Report UNKNOWN for missing and empty directories;
virtualization can replace contents while leaving a valid path.

A hook may work by hand yet read nothing when the client runs it. Missing data and reassuring data
must never produce the same output.

## Related

- [TIPS-AND-TRICKS.md](TIPS-AND-TRICKS.md) -- the general form of most of the above
- [HOOKS.md](HOOKS.md) -- fail-open versus fail-closed, and declaring which you chose
- [CASE-STUDY-drift-audit.md](CASE-STUDY-drift-audit.md) -- auditing controls that look installed
- [TOKEN-ACCOUNTING.md](TOKEN-ACCOUNTING.md) -- what a weekly percentage counts, measured on four accounts
- [DESKTOP-ACCOUNTS.md](DESKTOP-ACCOUNTS.md) -- one config root per account, and how to read which one a session is on
