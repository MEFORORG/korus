---
name: "fleet-push-or-open-a-pr"
description: "Push a branch, open a pull request, or touch CI or the merge queue. Use before the push and before anything that reads a check result."
user-invocable: true
disable-model-invocation: false
---

# fleet-push-or-open-a-pr

> Shared fleet rules, split out of [COMMON.md](../../../roles/COMMON.md) on 2026-09-05.
> Prohibitions that bind before this task starts stay in that file. Read it first.

### The PR route: every seat pushes its own, and the Lander merges

**Two steps since 2026-09-12.** Push your own branch and open your own pull request, which needs no
approval. The Lander merges it once the two required checks are green.

**NARROWED 2026-09-18, by owner ruling: a Builder under a Manager does not open the pull request.**
It pushes, reports and exits.

The Manager checks the branch reached the remote, opens the pull request, and hands it to the
Lander with five fields. Every other seat still opens its own.

| Item | Rule |
| --- | --- |
| Whose step 2 this is | Yours, unless you are a Builder working to a Manager's brief. Then it is the Manager's. |
| What the 2026-08-29 ruling covered | *"Sessions push their own."* The push. It never named the pull request. |
| RETIRED 2026-09-12, the middle step | The 2026-08-29 route had three: create the pull request, a review seat posts findings or approves, then it passes the work to the Lander. The owner retired that seat and nothing replaced it. |
| Nothing reads your diff before the merge | Your own pass is the only one it gets. Say in the pull request what you ran and what you did not vary. |
| Findings on a pull request are still worth posting | Any seat may write them, and the pull request outlives the session that did. Nobody waits for them. *Your pull request has to survive your own exit* covers what it must carry. |
| RETIRED 2026-09-04, the label | No label blocks a merge. The owner removed the review gate. The required checks on `main` are `gates (ubuntu-latest)` and `gates (windows-latest)`. |
| Do not spend a turn on it | `reviewed` now carries no machine meaning. Do not apply it, wait on it, or read a pull request as blocked for want of it. |
| What that label proved, kept | That a step happened, not that a party looked. A seat could label a pull request it wrote itself and satisfy the machine. Any gate keyed on a self-appliable mark has this shape. |
| Direct pushes to `main` | Still blocked by the harness. Branch and pull request is the path. |
| RETIRED 2026-08-31, the fallback | The old route around an absent review seat. The record is [retired/SEAT-RETIRED-2026-09-12.md](../../../roles/retired/SEAT-RETIRED-2026-09-12.md), *You sit in the pull request path*. |

**What the retired rows used to say**, kept because seats still quote them.

The 2026-08-29 fallback, retired on 2026-08-31:

*"If no Reviewer is running, hand the PR to the Lander as before -- a route through an absent seat
is a stall."*

The sentence that retired it, whose gate is now gone:

*"Since the review gate was armed the Lander cannot merge an unlabelled pull request either. Start a
Reviewer, have any other running seat read the diff and label it."*

**Neither one is a route now.** The gate went on 2026-09-04, the seat on 2026-09-12, and the fallback
became the whole path: push, open the pull request, and the Lander merges.

**The 2026-09-18 ruling changed only who performs the second step for a Builder.** The path itself is
unchanged, and no review step came back.

## A new test file is unlandable until the manifest classifies it

Source of record: `tests/tooling_manifest.txt` and its guard
`tests/test_tooling_partition.py::test_every_non_engine_test_is_classified`.

| Item | Rule |
| --- | --- |
| When it applies | You added a file under `tests/`. Ask before you commit, not after CI answers for you. |
| The question | Does it import `messagefoundry`, `messagefoundry_webconsole`, `harness` or `tee`? If yes, it is exempt. |
| The rule | If it imports none of them, add its path to `tests/tooling_manifest.txt` in the same commit. |
| The path form | Write the path exactly as `git diff --name-only` reports it. `ci.yml` matches with `grep -qxFf`, so a bare basename matches nothing. |
| Do not sort | The manifest is read as a `set()` and is already unsorted on `main`. Sorting it rewrites unrelated lines into your diff. |
| Insert, do not move | Put the one new line at its alphabetical slot and leave every other line untouched. |
| The check | Run `pytest tests/test_tooling_partition.py` before you commit. It takes under a second. |
| Why it is not optional | The guard reds all three required test legs, and it is not marked `tooling`, so `-m 'not tooling'` does not deselect it. |
| Why you will not see it | It fails only in CI, after your process has exited. The pull request looks fine when you open it and can never go green. |
| The cost, measured | 2026-09-04: eight open pull requests were unlandable for this one missing line each. None of them could ever have merged. |

---

## Your pull request has to survive your own exit

Your process ends when the pull request opens. Nothing you author is watched by you afterwards, so
anything left half-done stays half-done until a different session notices. Leave it self-sufficient.

