// Developer documentation site for Classroom Token Hub.
//
// Serving boundary (mirrors app/routes/docs.py and app/utils/helpers.py):
// this site publishes the developer-facing documentation tree — INVARIANT,
// DOMAIN, FEATURE-EXECUTION, SPEC, STANDARD_OPERATING_PROCEDURES, MAP,
// PRINCIPLES, REFERENCE, TRACKING, ops, self-hosting. It deliberately does
// NOT publish docs/user-guides: the Flask application owns the in-app help
// centre and is the only place those are rendered.
//
// Content is read straight out of ../docs. There is no copied or mirrored
// second version of a normative document in this workspace.

function stripTrailingSlash(value) {
  return value.replace(/\/+$/, "");
}

const docsSiteUrl = stripTrailingSlash(
  process.env.DOCS_SITE_URL || "https://classroomtokenhub.com",
);
const appDocsOrigin = stripTrailingSlash(
  process.env.APP_DOCS_ORIGIN || "https://app.classroomtokenhub.com",
);
const baseUrl = process.env.DOCS_SITE_BASE_URL || "/docs/";

const repoUrl = "https://github.com/timwonderer/classroom-economy";

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: "Classroom Token Hub Developer Docs",
  tagline: "Invariants, domain contracts, and operating procedures",
  url: docsSiteUrl,
  baseUrl,
  favicon: undefined,
  future: {
    v4: true,
    faster: true,
  },
  organizationName: "timwonderer",
  projectName: "classroom-economy",
  trailingSlash: false,
  onBrokenLinks: "throw",
  onBrokenAnchors: "throw",
  markdown: {
    // The docs tree is hand-written CommonMark, not MDX. Parsing it as MDX
    // turns ordinary prose such as <seat_id> or {class_id} into a build error.
    format: "detect",
    hooks: {
      onBrokenMarkdownLinks: "throw",
    },
  },
  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },
  presets: [
    [
      "classic",
      {
        docs: {
          path: "../docs",
          routeBasePath: "/",
          include: ["**/*.md", "**/*.mdx"],
          exclude: [
            // Owned by the Flask app's /docs help centre.
            "user-guides/**",
            // Superseded v1 material — history only, never authority.
            "archive/**",
            "assets/**",
            // The repository-side index; this site has its own landing page.
            "README.md",
          ],
          sidebarPath: require.resolve("./sidebars.js"),
          editUrl: `${repoUrl}/tree/main/docs/`,
          showLastUpdateTime: true,
        },
        blog: {
          path: "blog",
          routeBasePath: "notes",
          blogTitle: "Engineering Notes",
          blogDescription:
            "Release notes, decision records, and migration write-ups",
          showReadingTime: true,
          editUrl: `${repoUrl}/tree/main/docs-site/`,
          onInlineAuthors: "ignore",
          onUntruncatedBlogPosts: "ignore",
        },
        theme: {
          customCss: require.resolve("./src/css/custom.css"),
        },
      },
    ],
  ],
  themeConfig: {
    colorMode: {
      // The design system defines one identity per role, all of them light
      // (SPEC-DES-001 §VI.4). A dark theme here would have to invent brand
      // values the system does not define, so the switch is off rather than
      // shipping colours that contradict §VI.4.
      defaultMode: "light",
      disableSwitch: true,
      respectPrefersColorScheme: false,
    },
    navbar: {
      title: "Classroom Token Hub",
      items: [
        {type: "docSidebar", sidebarId: "developer", label: "Developer Docs", position: "left"},
        {to: "/documents", label: "All documents", position: "left"},
        {to: "/REFERENCE/REF-TERM-001_DEVELOPER_VOCABULARY", label: "Glossary", position: "left"},
        {
          type: "dropdown",
          label: "Reference",
          position: "left",
          items: [
            {to: "/REFERENCE/REF-API-001_HTTP_INTERFACE_REFERENCE", label: "HTTP interface"},
            {to: "/STANDARD_OPERATING_PROCEDURES/SOP-DOC-001_DOCUMENTATION_INDEX", label: "Document index (SOP-DOC-001)"},
            {to: "/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP", label: "Template → FEAT wiring"},
            {to: "/MAP/MAP-UI-002_REQUEST_CONTEXT_AND_VIEW_MODEL_PIPELINE", label: "Request context and view models"},
            {to: "/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-001_Migration_Specifications", label: "Writing a migration"},
            {to: "/STANDARD_OPERATING_PROCEDURES/TESTING/SOP-TEST-003_Test_Creation", label: "Writing a test"},
            {to: "/self-hosting/", label: "Self-hosting"},
            {to: "/notes", label: "Engineering notes"},
          ],
        },
        {href: `${appDocsOrigin}/docs/`, label: "User Guides", position: "right"},
        {href: repoUrl, label: "GitHub", position: "right"},
      ],
    },
    footer: {
      style: "dark",
      links: [
        {
          title: "Documentation",
          items: [
            {label: "Start here", to: "/"},
            {label: "All documents", to: "/documents"},
            {label: "Developer glossary", to: "/REFERENCE/REF-TERM-001_DEVELOPER_VOCABULARY"},
            {label: "Core invariants", to: "/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS"},
            {label: "Engineering notes", to: "/notes"},
          ],
        },
        {
          title: "Product",
          items: [
            {label: "Classroom Token Hub", href: "https://classroomtokenhub.com/"},
            {label: "User guides (in-app)", href: `${appDocsOrigin}/docs/`},
          ],
        },
        {
          title: "Project",
          items: [
            {label: "Repository", href: repoUrl},
            {label: "Changelog", href: `${repoUrl}/blob/main/CHANGELOG.md`},
            {label: "Contributing", href: `${repoUrl}/blob/main/CONTRIBUTING.md`},
          ],
        },
      ],
      copyright: `Copyright ${new Date().getFullYear()} Classroom Token Hub — PolyForm Noncommercial 1.0.0`,
    },
    prism: {
      additionalLanguages: ["bash", "python", "sql", "json"],
    },
  },
};

module.exports = config;
