---
title: Attribution & Project Philosophy
roles: [teacher, student]
description: Project principles, ethical stance, and acknowledgments
category: legal
keywords: [attribution, philosophy, ethics, privacy, transparency, open source]
searchable: true
related:
  - user-guides/legal/license
  - user-guides/legal/commercial
  - user-guides/legal/third-party-notices
---

# Attribution & Project Philosophy

This project exists to provide teachers with a **complete, inspectable, and ethical classroom economy system**.

It is built on the work of many open-source contributors and services, whose efforts are acknowledged with respect and care.

---

## I. Purpose

**Classroom Token Hub** was created to fill a gap in educational technology: a free, transparent, and privacy-respecting platform for teaching financial literacy through hands-on classroom banking simulations.

The intent of this project is **educational, not extractive**.

- **Use is encouraged** for learning and teaching
- **Monetization of the software itself is not permitted**
- **Transparency, minimal data collection, and teacher autonomy** are core design principles

---

## Design Principles

### 1. Educational First

This platform is designed for classrooms, not commerce. Every feature prioritizes the learning experience and teacher control over profit or scale.

### 2. Privacy & Security

- **Student data is encrypted at rest** - All personally identifiable information (PII) is protected
- **Post-claim PII minimisation** - Name-based claim verification artifacts are used only for seat claim and are minimized after setup, reducing the long-term sensitive-data footprint
- **Minimal data collection** - We only collect what's necessary for the classroom economy simulation
- **No tracking or analytics** - No third-party analytics or advertising
- **Teacher ownership** - Teachers control their data and can export or delete it at any time
- **Continuously audited** - Regular security audits of critical paths (deletion flows, multi-tenancy scoping, authentication) with documented findings and fixes

### 3. Transparency

- **Open source, as CTH defines it** - The source is available for inspection, and the project's
  philosophy is described in [PRN-PHL-002](../../PRINCIPLES/PROJECT_PHILOSOPHY/PRN-PHL-002_Classroom_Token_Hub_Open_Source_Philosophy.md).
  This is CTH's own definition; it does not claim OSI approval or certification.
- **Published license** - PolyForm Noncommercial License 1.0.0 sets the current baseline terms.
  The project's use of “open source” does not expand the rights that license grants.
- **Documented architecture** - Technical documentation explains how the system works
- **No hidden features** - What you see is what you get

### 4. Accessibility

- **Free to use** - No cost for educators or students
- **Simple deployment** - Can be self-hosted or deployed by schools
- **Comprehensive documentation** - User guides and technical references included
- **Community support** - Open to contributions and improvements

---

## Acknowledgments

This project stands on the shoulders of giants. We gratefully acknowledge:

### Open Source Communities

The Python, Flask, PostgreSQL, and broader open-source communities whose tools and libraries make this platform possible. See [Third-Party Notices](third-party-notices.md) for specific attributions.

### Educators

Teachers who provided feedback, feature requests, and real-world insights that shaped this platform into a practical classroom tool.

### Contributors

All contributors who have submitted code, documentation, bug reports, and suggestions to improve the platform.

---

## Ethical Stance

### Against Extraction

We reject business models that:

- Extract value from educators through subscription fees
- Lock essential features behind paywalls
- Monetize student data through advertising or analytics
- Create vendor lock-in through proprietary formats

### For Empowerment

We believe in:

- **Teacher autonomy** - Educators should control their tools and data
- **Student privacy** - Young people deserve protection, not profiling
- **Community ownership** - Educational tools should belong to education, not shareholders
- **Sustainable sharing** - Open source licenses preserve freedom while preventing exploitation

---

## Commercial Services vs. Software Monetization

The project intends to permit commercial providers to charge for actual services around CTH,
such as hosting, support, and deployment, while keeping CTH software and its standard features
outside paid software entitlements. This is a project objective, not a permission currently
granted by PolyForm Noncommercial 1.0.0. No additional commercial-services permission is
effective unless and until a separate instrument is published with an effective date.

See [Commercial Use Policy](commercial.md) for the complete commercial use policy.

The intended distinction is:

- **Services** involve labor or infrastructure for which providers may charge under the
  proposed permission
- **Software rights and features** would not become paid entitlements under that proposal

---

## License Rationale

CTH currently publishes the **PolyForm Noncommercial License 1.0.0** as its baseline license.
Its text permits the purposes it specifies and does not itself grant the proposed permission
for paid commercial hosting or support. CTH's separate objective is to permit qualifying
service providers to charge for actual services, without charging for CTH software rights or
features. That objective remains subject to project licensing review.

See [License](license.md) for the published license text and [Commercial Use Policy](commercial.md)
for the status of the proposed services permission.

---

## Contributing Back

If you use this project, we encourage you to:

- **Report bugs** - Help us improve the platform for everyone
- **Suggest features** - Share ideas from your classroom experience
- **Contribute code** - Bug fixes and improvements are always welcome
- **Share documentation** - Help other educators understand and use the platform
- **Respect the license** - Use the software ethically and legally

See the [Contributing Guide](https://github.com/timwonderer/classroom-token-hub/blob/main/.github/CONTRIBUTING.md) for contribution guidelines.

---

## Contact

For questions about licensing, commercial use, or the project philosophy:

- **GitHub Issues:** For technical questions and bug reports
- **Security:** Report security vulnerabilities privately to project maintainers
- **Commercial Inquiries:** Contact the project maintainer for clarification on permitted uses

---

**This project is a labor of love for educators and students.**

**Use it freely. Share it widely. Keep it open.**

---

**Last Updated:** 2026-02-25
