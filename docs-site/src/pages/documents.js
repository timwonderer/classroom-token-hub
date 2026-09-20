import Heading from "@theme/Heading";
import Link from "@docusaurus/Link";
import Layout from "@theme/Layout";
import {useAllDocsData} from "@docusaurus/plugin-content-docs/client";

// Generated from the docs plugin's own routing data, so it lists exactly what
// this site publishes and cannot fall behind the tree the way a hand-kept
// index does. SOP-DOC-001 remains the repository's canonical index of record.

const GROUPS = [
  ["INVARIANT", "Invariants", "Constitutional. INV-CORE is foundational, INV-ARC governs architecture."],
  ["DOMAIN", "Domain authority", "What each domain owns and the contracts it exposes."],
  ["FEATURE-EXECUTION", "Feature execution", "The contract behind every state mutation."],
  ["SPEC", "Specifications", "Technical contracts: testing, design system, time, build requirements."],
  ["STANDARD_OPERATING_PROCEDURES", "Operating procedures", "How to change the database, deploy, test, and write docs."],
  ["MAP", "Interface maps", "Domain-to-FEAT capability and UI wiring maps."],
  ["REFERENCE", "Reference", "Vocabulary and interface references."],
  ["PRINCIPLES", "Principles", "Why a design was chosen. Informative."],
  ["ops", "Operations", "Operational notes, audits, and evidence."],
  ["self-hosting", "Self-hosting", "Running your own instance."],
  ["TRACKING", "Tracking", "Readiness and migration status. Descriptive, never authoritative."],
];

// FEAT-CLASS-001_CREATING_NEW_CLASS_BOUNDARY -> "FEAT-CLASS-001 · Creating new class boundary"
function label(id) {
  const name = id.split("/").pop();
  const match = name.match(/^((?:INV|DOM|FEAT|SPEC|SOP|MAP|REF|PRN)-[A-Z]+-\d+[A-Z]?)[_ ](.*)$/);
  const words = (rest) =>
    rest.replace(/[_-]+/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase());
  return match ? `${match[1]} · ${words(match[2])}` : words(name);
}

export default function Documents() {
  const docs = Object.values(useAllDocsData())[0].versions[0].docs;

  const grouped = GROUPS.map(([prefix, title, blurb]) => [
    title,
    blurb,
    docs
      .filter((doc) => doc.id.startsWith(`${prefix}/`) || doc.id === prefix)
      .sort((a, b) => a.id.localeCompare(b.id)),
  ]).filter(([, , items]) => items.length > 0);

  const total = grouped.reduce((sum, [, , items]) => sum + items.length, 0);

  return (
    <Layout
      title="All documents"
      description="Every document published by the Classroom Token Hub developer documentation site"
    >
      <main className="container margin-vert--xl">
        <Heading as="h1">All documents</Heading>
        <p className="section-lede">
          Every one of the {total} documents this site publishes, generated from
          the site's own routing data. The repository's canonical index of
          record is{" "}
          <Link to="/STANDARD_OPERATING_PROCEDURES/SOP-DOC-001_DOCUMENTATION_INDEX">
            SOP-DOC-001
          </Link>
          ; this page is navigation, not authority. Teacher and student guides
          are not listed here — the application serves those.
        </p>

        {grouped.map(([title, blurb, items]) => (
          <section key={title} className="margin-top--lg">
            <Heading as="h2" id={title.toLowerCase().replace(/\s+/g, "-")}>
              {title}
            </Heading>
            <p className="section-lede">{blurb}</p>
            <ul className="document-index">
              {items.map((doc) => (
                <li key={doc.id}>
                  <Link to={doc.path}>{label(doc.id)}</Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </main>
    </Layout>
  );
}
