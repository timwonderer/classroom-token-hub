# Security Policy

Classroom Token Hub (CTH) takes security and privacy reports seriously.

CTH is classroom software and may be used by students. If you believe you have
found a security vulnerability, please report it responsibly and avoid accessing,
collecting, modifying, or retaining data beyond what is necessary to demonstrate
the issue.

## Reporting a Vulnerability

> [!CAUTION]
> Please do not report security vulnerabilities through a public GitHub issue.

Use GitHub's private vulnerability reporting feature for this repository:

Security → Advisories → Report a vulnerability

When possible, include:

- a clear description of the issue
- the affected component or route
- steps necessary to reproduce the behavior
- the security impact you believe is possible
- the CTH version, commit, or deployment involved
- minimal supporting evidence necessary to reproduce the issue

> [!WARNING]
> Do not include student names, credentials, authentication secrets, or other
personally identifiable information in the report. 

## Responsible Testing

Security research must remain within accounts, classes, and data you are
authorized to use.

Please do not:

- access another user's account or class without authorization
- obtain or retain student personally identifiable information
- modify or delete data belonging to other users
- attempt denial-of-service or resource-exhaustion attacks
- use automated scanning that could materially disrupt the service
- perform social engineering against students, teachers, or other users
- publish an unresolved vulnerability before coordinated disclosure

If you unexpectedly gain access to data or privileges outside your authorized
scope, stop testing that path and report what occurred. 

> [!CAUTION]
> Certain data processed by the platform may constitute education records protected under the Family Educational Rights and Privacy Act (FERPA). Accessing education records without authorization, or accessing more information than is necessary to demonstrate a vulnerability, may have legal consequences.

## What We Consider Security Issues

Examples include:

- authentication or session bypass
- unauthorized access across class boundaries
- privilege escalation
- exposure of personally identifiable information
- unauthorized financial or ledger mutation
- bypass of authorization or capability checks
- secret or credential exposure
- injection vulnerabilities
- vulnerabilities allowing execution of unauthorized actions

Ordinary application bugs, incorrect calculations, accessibility issues, and
feature requests should use the normal project issue or support process unless
they create a security boundary violation.

## What Happens After a Report

Reports will be reviewed and triaged based on severity and reproducibility.

When a vulnerability is confirmed, the project may:

1. reproduce and contain the issue
2. develop and validate a fix
3. deploy or release the correction
4. monitor for recurrence
5. publish a security advisory when appropriate

We may request additional information when it is necessary to reproduce the
reported behavior.

## Disclosure

Please allow reasonable time for investigation, remediation, and deployment
before publicly disclosing an unresolved vulnerability.

After remediation, coordinated public disclosure is welcome.

## Supported Versions

CTH is currently under active development.

Security fixes are provided for the current supported release and active
development version. Older or superseded versions may not receive security
updates.

## Good-Faith Research

Good-faith security research that follows this policy is welcomed.

This policy does not authorize testing against infrastructure, accounts,
networks, or systems that are not owned or controlled by the CTH project.
