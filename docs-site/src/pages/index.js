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
    label: "Invariants (INV-*)",
    to: "/category/invariants",
    tier: "Constitutional/Normative",
    body: "Core Invariants and Architectural Invariants of Classroom Token Hub. These are the foundational rules that must be followed by all developers",
  },
  {
    label: "Domain (DOM-*)",
    to: "/category/domain-authority",
    tier: "Normative",
    body: "Domains are specific and well-defined features of Classroom Token Hub (e.g. Class Configuration, Identity, etc.). Each domain define the type of data it should own, the invariants that must be maintained, and the authority it has over its data.",
  },
  {
    label: "Feature-Execution (FEAT-*)",
    to: "/category/feature-execution",
    tier: "Normative",
    body: "FEATs are owned by a single domain and are the sole authority for the execution of any mutation that affects the domain. They are the only source of truth for how a feature should behave and are responsible for ensuring that the feature is implemented correctly.",
  },
  {
    label: "Specifications (SPEC-*)",
    to: "/category/specifications",
    tier: "Normative",
    body: "SPEC documents the specific design of a feature or hardware. SPEC documents derive its authority from the corresponding domain that owns the feature. SPEC defines how a feature should be presented, how its transition looks like, and how it should be implemented.",
  },
  {
    label: "Operating Procedures (SOP-*)",
    to: "/category/standard-operating-procedures",
    tier: "Normative",
    body: "SOPs are the standard operating procedures for the development and maintenance of Classroom Token Hub. They define the processes and best practices that must be followed by all developers to ensure that the system is maintainable, scalable, and secure.",
  },
  {
    label: "Reference & Principles (REF-*, PRN-*)",
    to: "/category/reference",
    tier: "Informative",
    body: "Reference documents provide additional information and context for developers. They include glossaries, API references, and other supporting materials that help developers understand the system and its components.",
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
              Welcome! Discover the underlying structure of Classroom Token Hub and why we build it that way.
            </p>
            <div className="hero__actions">
              <Link className="button button--primary button--lg" to="/category/invariants">
                Start here: Read the Invariants
              </Link>
              <Link className="button button--secondary button--lg" to="/REFERENCE/REF-TERM-001_DEVELOPER_VOCABULARY">
                Project Glossary
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="container margin-vert--xl">
        <section>
          <Heading as="h2">How to navigate the documentation</Heading>
          <p className="section-lede">
            Classroom Token Hub has a strict documentation hierarchy structure to ensure all layers of specification and guardrails are coherent and consistent. The following sections are organized by their level of authority and purpose, from the most foundational rules to informative references.
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
