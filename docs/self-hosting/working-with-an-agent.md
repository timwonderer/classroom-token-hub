---
title: "Working with an AI agent"
category: self-hosting
description: Use an AI agent to explain, carry out and troubleshoot self-hosting steps while checking its work.
roles: [operator]
---

# Working with an AI agent

You can use an AI agent as a working partner throughout this guide. It can
explain an unfamiliar command, inspect the release's source, compare results
and carry out actions on a computer you let it access. You don't need to learn
all of Flask, PostgreSQL and nginx first. Learn enough at each step to know
what you're changing and how you'll check it.

**Your part:** choose the server and budget, keep control of the credentials,
and decide when to admit real students or erase data. **The agent's part:**
show its reasoning in terms you can evaluate and verify the result of its work.

## Start with this prompt

Copy this into your agent's conversation. Replace the bracketed details. You
can leave unknown fields as “not chosen yet.”

```text
Help me self-host Classroom Token Hub using docs/self-hosting in the exact
release I choose. I'm a technologically capable teacher, but I haven't
administered Flask, PostgreSQL or nginx before. Explain terms where we use
them. Keep each explanation connected to the step we're doing.

My computer: [macOS / Linux / Windows with WSL]
Server provider: [provider or not chosen yet]
Release tag and full SHA: [values or not chosen yet]
Current chapter and last successful checkpoint: [place]
Does this installation contain real classroom data? [yes/no]
Agent access: [chat only / local repository / local terminal / SSH]

Read the relevant guide and the actual release's installer before suggesting
commands. Start by telling me where each command runs, what it changes and
what result we expect. Work one checkpoint at a time and verify what happened.
Use the documented defaults unless you explain why a change is necessary.

If you have terminal access, begin with read-only inspection. Stay within the
host and repository I identify. Before a change that deletes data, replaces
keys, changes DNS, incurs a new charge or interrupts users, describe the exact
target and consequence so I can make that decision. Routine actions I've
already authorized don't need repeated confirmation.

Do not print secret files, send credentials to chat, use my real students as
test data, or disable protections to clear an error. I will enter provider
keys at private prompts. Preserve application encryption, lookup and audit
keys when data already exists. Never edit the installer's journal or pinned
manifest to pretend a stage passed. Never run pytest against the classroom
database: this repository's test setup resets its target schema.

If a check fails, inspect and explain the cause before proposing one repair.
Keep a short private handoff: release, server label, last passed checkpoint,
error, changes made and next check. Include no keys or student records.
Distinguish a command you actually ran and verified from one you only propose.
```

> [!NOTE]
> **A chat assistant and an agent have different access.** A chat assistant
> can explain what you paste; it cannot inspect your server unless a connected
> tool gives it that access. “That should work” is a prediction. “I ran this
> command on this host and observed this result” is a check. Ask which it means.

## Know which computer you're using

The terminal is a window for issuing commands. SSH connects that window to a
second computer. The window stays on your screen, but the commands now run on
the server. This distinction matters most when creating or deleting files.

| Where the guide says to work | How to get there | How to check |
| --- | --- | --- |
| Your computer | Open Terminal on macOS/Linux, or your WSL terminal on Windows. | Run `hostname` and `whoami` before connecting. Note your local computer name and username. |
| Server, as root | From that local terminal, use the SSH command in Part 2. Some providers also need `sudo -i`. | Run `hostname` and `whoami` again. The name should match your server; the username should be `root`. |
| Your computer again | Use a separate local terminal window for backups, or leave the SSH session with `exit`. | Check `hostname` and `whoami`. If you entered `sudo -i`, one `exit` leaves root but may still leave you on the server. |
| Provider or Cloudflare dashboard | Open the service in your web browser. | Check the account and selected server/domain before changing it. |

**Example:** if your computer is `Tims-Mac` and the server is `cth-practice`,
`hostname` should change from the first to the second after SSH connects.
Those are examples; your actual names will differ. A `#` prompt alone doesn't
identify a computer.

## Read a command block without learning a programming language

