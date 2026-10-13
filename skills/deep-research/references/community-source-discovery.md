# Community Source Discovery and Access

Use this reference whenever a question may depend on lived experience, hidden
resources, niche communities, practitioner knowledge, cohort behaviour, or industry
pain points.

## 1. Let the LLM choose sources

Do not classify the query into one exclusive category. Read the complete question and
reason about:

- who experiences the problem;
- who administers, regulates, teaches, sells, repairs, researches, or complains about it;
- which region and language those people use;
- whether the useful evidence is a rule, dataset, full discussion, attachment, review,
  interview report, case history, or current operational signal;
- which neighbouring fields may use different words for the same problem.

List every website or source that may contain useful or unexpected information. Do not
exclude a source because it belongs to another category or because relevance is
uncertain. The question can use many unrelated-looking sources at once.

## 2. Consult the capability registry

Read `~/MyGithub/ai-research-engine/community-sources.json`. It records:

- topics, regions, languages, and evidence types commonly found at each source;
- verified discovery, search, and full-content routes;
- whether public access, a browser session, or an account is needed;
- route health and known access failures;
- sampling and community biases.

The registry is a phonebook for the LLM, not a classifier. It stores what each source
contains, its access recipe, and a credential reference when one exists. The LLM may add
unregistered sources when the question suggests them.

```bash
python3 ~/MyGithub/ai-research-engine/social-research.py source-list
```

## 3. Keep Nicole in the loop

Before collection, show two short lists:

- **Proposed:** sources the LLM plans to search, with one-line reasons.
- **Not proposed / optional:** known unused sources, so Nicole can add one the LLM missed.

Nicole may add, remove, or require any source. After collection, show what was actually
used and unused, and distinguish `EMPTY`, `FAILED`, and `SKIPPED`.

## 4. Search the selected sources

For each source:

1. Load its access recipe and credential reference from the phonebook.
2. Use an existing authenticated session or read the credential from its secret store.
3. Search through the source's first-party API.
4. Expand the useful full thread, replies, attachments, records, or dataset.
5. Use a bounded browser-page route only when no usable API exists.

Never put a password, token, cookie, recovery code, or secret in the repository or tool
output. Never export browser cookies.

## 5. Discover unknown communities

When the registry does not cover the likely information holders, vary discovery across:

- exact terms, synonyms, acronyms, local-language terms, older names, and adverse terms;
- `forum`, `community`, `discussion`, `board`, `subreddit`, `Discord`, `Slack`, `群`,
  `论坛`, `真题`, `经验`, `避雷`, and the corresponding local-language vocabulary;
- professional associations, student groups, worker communities, diaspora groups,
  vendor/user communities, complaint boards, technical issue trackers, and archives;
- people trails, cited links, attachment hosts, and communities named inside useful
  posts.

Search engines are discovery tools here, not the final evidence source. Open the actual
community and read the full thread, reply tree, linked files, dates, and context.

## 6. Choose the least invasive reliable route

Use this order:

1. Official/public API or JSON endpoint.
2. First-party API inside an existing logged-in Agent Chrome session.
3. Public page through browser transport when anti-bot controls block plain HTTP.
4. Bounded DOM extraction for the identified page only.
5. Account creation only when it unlocks materially unique evidence unavailable by the
   routes above.

Do not broad-crawl a site merely because a browser session exists. Respect pagination,
rate limits, community rules, and access controls. Never export browser cookies.

## 7. Account onboarding gate

Before registering, record:

- the exact evidence unavailable through public routes;
- why that evidence is material to the current or reusable research coverage;
- registration requirements and whether Nicole is eligible;
- whether email verification, MFA, CAPTCHA, a verified employer/school identity, paid
  membership, or acceptance of special terms is required.

Do not register when public search and full content already work. Never invent employer,
school, residency, or identity details to satisfy a gate. Pause for Nicole when the site
requires CAPTCHA, MFA, identity choice, payment, or personal factual input.

When a generated credential is genuinely required, store it in `gopass`; never put a
password, token, cookie, recovery code, or secret in the repository or command output.
The registry may store only the secret's reference path, never the secret value.

Suggested path:

```text
research-engine/community/<source-id>
```

## 8. Report route results

For each probe:

- `MATERIAL` — open the full content and expand related terms/sources.
- `EMPTY` — route worked but returned no relevant evidence.
- `FAILED` — access/tool/parse/rate-limit failure; never interpret as no discussion.
- `SKIPPED` — not attempted, with the reason.

If a source produces signal, follow its vocabulary, linked communities, attachments,
named people, and primary sources. Preserve every attempted canonical query and route in
the coverage ledger so unchanged retrievals are not repeated without reason.

## 9. Verify what community evidence can prove

Community material can establish that a stated experience, practice, workaround, or pain
point exists. It rarely establishes prevalence, official policy, legal effect, or a
population rate by itself. Verify consequential claims using current first-party,
official, administrative, or reproducible data while preserving conflicting community
evidence rather than silently merging it.
