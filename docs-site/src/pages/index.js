import Heading from "@theme/Heading";
import Link from "@docusaurus/Link";
import Layout from "@theme/Layout";
import useDocusaurusContext from "@docusaurus/useDocusaurusContext";

const BRAND_ROWS = [
  ["local_atm", "CLASSROOM"],
  ["store", "TOKEN"],
  ["finance_mode", "HUB"],
];

const SECTIONS = [
  {
    label: "Invariants",
    to: "/category/invariants",
    tier: "Constitutional",
    body: "INV-CORE and INV-ARC. The rules nothing else may contradict, including the identity model.",
  },
  {
    label: "Domain Authority",
    to: "/category/domain-authority",
    tier: "Normative",
    body: "DOM-* specs. What each domain owns, and the contracts it exposes to everything else.",
  },
  {
    label: "Feature Execution",
    to: "/category/feature-execution",
    tier: "Normative",
    body: "FEAT contracts. Every state mutation in the application runs through one of these.",
  },
  {
    label: "Specifications",
    to: "/category/specifications",
    tier: "Normative",
    body: "SPEC-* technical contracts: testing, design system, temporal handling, build requirements.",
  },
  {
    label: "Operating Procedures",
    to: "/category/standard-operating-procedures",
    tier: "Normative",
    body: "SOP-* procedures for migrations, deployment, devops, and documentation.",
  },
  {
    label: "Reference & Principles",
    to: "/category/reference",
    tier: "Reference",
    body: "REF-* vocabulary and PRN-* rationale — why a given design was chosen.",
  },
];

// Entry points a developer reaches for by name rather than by browsing. Each
// one is a document that is current; a stale map is left to the tree.
const QUICK_LINKS = [
  ["All documents", "/documents", "Everything this site publishes, in one list"],
  ["Developer glossary", "/REFERENCE/REF-TERM-001_DEVELOPER_VOCABULARY", "Seat, class boundary, FEAT, canonical context"],
  ["HTTP interface", "/REFERENCE/REF-API-001_HTTP_INTERFACE_REFERENCE", "Routes, blueprints, and their contracts"],
  ["Writing a migration", "/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-001_Migration_Specifications", "Idempotency helpers, heads, rollback"],
  ["Writing a test", "/STANDARD_OPERATING_PROCEDURES/TESTING/SOP-TEST-003_Test_Creation", "Classroom initializer, scoping, mutation proofs"],
  ["Template → FEAT wiring", "/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP", "Which surface drives which contract"],
  ["Self-hosting", "/self-hosting/", "Running your own instance"],
  ["Engineering notes", "/notes", "Release notes and decision records"],
];

export default function Home() {
  const {siteConfig} = useDocusaurusContext();
  const appDocs = siteConfig.themeConfig.navbar.items.find(
    (item) => item.label === "User Guides",
  );

  return (
    <Layout
      title="Developer Documentation"
      description="Invariants, domain contracts, feature execution contracts, and operating procedures for Classroom Token Hub"
    >
      <header className="landing-hero">
        <div className="container landing-hero-grid">
          {/* The brand is the three-row text wordmark, never an image
              (SPEC-DES-001 §IX). Mirrors templates/macros/docs_hero.html. */}
          <div className="landing-brand">
            {BRAND_ROWS.map(([icon, word]) => (
              <div className="landing-brand-row" key={word}>
                <span className="material-symbols-outlined" aria-hidden="true">
                  {icon}
                </span>
                <span>{word}</span>
              </div>
            ))}
          </div>
          <div className="landing-welcome">
            <Heading as="h1">Developer documentation</Heading>
            <p>
              The documentation that governs the system: constitutional
              invariants, domain authority specs, feature execution contracts,
              and the procedures that keep the database and deployments honest.
            </p>
            <div className="hero__actions">
              <Link className="button button--primary button--lg" to="/category/invariants">
                Start with the invariants
              </Link>
              <Link className="button button--secondary button--lg" to="/REFERENCE/REF-TERM-001_DEVELOPER_VOCABULARY">
                Read the glossary
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="container margin-vert--xl">
        <section>
          <Heading as="h2">Authority flows downward</Heading>
          <p className="section-lede">
            <code>INV-CORE</code> → <code>INV-ARC</code> → <code>DOM</code> →{" "}
            <code>FEAT</code>. When a specification and the implementation
            disagree, the constitutional documents define the target state.
          </p>
          <div className="row">
            {SECTIONS.map((section) => (
              <div className="col col--4 margin-bottom--lg" key={section.label}>
                <Link className="card padding--lg section-card" to={section.to}>
                  <span className="section-card__tier">{section.tier}</span>
                  <Heading as="h3" className="section-card__title">
                    {section.label}
                  </Heading>
                  <p className="section-card__body">{section.body}</p>
                </Link>
              </div>
            ))}
          </div>
        </section>

        <section className="margin-top--lg">
          <Heading as="h2">Go straight there</Heading>
          <ul className="quick-links">
            {QUICK_LINKS.map(([label, to, blurb]) => (
              <li key={to}>
                <Link to={to}>{label}</Link>
                <span className="quick-links__blurb">{blurb}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="margin-top--lg">
          <div className="card padding--lg">
            <Heading as="h2">Looking for help using the app?</Heading>
            <p className="section-lede">
              Teacher and student guides are not published here. They are served
              inside the application, where they keep your session and the
              context of the page you came from.
            </p>
            {appDocs ? (
              <Link className="button button--secondary" href={appDocs.href}>
                Open the in-app help centre
              </Link>
            ) : null}
          </div>
        </section>
      </main>
    </Layout>
  );
}