| What you see | What to do with it |
| --- | --- |
| `classroom.example.org`, `203.0.113.10`, `vX.Y.Z`, `REPLACE` | These are examples or placeholders. Substitute the value the step requests. Never run them as your actual address or version. |
| `CTH_HOSTNAME=classroom.example.org` | Stores a value in this terminal session. Replace the example once; later `$CTH_HOSTNAME` uses that value. It disappears when the session closes. |
| `cd /root/cth-installer` | Changes the working folder. Relative paths in the next command start there. |
| A line ending in `\` | The command continues on the next line. Copy the whole command, including the continuation lines. |
| `A | B` | Sends A's output into B. The backup steps send the database directly into encryption this way. |
| `A && B` | Runs B only if A succeeds. Keep this connection intact; it often prevents the next action after a failure. |
| `> filename` | Writes output into a file. It can replace that file unless overwrite protection is enabled. |
| `<<EOF` through a later `EOF` | One block that writes several lines into a file. Copy both boundary lines and everything between them. |
| A prompt ending in `#` or `$` outside a code block | A sign the terminal is waiting. Don't add a prompt character to a command you copy. |

Run separate setup commands one at a time unless the guide specifically says
to paste a whole block. Wait for the result before continuing. If the terminal
shows a continuation prompt such as `>` and never returns, it may be waiting
for a missing quote or the end of a pasted block. Use **Ctrl+C** to cancel;
inspect the destination before retrying a block that might have written a file.

Some commands succeed silently. The guide tells you what check to run after
them. Silence and success are different things; the next check settles it.

## When you don't understand a step

```text
Explain step [number] in docs/self-hosting/[filename] before we run it.
First say what problem it solves. Then explain only the parts of the command
I need to understand to use it safely. Mark the values I replace, the values
I keep and where it runs. Give an example of success and one common failure.
Keep the exact command available so I can compare your explanation with it.
```

For example, “nginx is the web server” may still leave you wondering why CTH
needs it. A useful explanation connects it to your next action: “CTH currently
answers only inside the server. nginx receives the HTTPS connection and passes
it to CTH. This step will make the sign-in page reachable.”

## When something fails

Give the agent the step number, release tag and a **redacted error line**.
For example, `redis: service account cannot reach Redis socket` is useful.
The complete runtime file is not needed to diagnose that message.

```text
I'm following docs/self-hosting/[filename], step [number], release [tag/SHA].
The last successful checkpoint was [checkpoint]. The failing command was
[command with no secrets]. It reported [redacted error]. There [is/is not]
real data on this server.

Read this release's implementation of that check. Start with read-only
inspection and tell me which computer each diagnostic belongs on. Separate
what we observed from possible causes. Propose one bounded repair, explain
its effect on existing data and keys, and show the verification command.
Don't delete files, broaden permissions or disable security to clear a check.
If the error is an installer defect, identify the failing source and a fixed
release or a reproducible report. Don't silently modify the pinned checkout.
```

An agent can inspect a private setting locally and report “present and valid”
without printing its value. Set the same expectation for logs and student data.
For keys you must enter yourself, ask it to pause at the guide's hidden prompt.

## Check the agent's proposed repair

| Proposal | What you should be able to ask and verify |
| --- | --- |
| “Restart the service.” | Which service, why, who loses access, and what result after restart would confirm the cause? |
| “Change the firewall.” | Which port and source? Will a new SSH connection still work? Does HTTPS remain restricted to Cloudflare? |
| “Regenerate the keys.” | Is this still an empty practice installation? Existing data needs its original keys. Generating new ones can make that data unusable. |
| “Reset the database.” | Which exact database and host? What data will be erased? Why would a reset address this error? |
| “All tests pass.” | Which tests, against which disposable target? Tests must never use the classroom database. |
| “The server is healthy.” | Did it only answer `/health`, or did teacher sign-in, student claim and the intended classroom action also work? |

You don't need to recognize every command to ask these questions. The answers
should let you decide whether the repair fits the problem.

## Pause and resume

Use this after a completed checkpoint or while preserving an error:

```text
Make a short private handoff for continuing this installation. Record the
release tag and full SHA, server label, current chapter, last passed check,
commands that changed anything, unresolved errors and the next verification.
Describe credentials by name and protected location only. Don't copy their
values, student information or full logs. Say which terminal variables need
to be set again when I return. Don't record an unfinished check as passed.
```

Keep that handoff in your password manager's “CTH install” note. A new agent
can read it and inspect the current state rather than guessing from an earlier
conversation. [Continue with Part 1](part-1-accounts-and-domain.md), or return
to your current chapter.
