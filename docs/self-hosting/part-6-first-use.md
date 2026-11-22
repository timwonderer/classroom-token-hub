---
title: "Part 6: First use"
category: self-hosting
description: Create your teacher account and class, claim a test student account, check health and open the site to students.
roles: [operator]
keywords: [self-hosting, tutorial, teacher signup, TOTP, student claim, health, Cloudflare Access]
---

# Part 6: First use

Your CTH is running behind the Access gate. Now use it the way a teacher and a
student will, before any real student sees it.

Throughout this part, `classroom.example.org` stands for your CTH hostname.

The teacher and student help pages linked below are also built into your own
CTH, under `https://classroom.example.org/docs/user-guides/`.

## 6.1 Get ready

**What you're doing.** Setting up a teacher browser and a separate student
browser.

**Why.** Teacher and student sessions must not share a browser. Using a
separate window for the student shows you exactly what a student sees.

**Steps.**

1. Install an authenticator app on your phone if you haven't
   ([Before you begin](before-you-begin.md#required-by-the-current-release)).
2. Use your normal browser window as the **teacher**.
3. Use a private window, or a different browser, as the **student**.

While the whole site is behind Access, both windows ask for your email code
first. Use your own email in both.

**What you should see.** Both windows reach the Access page.

**If something looks wrong.** If a window skips the Access page, it's
reusing an earlier sign-in. That's fine.

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

**Why.** Passkeys can't be phished, and you won't need to type codes every
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

## 6.9 Open the site to your students

**What you're doing.** Letting students reach the student pages without an
Access code, while keeping teacher pages behind Access.

**Why.** Students don't have an approved email in your Access policy, so they
can't get past the gate. But the teacher pages should stay behind it: Access
stops strangers from even reaching your teacher sign-in or sign-up, and the
installer's `ingress` and `readiness` checks expect `/admin/login` to stay
gated.

> [!WARNING]
> Don't delete the Access application. Without it, anyone on the internet can
> reach your teacher sign-up page, and `check readiness` fails. A setup
> without Access isn't supported yet ([#1792](https://github.com/timwonderer/classroom-token-hub/issues/1792)).

**Steps** *(Cloudflare Zero Trust)*. Edit the "CTH" Access application you
created in [Part 2, 2.6](part-2-create-the-server.md#26-put-cloudflare-access-in-front-of-the-site):

1. Change its destination from the whole hostname to the path `admin` on your
   CTH hostname (`classroom.example.org/admin`).
2. Add a second destination for the path `sysadmin` (`classroom.example.org/sysadmin`).
3. Keep the policy: only your email, plus any other teachers you invite to
   your server.

Then tell students to go to `https://classroom.example.org/student/login`.
By default, the site's home page and its privacy and terms links point to the
project's public site, so give students the full `/student/login` address.

**What you should see.** In a fresh private window,
`https://classroom.example.org/student/login` opens without an Access page,
while `https://classroom.example.org/admin/login` still asks for an email code.
On the server, `check readiness` still ends in `"result": "ok"`.

**If something looks wrong.**

- **Students still see the Access page:** the application still covers the
  whole hostname. Check its destinations.
- **`/admin/login` opens without Access, or readiness fails with
  `unauthenticated public login did not reach the selected admission gate`:**
  the `admin` path isn't covered. Fix the destination before anyone else
  visits.

*Alternative:* if every student has a school email address, you can instead
leave the whole site gated and add those addresses to the Access policy.
Students then enter an email code before every new sign-in. Check your
Cloudflare plan's user limit first.

## Checkpoint

You have a teacher account, a class, a claimed student, and a site students
can reach. The rest of the teacher manual is at
[Teacher Manual](https://github.com/timwonderer/classroom-token-hub/blob/main/docs/user-guides/teacher_manual.md).

**Next:** [Part 7: Keep it running](part-7-keep-it-running.md). Set up backups
before real students join.
