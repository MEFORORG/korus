# KORUS

**Keep One Repo, Unblock Sessions.** A working method for running several AI coding
sessions against one codebase without them colliding, losing work, or quietly agreeing
with each other.

## Status: early, and the spec is being written now

KORUS grew out of tooling for a single project and has been revised repeatedly under
real use. Its properties were **discovered, not designed** -- most of what is known
about it came from running it and measuring what broke.

This repository exists to change that. It uses
[Spec Kit](https://github.com/github/spec-kit) for spec-driven development: the
constitution first, then the spec, then the plan.

**Nothing here is stable yet.** Findings are still being consolidated from three days of
measured operation, and some published guidance has already been shown wrong.

## Start here: the constitution

**[The KORUS Constitution](.specify/memory/constitution.md)** is the document to read first.
It holds the rules a session, a seat, a gate or a later spec may not break, and **every
article names the evidence behind it** so a reader can check rather than trust.

Alongside it are the seat playbooks in [`roles/`](roles/), the working guides in
[`docs/`](docs/), and the specs in [`specs/`](specs/). The constitution outranks all of them:
where a playbook and an article disagree, the article wins and the playbook is the bug.

Thirteen articles, in short:

| | |
|---|---|
| I | No session is the only reader of its own work |
| II | Publish readings, not conclusions |
| III | A gate that cannot check identity must make refusal legible |
| IV | Every claim names the condition it did not vary |
| V | No rule may manufacture its own evidence |
| VI | A number without its instrument is not a measurement |
| VII | Waiting is a design cost and it is measured |
| VIII | The account roster is assigned by the Owner, and no design may infer it |
| IX | Built for Claude Code, and no design may require a particular surface |
| X | A seat that cannot be measured cannot be steered |
| XI | A seat's job is to write something down |
| XII | The shared write surface is the boundary that binds, not the account |
| XIII | Work reaches the model through Claude Code, never through the API |

It is at **v1.16.0** and it expects to be wrong in places. Most articles rest on a small
number of observations, several from a single night of operation, and the document says so.
Amendments require evidence, and retired text stays with the reason it was retired.

## What problem it solves

Run more than one AI session on one repository and four things go wrong:

1. **They collide.** Two sessions in one checkout overwrite each other's work.
2. **They lose work.** A session ends and its context, findings and half-finished
   branches go with it.
3. **They agree wrongly.** Two sessions that share a hidden condition reach the same
   wrong answer and their agreement reads as confirmation.
4. **They cannot be told apart.** A stalled session and a working one look identical
   from outside.

KORUS is the set of roles, gates and instruments that address these.

## Two design facts that came from measuring rather than guessing

Both on the repository this tooling was developed in. Over 30 days, **166 sessions** ran with
their working directory in the shared primary checkout. Both percentages below are shares of
the Edit/Write calls **those** sessions made, not of every write on the machine:

- **A banner asking sessions to use worktrees does not work.** 6,075 of those calls (**44%**)
  landed in the primary's own tree. If a convention matters, enforce it with a hook. A
  reminder produces no evidence either way.
- **Gate on the write's target path, never the session's working directory.** Another 4,010 of
  them (**29%**) landed inside a sibling worktree by absolute path, which is already correct
  behaviour that a directory-keyed gate would have denied every one of.

This page is the record for both figures. Neither has been re-measured, and nothing in this
repository can recompute them.

## The shape

Work is divided among **seats**, each a session with one job:

| Seat | What it does | Lifetime |
|---|---|---|
| Manager | Plans, runs workers, holds the owner's attention | long-lived |
| Builder | Takes one brief, does the work, opens a pull request | one turn |
| Regulator | Attributes a failing build | woken on a red |
| Steward | Writes files other seats read | cron, no model calls |
| Lander | Decides merge order | long-lived |

Nine further seats were tried and retired: the Console on 2026-09-10 and another on 2026-09-12,
with nothing replacing that one and its name deliberately left out here. Why each went is part of
the record this repository holds.
Nine further seats were tried and retired: the Console on 2026-09-10, and a ninth on 2026-09-12 that is deliberately left unnamed here, with nothing replacing it. Why each went is part of the record this repository holds.

## Repository layout

```
.specify/memory/constitution.md   the rules nothing may break
.specify/                         Spec Kit scaffold: templates and scripts
specs/                            one directory per feature: spec.md, plan.md, tasks.md
```

## Related

- [claude-multisession](https://github.com/wshallwshall/claude-multisession) -- the
  earlier public home for KORUS docs and scripts. **Its site deploy was disabled on 2026-09-08,
  and korus publishes the site now.** The findings moved here too, so the clause saying they
  live there is retired.

## Licence

See [LICENSE](LICENSE).
