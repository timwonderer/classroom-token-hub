# Docs Site Workspace

This directory hosts a local-only internal preview site for Classroom Token Hub v2 docs work.

## Why It Exists

The Flask app still owns contextual in-product help, but this Docusaurus workspace gives us a safer place to preview a small subset of v2 docs and routing ideas without treating them as canonical.

This is not a public site. The intended usage is local development against a dev server. Until the v2 docs rework is complete, only the routes listed in `route-map.json` should be treated as intentionally handed off from Flask.

## Local Development

Requirements:

- Node.js 20 or newer
- npm or another compatible package manager

Commands:

```bash
cd docs-site
npm install
npm run start
```

## Routing Assumption

The Docusaurus docs plugin is mounted at the site root, but Flask only redirects the subset of public routes listed in `route-map.json`.
The Docusaurus docs plugin is mounted at the site root, but Flask only redirects the subset of preview routes listed in `route-map.json`.

That lets the migration move incrementally instead of breaking unmigrated docs.

Mapped preview requests can move from:

```text
/docs/<path>
```

to:

```text
https://docs.example.com/<mapped-path>
```

The preview site also uses Docusaurus client redirects for those legacy aliases.
