import clsx from "clsx";
import Heading from "@theme/Heading";
import Link from "@docusaurus/Link";
import Layout from "@theme/Layout";

export default function Home() {
  return (
    <Layout
      title="Classroom Token Hub"
      description="Public documentation, release storytelling, and technical reference"
    >
      <header className="hero hero--primary">
        <div className="container">
          <Heading as="h1" className="hero__title">
            Classroom Token Hub Docs
          </Heading>
          <p className="hero__subtitle">
            Public docs and blog publishing now live outside the Flask app.
          </p>
          <div className={clsx("margin-top--md")}>
            <Link className="button button--secondary button--lg" to="/overview">
              Read the docs
            </Link>
          </div>
        </div>
      </header>
    </Layout>
  );
}
