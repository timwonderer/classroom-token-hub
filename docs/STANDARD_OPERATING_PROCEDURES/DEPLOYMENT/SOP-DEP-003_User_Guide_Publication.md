# SOP-DEP-003: User Guide Publication

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DEP-003      | 1.0     | 2026-11-25     | —    | Normative |

## I. Purpose

Publish updated user guides to production without a formal application release. Production serves the user
guides from a separately published **documentation artifact**, with its own source revision and rollback,
alongside the application release. Publishing changes no code, template, database or process, so the release
ceremony of `SOP-DEP-002` does not apply. This document covers only what publication needs: eligibility,
authority, scope enforcement, compatibility, deployment, rollback and evidence. Everything else stays with
`SOP-DEP-002`.

## II. Scope

The production user guides: `docs/user-guides/` as served at `/docs/user-guides/`. Nothing else is eligible:
templates (including the docs index page), Python, JavaScript, CSS, deployment scripts, normative documents and
the public site all ship with an application release or their own deployment. Self-hosted installations that do
not set `CTH_USER_GUIDES_DIR` keep serving the guides bundled with their release.

## III. Authority Level

Normative (SOP Tier). Subordinate to INV-CORE-000. `SOP-DEP-002` §VII.A step 10a links here.

## IV. Dependencies

- `SOP-DEP-002`: formal releases, which publish their own guides before the gate reopens.
- `infra/release-gate/guarded-docs.sh` and `docs_publish.py`: the droplet-side enforcement, installed by hand.
- `.github/workflows/docs-deploy.yml`: the dispatch.

## V. Eligibility and authority

1. **Eligible change.** A commit on `main` whose `docs/user-guides/` tree contains only regular Markdown and
   image files.
2. **Compatibility with deployed behavior.** Every published guide describes the behavior of the application
   release **currently deployed**, never a feature merged to `main` but not yet released. This is the
   publisher's requirement to meet and attest to by dispatching. Mechanical screening (§VI.3) catches the
   common case but cannot establish it.
3. **Authority.** The owner, or an operator acting on the owner's instruction, dispatches publication. Merging
   a guide change does not publish it.

## VI. Scope enforcement

The droplet enforces each rule independently of the workflow, through `DOCS_DEPLOY_KEY`'s root-owned forced
command, which executes no client-supplied text:

1. The revision is 40 hex characters and an ancestor of `origin/main`.
2. The artifact contains only regular files under `docs/user-guides/` with an allowed suffix. Symlinks,
   submodules and any other file type are refused.
3. **Screening.** Every commit since the deployed application release that changed `docs/user-guides/`
   changed nothing else (`CHANGELOG.md` excepted). A guide changed together with code most likely describes
   code that is not deployed yet, so it waits for that release.
4. A publication and a formal release never run at once: both take the same droplet lock.

Rendering is unchanged: artifact guides pass through the same Markdown renderer and HTML sanitizer as guides
in the checkout, and path containment applies to the artifact root.

## VII. Deployment and rollback

1. **Publish.** Dispatch `docs-deploy.yml` with the commit's full SHA. The droplet extracts the guides to
   `/srv/cth-docs/releases/<sha>/`, then verifies every file's git blob hash against the commit, with nothing
   extra. It switches `/srv/cth-docs/current` atomically, so readers see the old or the new guides, never a
   mix. It then verifies again that the switched tree is the commit's and that the running application serves
   guides from `/srv/cth-docs/current/docs`. No maintenance gate, backup or restart is needed.
2. **Roll back.** Publish the earlier revision the same way. Earlier artifacts remain on the droplet until
   removed by hand.
3. **With a formal release.** A release changes behavior, so it publishes its own guides (its release SHA)
   **before** the gate reopens (`SOP-DEP-002` §VII.A step 10a). Rolling back an application release also
   publishes the guides of the release rolled back to.

## VIII. Evidence

The `docs-deploy.yml` run is the record. Its summary names:
- the requested and previously published docs revisions;
- the deployed application release at publication;
- the root the application serves guides from;
- the changed guide files.

The droplet keeps `SOURCE` with each artifact. The next formal release record lists the docs revisions
published since the previous release (`SOP-DEP-002` §VII.A step 12). No separate record file is written.

## IX. One-time setup

Owner actions on the droplet, in `infra/release-gate/README.md` (*Documentation publication*):
- the key and its forced-command line;
- the two installed files;
- `/srv/cth-docs`;
- the `DOCS_DEPLOY_KEY` repository secret;
- a two-pass first publication: publish (which creates `/srv/cth-docs/current`), set
  `CTH_USER_GUIDES_DIR=/srv/cth-docs/current/docs` for the service, restart, then publish again to verify.

Until then, guides ship with application releases.

## X. Amendment

Revisions require incrementing the version, updating the Effective Date, and populating the Supersedes field.

### Revision History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-11-25 | Established (owner ruling 2026-11-25): user guides as a separately published documentation artifact. |
