const routeMap = require("./route-map.json");

function stripTrailingSlash(value) {
  return value.replace(/\/+$/, "");
}

const docsSiteUrl = stripTrailingSlash(
  process.env.DOCS_SITE_URL || "http://127.0.0.1:3000",
);
const appDocsOrigin = stripTrailingSlash(
  process.env.APP_DOCS_ORIGIN || "http://127.0.0.1:5000",
);
const publicRedirects = Object.entries(routeMap).map(([from, to]) => ({
  from: `/${from}`,
  to,
}));

// Docusaurus config for the external docs/blog site.
// Route base path stays at the site root for migrated public docs.
// Flask only redirects the subset of /docs paths that exist in route-map.json.

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: "Classroom Token Hub",
  tagline: "Internal v2 docs preview",
  url: docsSiteUrl,
  baseUrl: "/",
  future: {
    v4: true,
    faster: true,
  },
  organizationName: "timwonderer",
  projectName: "classroom-economy",
  onBrokenLinks: "throw",
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: "warn",
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
          routeBasePath: "/",
          sidebarPath: require.resolve("./sidebars.js"),
          editUrl: "https://github.com/timwonderer/classroom-economy/tree/main/docs-site/",
        },
        blog: {
          showReadingTime: true,
          editUrl: "https://github.com/timwonderer/classroom-economy/tree/main/docs-site/",
        },
        theme: {
          customCss: require.resolve("./src/css/custom.css"),
        },
      },
    ],
  ],
  plugins: [
    [
      "@docusaurus/plugin-client-redirects",
      {
        redirects: publicRedirects,
      },
    ],
  ],
  themeConfig: {
    navbar: {
      title: "Classroom Token Hub",
      items: [
        {to: "/overview", label: "Preview", position: "left"},
        {to: "/blog", label: "Notes", position: "left"},
        {
          href: "https://github.com/timwonderer/classroom-economy",
          label: "GitHub",
          position: "right",
        },
      ],
    },
    footer: {
      style: "dark",
      links: [
        {
          title: "Preview",
          items: [
            {label: "Overview", to: "/overview"},
            {label: "Migration Plan", to: "/technical/migration-plan"},
          ],
        },
        {
          title: "Project",
          items: [
            {
              label: "Repository",
              href: "https://github.com/timwonderer/classroom-economy",
            },
            {
              label: "Flask Docs",
              href: `${appDocsOrigin}/docs/`,
            },
          ],
        },
      ],
      copyright: `Copyright ${new Date().getFullYear()} Classroom Token Hub`,
    },
  },
};

module.exports = config;
