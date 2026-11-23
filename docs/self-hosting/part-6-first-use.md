---
title: "Part 6: First use"
category: self-hosting
description: Create your teacher account and class, claim a test student account, check health and open the site to students.
roles: [operator]
keywords: [self-hosting, tutorial, teacher signup, TOTP, student claim, health]
---

# Part 6: First use

**Work here: your browser, except for step 6.7.** You have checked the
machinery; now check the experience. Use fictional information for the first
class and student. This also gives you something recognizable to look for
when you test a backup restore.

A **seat** means one student's place on one class roster. The teacher creates
the place; the student claims it and chooses their own sign-in credentials.

Your CTH is running. Now use it the way a teacher and a
student will, before any real student sees it.

Throughout this part, `classroom.example.org` stands for your CTH hostname.

The teacher and student help pages linked below are also built into your own
CTH, under `https://classroom.example.org/docs/user-guides/`.

## 6.1 Get ready

**What you're doing.** Setting up a teacher browser and a separate student
browser.

**Why.** Your browser remembers who's signed in using small records called
**cookies**. Teacher and student tests need separate sessions so one login
doesn't replace the other. A second normal
window usually shares cookies; use a private window or a separate browser
profile for the student.

**Steps.**

1. Install an authenticator app on your phone if you haven't
   ([Before you begin](before-you-begin.md#required-by-the-current-release)).
2. Use your normal browser window as the **teacher**.
3. Use a private window, or a different browser, as the **student**.

**What you should see.** Both windows open `https://classroom.example.org/admin/login`.

**If something looks wrong.** If the page doesn't load, run the checks in
[6.7](#67-check-health-from-the-server).

## 6.2 Create your teacher account and first class

**What you're doing.** Signing up as the first teacher. Sign-up creates your
first class at the same time.

**Why.** Teacher accounts are only created through the app's own sign-up,
which records everything correctly. Never create accounts directly in the
database.

**Steps.** In the teacher window, open `https://classroom.example.org/admin/signup`.

1. Fill in the class form: class name, section (optional), your display name,
   and the class **time zone**. Pick it carefully: payroll and rent run on the
   class's time zone, and it can't be changed later.
2. Agree to the terms, complete the Turnstile check, and continue.
3. Choose a teacher **username**.
4. Scan the QR code with your authenticator app, and enter the six-digit code.

Add to your note: your **teacher username**. Your authenticator app now
holds the code generator; keep the phone safe.

**What you should see.** Your new class's dashboard.

**If something looks wrong.**

- **The Turnstile box doesn't appear, or says the site isn't allowed:** the
  Turnstile widget's hostname must be exactly your CTH hostname ([Part 1, 1.3](part-1-accounts-and-domain.md#13-create-the-turnstile-keys)).
- **The six-digit code is rejected:** the phone's clock may be wrong. Turn on
  automatic date and time on your phone, then try the next code.
- More help: [teacher login problems](https://github.com/timwonderer/classroom-token-hub/blob/main/docs/user-guides/diagnostics/teacher/login.md).

## 6.3 Sign out and sign in again

**What you're doing.** Proving you can get back in.

**Why.** It's better to find a sign-in problem now than on the first day of
class.

**Steps.** Sign out, then go to `https://classroom.example.org/admin/login`
and sign in with your username and the current code from your app.

**What you should see.** Your class dashboard again.

**If something looks wrong.** See [teacher login problems](https://github.com/timwonderer/classroom-token-hub/blob/main/docs/user-guides/diagnostics/teacher/login.md).

## 6.4 Add a passkey (recommended)

**What you're doing.** Letting your device sign you in with a fingerprint,
face or PIN.

**Why.** Passkeys resist phishing, and you won't need to type codes every
time ([why](before-you-begin.md#strongly-recommended-with-alternatives)).

**Steps.** While signed in, open `https://classroom.example.org/admin/passkey/settings`
and register a passkey. Then sign out and sign in with it.

**What you should see.** Your device asks for your fingerprint, face or PIN,
then shows your dashboard.

**If something looks wrong.** A passkey error usually means the
Passwordless.dev application's origin doesn't match `https://` + your CTH
hostname ([Part 1, 1.4](part-1-accounts-and-domain.md#14-create-the-passwordlessdev-keys)).
You can still sign in with your username and code.

## 6.5 Add a test student

**What you're doing.** Putting one made-up student on your class roster.

**Why.** A student can only claim a seat that's already on the roster. A
made-up name lets you test without touching a real student's data.

**Steps.** Follow [Adding students to the roster](https://github.com/timwonderer/classroom-token-hub/blob/main/docs/user-guides/features/teacher/classroom/class-setup.md#adding-students-to-the-roster)
with a made-up first and last name. Then copy the class **join code**
([Sharing the join code](https://github.com/timwonderer/classroom-token-hub/blob/main/docs/user-guides/features/teacher/classroom/class-setup.md#sharing-the-join-code)).

**What you should see.** The roster lists the test student as unclaimed.

**If something looks wrong.** Check that you're in the class you just
created; the class switcher is in the teacher sidebar.

## 6.6 Claim the student account

**What you're doing.** Acting as the student and claiming the seat.

**Why.** Claiming exercises the parts a teacher sign-up doesn't: the
student-setup Redis service, the claim checks and the PIN and passphrase setup.

**Steps.** In the **student** window, open `https://classroom.example.org/student/login`,
choose **First Time? Set Up Account**, and follow
[Log In and First-Time Setup](https://github.com/timwonderer/classroom-token-hub/blob/main/docs/user-guides/features/student/account/login-setup.md)
with the join code and the made-up name.

**What you should see.** The student dashboard. In the teacher window, the
roster now shows the seat as claimed.

**If something looks wrong.**

- **An "unavailable" error (HTTP 503) on the claim page:** see
  [Troubleshooting](troubleshooting.md#student-claim-returns-503).
- **The claim page can't find the student:** check the spelling against the roster and the join
  code. More help: [students can't claim](https://github.com/timwonderer/classroom-token-hub/blob/main/docs/user-guides/diagnostics/teacher/students.md).

## 6.7 Check health from the server

**What you're doing.** Confirming the server reports itself healthy now that
it has real use.

**Why.** You'll run these same checks after every change, so learn them now.

**Steps.** On the server, as root:

```bash
cd /root/cth-installer
manifest=/etc/cth/installation.json
python3 infra/self-hosting/install.py check readiness --config "$manifest"
curl -s http://127.0.0.1:8000/health
systemctl is-active cth-web.service cth-ingress.service cth-rate-limit.service cth-student-setup.service
```

**What you should see.** The readiness check ends in `"result": "ok"`, the
health check prints `ok`, and the last command prints `active` four times.

**If something looks wrong.** See the stage notes in [Part 5](part-5-install-stages.md)
and [Troubleshooting](troubleshooting.md).

## 6.8 Optional: a system administrator account

CTH also has a separate **system administrator** account for running the
installation as a whole, separate from any class. You don't need it
for teaching. If you want one, follow [First operator account](operations.md#first-operator-account)
in the operations reference.

## Before inviting students

Treat these as a checklist you complete, not a list to skim. Record a short
result next to each item. If one fails, keep working with the fictional class
until you understand the failure.

- Sign out of the test student account and sign back in with the saved
  credentials. A successful claim alone does not test the next login.
- Using only your fictional student, make one small manual payroll payment
  through the teacher payroll page. Confirm the amount appears once in the
  teacher history and the student account. If a request times out, check the
  history before submitting it again.
- Try the site on a student device and the school network. Confirm that
  Turnstile, sign-in and any passkey flow you plan to use work there.
- Check home, privacy, terms, support and status links. Some still point at
  the project's hosted services; they do not describe or monitor your server.
  See the [configuration limitations](configuration.md#conditional-features-and-runtime-defaults).
- Complete the backup and restore drill in Part 7. If you used Access to keep
  setup private, deliberately open it only when these checks are complete.

These are practical first-use checks, not proof of every classroom feature or
a completed independent installation rehearsal.

**Agent prompt for checking first use:**

```text
Walk me through Part 6 of docs/self-hosting one check at a time using my
fictional class. Keep teacher and student browser sessions separate. Have me
enter credentials privately. Record the observed result for signup, repeat
login, student claim, repeat student login and one manual payroll payment.
If a request times out, inspect history before proposing a retry. Report
untested checks as untested; a working health URL is only one check.
```

## Checkpoint

You can sign back into both accounts, and your fictional student's payment
appears once for the correct amount. Keep using practice data until the backup
and restore drill in Part 7 passes. You have a teacher account, a class and a claimed student. The rest of the teacher manual is at
[Teacher Manual](https://github.com/timwonderer/classroom-token-hub/blob/main/docs/user-guides/teacher_manual.md).

**Next:** [Part 7: Keep it running](part-7-keep-it-running.md). Set up backups
before real students join.
