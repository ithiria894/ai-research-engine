# GEO / AEO Skills（本地 reference，唔 install）

呢度啲 skill 係 **download 落本地做 reference**，唔係 `npx skills add` 裝（install = 每 session load 落 context 嘥 token）。要做 GEO 工作先 `Read skills/geo/<skill>/SKILL.md`，零 per-session 開銷。

## 來源 + License

| Skills | 來源 repo | License |
|--------|-----------|---------|
| geo-content-optimizer · schema-markup-generator · entity-optimizer · content-quality-auditor · domain-authority-auditor · competitor-analysis · content-gap-analysis · serp-analysis · on-page-seo-auditor · technical-seo-checker | [aaron-he-zhu/seo-geo-claude-skills](https://github.com/aaron-he-zhu/seo-geo-claude-skills) | Apache-2.0 |
| ai-seo | [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | MIT |

## 揀選原則

- **Keep**：純 methodology，靠你 fetch 嘅 data 行，無 live SEO-tool 依賴。
- **Drop**：要 live analytics/rank/backlink data（rank-tracker、performance-reporter、backlink-analyzer）、ops（alert-manager）、純 content-doer（copywriting、seo-content-writer）、或同 Nicole 自己 memory 系統撞（memory-management）。
- Vendored 時 strip 走每個 repo 自己嘅 governance junk（`_references/` ADR/evolution/proposal）同 `evals/`（作者 test case）。

詳情見 `research-engine.md` 嘅 GEO cluster section。
