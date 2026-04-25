# Security Policy

## Supported Versions

Only use the latest release on `main`. The latest release will receive security fixes.

| Version | Supported |
| ------- | --------- |
| latest  | ✅        |
| older   | ❌        |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report vulnerabilities privately via [GitHub private vulnerability reporting](https://github.com/therogue/hakadorio-community/security/advisories/new).

Include as much detail as possible:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fix (optional)

## Response Timeline

| Milestone                        | Target     |
| -------------------------------- | ---------- |
| Acknowledgement                  | 3 days     |
| Initial assessment               | 7 days     |
| Fix or workaround                | 30 days    |
| Public disclosure (coordinated)  | After fix  |

We will keep you informed throughout the process. If you do not receive an acknowledgement within 3 days, follow up via [Hakadorio@discussions](https://github.com/therogue/hakadorio-community/discussions).


## Scope

**In scope:**

- Authentication or authorization flaws
- Injection vulnerabilities (SQL, command, etc.)
- Sensitive data exposure
- Dependency vulnerabilities with a credible exploit path

**Out of scope:**

- Automated scanner output without a credible exploit path
- Denial-of-service via resource exhaustion in a local dev environment
- Issues in unsupported versions

## Automated Scanning

Dependabot and CodeQL handle automated dependency and code scanning. This policy covers human-reported disclosures only.