| Item | Rule |
| --- | --- |
| The invalidation race | RETIRED SUBJECT, LIVE LESSON. Where a check invalidates on an event, the event is the gate's own RUN, not your command returning. Acting straight after a push loses. |
| The order | Push. Wait for that branch's run to reach `completed`. Then act. Then read the state back. |
| The cost, measured | 2026-09-04: 15 of 16 pull requests had NO `reviewed` label, though the labelling command reported success on every one. The review gate's `synchronize` run stripped it after each push returned. |
| The gate that taught it is gone | The owner removed the review gate on 2026-09-04, so `reviewed` no longer gates anything. The race above is a property of gates, not of that one, so it recurs. |
| Read the newest run | A label cycle fired both an `unlabeled` run that failed and a `labeled` run that succeeded. The rollup shows the stale red; the newest run per name is the truth. |
| Do not trust exit 0 | `gh pr edit`, `gh run cancel` and `gh pr merge --disable-auto` can each report success and change nothing. Read the state back. |
| **A REFUSED COMMIT, THEN A SUCCESSFUL PUSH, SHIPS THE COMMIT BEFORE IT** | When a hook refuses, HEAD does not move. The next push then succeeds, and what it sends is the PREVIOUS commit. Nothing in either exit line says so. |
| Why the refusal is easy to miss | A `pre-commit` runner prints its PASSING hooks after the refusal, so the tail of the output is green. Reading the last lines hides the one that mattered. |
| Measured off-tree | It fired twice in one day, with two different gates. |
| After committing | Assert HEAD MOVED and the tree is clean. `git rev-parse HEAD` before and after, and `git status --porcelain` empty. |
| After pushing | Verify by CONTENT, not by the push's exit line. `git ls-remote origin <branch>` must equal your local HEAD. |
| It generalises | Any two-step where the first step can refuse silently and the second reports on its own success has this shape. |
| Re-derive, never reuse | Run ids and check ids go stale the moment a head moves. Re-derive with `gh run list -c "$sha"` at the current head. |
| Leave the question on it | If your brief left something open, write it in the pull request body. There is no session to ask later, and a comment is the only channel that outlives you. |

---

## The merge queue belongs to one seat, and BEHIND is not your problem

Source of record: `roles/LANDER.md`. This section is what every other session needs so it does not
fight the queue by accident. The rules that catch these errors live in *Measure it before you
conclude* and *A green light proves only what the gate asserts*. These are the instruments they
apply to.

| Item | Rule |
| --- | --- |
| A queue IS enabled | Branch protection does not expose merge-queue config, so a missing `merge_queue` key there proves nothing. Read it with the GraphQL `mergeQueue(branch:"main")` field before proposing to enable one. |
| Do not enqueue or dequeue | The queue is the Lander's, and it is one seat's job precisely so these races stop. Dequeuing also deletes the entry's `gh-readonly-queue` branch and orphans every run already queued against it. |
| Never `gh pr update-branch` -- **WHERE A QUEUE EXISTS** | The queue rebases each entry against the `main` it will actually land on, so BEHIND is not a merge blocker. Measured 2026-09-03: a pull request read BEHIND, the label was added with no push, and it went CLEAN. |
| **THAT CONDITION WAS MISSING UNTIL 2026-09-06, and this repository is where it bites** | The row above read as an absolute. It is right on the engine and wrong here. |
| The reading, with the control that arms it | `mergeQueue(branch:"main")` returns `null` on `wshallwshall/korus` and `MQ_kwDOS5JJRs4AA9_8` on `MEFORORG/MessageFoundry`, both read 2026-09-06. Both repository nodes returned an `id`, so the null is an absence, not a lookup failure. |
| What follows in a repository with no queue | Nothing rebases an entry. Under `strict=true`, BEHIND blocks until somebody runs `update-branch`, and it is the only thing that clears it. |
| The worked instance | korus PRs 57 and 58 each needed it to land on 2026-09-06. 58's head moved `a8d4e802` to `a7ee3c00`, a merge commit whose second parent `53ac1bde` was the `main` tip at that moment. |
| So run *A queue IS enabled* FIRST | That row already tells you to read `mergeQueue` rather than infer it from branch protection. This prohibition depends on its answer. |
| What a rebase costs | Every `update-branch` fires a `synchronize`, which restarts every required context. It buys nothing here. It also stripped `reviewed`, until that gate went on 2026-09-04. |
| Never arm auto-merge | Enqueuing is the Lander's call. Auto-merge fires on the head it SAW, so a later push is dropped: the pull request reads MERGED, the branch stays alive, and nothing reports a problem. |
| Read the log, then rerun | Name the failing test and its mechanism before rerunning. One rerun. A second red on the same leg is a finding, not a flake. Record which leg and which head SHA on the pull request. |
| `completed` is not `succeeded` | `status == completed` includes `skipped` and `cancelled`. Count `conclusion`. Measured: 79 of 100 runs were skipped. |
| Run status is not job status | A run reports `queued` while its jobs are completing. When the question is "is work happening", read `actions/runs/<id>/jobs`. |
| What to send the Lander | A pull request that is genuinely ready, with any defect you know of named; a red you have diagnosed, with the mechanism; a correction with the command you ran. |
| What not to send | A recommendation to enqueue, dequeue, rebase or rerun. |

---
