# Scout — Build Spec v0.4 (for Grok)

Nov 19, 2026 · @Jeremy

## Status

Scout's doctrine stays frozen at v0.3 (Grok round 3, Sept 16). This version adds only the build layer that Amp, Reverb and Warp have taught us since, and it reopens no frozen ruling. The frozen text is [Scout Spec v0.3](https://claude.ai/artifact/FxUsytmQ22LX5RtLwR94aL); this doc is what gets built from it.

| Item | State on Nov 19 |
| --- | --- |
| Doctrine, evidence standard, motive set, source list, budgets | Frozen at v0.3. Carried below in short form |
| S0 ledger (five rows, F-2026-38-001 to 005) | Written Sept 16. All five resolve dates have passed (Sept 20 to Oct 31). No resolution is on record. See Open calls, item 1 |
| S1 container | Not built. The Oct 5 target went to Amp, Reverb and Warp |
| Consumers | Hopper: spec only. Amp: live at v0.17. Reverb: live, Mixpost retired. Warp: live on QA and prod |

What v0.4 adds:

- A small web page on the shared shell, so rulings and findings have a home besides the Sunday email.
- A QA and prod pair with the same deploy, backup, health and alert pieces Amp and Reverb run on.
- Probes before any page: each outside dependency is proven live by a hand-run script first.
- One written contract with Hopper, identical in both specs.
- Slices rebased to today, in bigger batches.

Four renames that Grok should confirm are not doctrine changes:

1. Phrase-bank source "Mixpost text" becomes "Reverb post text". Same data; Mixpost's history was imported into Reverb Nov 7 to 9.
2. "Forge Ads Learn copy rows" and "Forge Ads vocab" become Amp copy rows and Amp vocab.
3. "Inspiration engine" becomes Hopper.
4. Operator rulings (term kind, motive, operator-resolved forecasts) are written on a Rulings page instead of by replying to the digest.

## Doctrine and refuse lines

Scout observes, scores and proposes; it never acts and never edits another tool's data. The nine lines below are v0.3's, shortened. The tenth is new and is the page footer.

1. **No thresholds, tags or thesis edits of its own.** A finding becomes an Amp tag, a Watchtower instrument or a thesis layer only when the operator writes it there.
2. **Every claim carries evidence:** source, metric, baseline, delta, breadth. A finding with no evidence row is refused by the digest and the page.
3. **Every forecast is dated, binary, resolvable and scored.** Its resolver is frozen at creation. Unscored forecasts expire; they never roll forward.
4. **Courier outputs are shown, not averaged.** Claude and Grok disagree in the open and the ledger records who was right.
5. **Budget-capped.** Each paid source has a monthly ceiling in config. A hit cap degrades to free sources and pages the operator; the run continues.
6. **Nothing personal leaves the Forge.** Couriers never see household figures or customer data.
7. **Not a scraper.** Phrase banks come only from the allowed-source list. No platform-comment adapter exists in the tree. This is the S1 refuse line, encoded as ledger row F-2026-38-005.
8. **The local model proposes, the operator writes.** Term kind and motive are suggested with quotes and confirmed by a person.
9. **Own data confirms, never discovers.** It never proposes a term and never counts toward breadth.
10. **Footer line (new, wording is an open call):** "Scout reads widely, proposes, and keeps score. A person rules."

Build-layer refusals added in v0.4, each learned the hard way on Amp or Reverb:

- Scout never reads another tool's live SQLite file. It reads that tool's read-only API, or a read-only copy.
- QA never spends on paid sources. QA replays recorded pulls; only prod calls SerpApi or a courier.
- A model response that fails its schema is retried once, then refused and logged. It is never repaired by hand-parsing.
- An export is written whole to a temp file and renamed. A consumer never reads half a file.

## Where Scout sits

Scout is the discovery layer: it answers "what is emerging that we have not named yet?" and hands the answer to tools that already have a person deciding.

&#91;embedded content: Scout's neighbours: four sources in, three readers out\]

Every arrow on the right ends at a person. Hopper's team votes, the operator adds a tag in Amp, the operator rules on the page. Bugs and ideas about Scout itself go to Warp through the shell's feedback widget; findings never do. Watchtower, Oracle and Radar join with the Life lane and are left off this picture.

## Pipeline

A term is proposed, observed, scored into a tier, and only then written up as a finding with forecasts attached. Every number in this section is frozen v0.3.

1. **Propose.** Proposers run in a fixed order of trust: Amp vocab seeds, own site and Shopify search terms, Google Trends rising-related on each seed (SerpApi), TikTok Creative Center hashtags, then local-model phrase extraction over text already pulled. A proposed term enters as `origin=discovered, status=probation` and retires if it has not reached Watch in 4 weeks. Probation terms never appear in the digest.
2. **Observe.** Adapters pull nightly. Each Trends term is pulled alone on a fixed `today 5-y` window; there is no shared anchor term and no pytrends fallback.
3. **Score.** Four components per term per week: level (z against the term's own baseline), acceleration (week-over-week change in z), breadth (`breadth_sources` and `breadth_families`), persistence (consecutive weeks at z of 1.0 or more).
4. **Tier.** One gate, no exceptions (table below).
5. **Rule.** The operator confirms term kind and motive on the Rulings page. Nothing reaches Finding without it.
6. **Forecast.** From S2, each courier states a probability on dated binary statements. The resolver is stored on the row and re-run verbatim on resolve day.
7. **Export and digest.** Sunday evening: one export per live lane, one digest capped at 12 findings.

| Tier | Rule | Shown |
| --- | --- | --- |
| Finding | `breadth_sources` of 3 or more and `breadth_families` of 2 or more, plus acceleration above 0 or persistence of 3 weeks or more, plus a phrase bank from allowed sources | Digest, page, export |
| Watch | `breadth_sources` of 2, or one source at z of 3 or more, or Finding numbers without a phrase bank | One line each; never forecast |
| Noise | Everything else | Stored, never shown |

Fan-out caps: 40 related pulls a week, rising to 60 after two consecutive weeks with a discovered term at Watch; seed shortlist of 20 a week. Own data with 12 or more weeks of history may multiply a finding's score; under 12 weeks it confirms direction only.

Calibration runs monthly: Brier plus log score and a reliability table per courier per lane. A disagreement of 0.25 or more between couriers is flagged as a live question. Prediction-market prices sit beside courier probabilities as context, never as a scored courier.

## Motive layer and phrase banks

Volume says what is rising; the motive layer records why, in the buyer's own words, and that is what makes a finding design-ready. The goal Jeremy set on Sept 16 stands: shirts that hit people in the gut.

| Motive | The buyer is saying | Threadpower example |
| --- | --- | --- |
| Identity | "This is who I am" | Wolf |
| Belonging | "I'm one of us" | Squatch Mode crew |
| Rebellion | "I don't play by that rule" | Free-thinkers, stay weird |
| Turning point | "I'm changing and I want it marked" | Bear: Go Within |
| Relief | "I need to laugh at this" | Baked |
| Nostalgia | "Take me back" | Retro cryptid, campfire |
| Aspiration | "This is who I'm becoming" | Dragon: Awaken |

The set is seven. Devotion is reserved and stays out of the enum until a faith SKU is live in Shopify and in Amp's vocab.

Rules:

- A phrase bank is up to 20 verbatim phrases per finding, attributed by URL, never paraphrased. Caps: 40 texts in, 20 phrases out, per term per week. No person table, ever.
- Motive is assigned by the phrase bank, not by the term. "Bigfoot" can be Relief or Belonging; the phrases decide.
- The local model may suggest a motive with its quotes. The operator confirms it on the Rulings page.
- A term with Finding numbers and no phrase bank is a Watch.

Allowed phrase-bank sources in S1:

| Source | Where it lives now | How Scout reads it |
| --- | --- | --- |
| Own product reviews | Shopify (review app to confirm) | Read-only token |
| Own site search terms | Shopify | Read-only token; scope to verify in the probe |
| Our own post text | Reverb (Mixpost history imported) | Reverb read-only endpoint |
| Google Trends related queries | SerpApi | Scout's own adapter |
| Converting copy rows | Amp copy bank, with stats | Amp read-only endpoint |

Each live copy row in Amp carries a motive tag, and motive win-rate per design becomes a confirm signal. That needs one new column in Amp, so it waits for Amp's first post-freeze release.

## Sources, models and budgets

S1 runs on four sources and one local model and spends on SerpApi only. Every adapter is a plugin with one contract: `pull(window)` returns rows, a health row and a cost count.

| Family | Source | Slice | Cost | Note |
| --- | --- | --- | --- | --- |
| Own data (confirm) | Shopify orders and search, Amp insights and copy rows, Reverb post text and insights | S1 | Free | Highest trust; phrase-bank source |
| Search | Google Trends via SerpApi, pinned | S1 | Paid, capped | Solo pulls, `today 5-y`. A SerpApi failure is a health row, not a silent fallback |
| Social | TikTok Creative Center | S1 | Free | Proposer seeds only. Stays only if the probe shows the pages read without a login |
| Social | X via Grok live search | S2 | Paid, capped | Watch tier and above only: 1 search, 20 posts, no profiles, no media per term |
| Search | YouTube Data API | S2 | Free (quota) | Candidate terms only |
| Social | Pinterest Trends | S3 | Free | Aesthetics |
| News, markets | GDELT, FRED, Polymarket, Kalshi | With the Life lane | Free | FRED is read from Watchtower's data, not pulled twice |
| Deferred or dropped | Reddit (commercial licence), Amazon and Etsy scrapes (ToS) | None | None | Revisit only if the ledger shows a gap |

Three workers:

| Worker | Does | Never does | Runs on |
| --- | --- | --- | --- |
| Local model (Qwen via Ollama) | Phrase extraction, dedup, noise filtering, suggested kind and motive with quotes | Forecast, or write a kind or motive | The Forge. Ollama is on the Windows host, so the base URL is the host IP, not localhost |
| Claude (API) | Cross-source synthesis, first forecaster, challenges Grok's X read | See household or customer data | Prod only, from S2 |
| Grok (API) | X sensor on Watch+ terms, second forecaster, challenges Claude for hype | Open scans | Prod only, from S2 |

Monthly ceilings in config, carried from v0.3: SerpApi $40, Grok live search $40 (S2), Anthropic $30 (S2). S1 spends $0 on X and $0 on couriers. Prices were approximate in September; the S1 probe re-reads SerpApi's plan page and the S2 probe re-reads xAI's before either cap is trusted.

Two lessons from Amp carried here. A daily cap on model calls exists beside the monthly dollar cap, because Amp hit a rate cap mid-session. And every model response is validated against a schema before use, because Amp's kit drafts failed on malformed JSON.

## Data model

One SQLite file per environment. The eight tables are v0.3's; four are added for the page, the phrase banks and operations.

| Table | Row means | Key columns | From |
| --- | --- | --- | --- |
| `terms` | One tracked term | term, lane, status (probation, active, retired), origin (seed, discovered, operator), kind, kind\_by | v0.3 |
| `observations` | One reading of one term from one source | term\_id, source, ts, metric, value, raw\_url | v0.3 |
| `scores` | One term's week | term\_id, week, z\_by\_source, accel, breadth\_sources, breadth\_families, persistence, tier | v0.3 |
| `findings` | One finding or watch | id, term\_id, lane, week, tier, motive, motive\_by, evidence\_json, proposed\_tags, blog | v0.3 |
| `phrases` | One verbatim phrase in a bank | finding\_id, text, source (one of the five allowed), url | New. v0.3 kept this inside evidence\_json; a table lets the refuse line be a database constraint |
| `forecasts` | One ledger row | id, lane, statement, resolves\_on, resolver\_json, p\_claude, p\_grok, outcome, resolved\_at, scoring | v0.3. The S0 YAML imports here unchanged |
| `packets` | One weekly courier round-trip | week, hash, courier\_responses, cost | v0.3 |
| `source_health` | One source's state | source, last\_ok, last\_error, calls\_this\_month, cap | v0.3 |
| `rulings` | One operator decision | subject (term, finding or forecast id), ruling, by, ts | v0.3. Append-only |
| `exports` | One file written | lane, week, path, sha256, rows, written\_at | New |
| `spend` | One paid call | source, ts, units, est\_cost | New. The Sources page reads it against the caps |
| `users` | One allowed person | email (from Access), display\_name, role, active | New. Same shape as Amp, Reverb and Warp |

The refuse line as a constraint: `phrases.source` is a closed enum of the five allowed sources, and a finding cannot be saved at tier Finding with zero phrase rows. Row F-2026-38-005 then resolves by query, not by audit.

Migrations are additive and numbered, with a `schema_version` row. `promote` runs every migration on a copy of prod's file before it touches prod.

## Contracts with other tools

Scout reads from four tools and writes to none of them; its only output is files that others choose to read. Each row below is one contract.

| Tool | Scout reads | Scout offers | Who acts | Slice |
| --- | --- | --- | --- | --- |
| Amp | `/api/vocab.json` (seeds), copy rows with stats, per-design insights | Proposed tags and phrase-bank candidates, inside the export | The operator resolves tags in Amp's Tag Manager. Phrases enter Amp's copy bank as candidates, never defaults | Read S1, offer S2 |
| Reverb | Post text, tags, insights | Nothing in S1 | None | S1 |
| Shopify | Orders, search terms, reviews | Nothing | None | S1 |
| Hopper | Nothing | `apparel_trends.json` | Hopper creates one idea per candidate at score zero; the team votes | S2 (Hopper H3) |
| Warp | Nothing | Bugs and ideas about Scout itself, through the shell's feedback widget | Warp's review queue. Findings never go to Warp (Grok's Nov 9 ruling) | S1 |
| Watchtower, Oracle | Watchtower's readings | `macro_signals.json`, proposed instruments and layers | Operator's pen | With the Life lane |
| Radar | Nothing | Scout's Trends adapter, so one paid pull serves two readers | Radar, when it is running | Later |

The access rule: every read goes through the other tool's read-only endpoint on forge-net with the shared-secret header. Grok's ruling makes endpoints the rule; a nightly read-only copy is the fallback only.

The Hopper contract, written identically in the Hopper spec:

```json
{
  "schema": 1,
  "week": "2026-W50",
  "generated_at": "2026-12-13T23:10:00Z",
  "candidates": [
    {
      "finding_id": "FND-2026-50-003",
      "term": "example term",
      "idea_text": "One plain line a person could vote on",
      "motive": "belonging",
      "phrases": [
        {"text": "verbatim phrase", "source": "reverb_text", "url": "https://..."}
      ],
      "tags": ["cryptids"],
      "proposed_tags": ["new-tag"],
      "blog": false,
      "evidence_url": "https://scout.threadpower.com/findings/FND-2026-50-003"
    }
  ]
}
```

Rules on that file:

- Only tier Finding rows appear. At most 12 a week, which is the digest cap and also Hopper's flood guard.
- `finding_id` is stable. Hopper stores it as `source_ref` and skips one it has seen, so reading the file twice does no harm.
- `schema` is a number. A reader that sees a number it does not know refuses the file and says so.
- Scout never emits an empty file for a lane that is not live.
- `idea_text` is built from a template (theme, motive, top phrase) in S2. Grok's ruling: template only; a local model later if it stays on the Forge; never a cloud model.

## App surface

Scout gets five pages on the shared shell in S1 (the sixth, the digest archive, is cut by Grok's ruling until someone uses the Sunday email), and only two of them are for the team. v0.3 had no page at all; the reason for one is Amp's lesson that a text report goes unread while cards with drill-down get used.

| Page | Shows | Who |
| --- | --- | --- |
| Home | Cards: findings this week, watches, forecasts due, sources failing, spend against caps | Everyone; this is the team's whole view with Findings |
| Findings | Each finding with motive first, then theme, phrase bank, evidence rows and source links | Everyone |
| Rulings | The operator's queue: confirm a term's kind, confirm a motive, resolve an operator-resolved forecast, acknowledge a proposed tag | Operator |
| Ledger | Every forecast, its frozen resolver, both probabilities, outcome, and the calibration table | Operator; readable by all |
| Sources | Health per source, calls this month, cap, last error | Operator |
| Digests | Archive of every Sunday digest and export, with hashes. Cut from S1 | Operator |

Roles: `operator` (Jeremy) writes rulings and config. `reader` (the roster) sees Home and Findings by default. There is no builder or approver role, because Scout writes to nothing.

From `forge_shell`, unchanged: Access identity check, header with the app switcher, theme, help bubbles, the bug-and-idea widget that files into Warp, doctrine footer.

Hostnames: scout.threadpower.com and scout-qa.threadpower.com, behind Cloudflare Access, added with the same setup script Reverb and Warp use. The main tunnel is remotely managed, so both hostnames are added in the dashboard's ingress list or they return 404.

The Sunday email stays only as a short notice with a link, sent from the shared Forge sender to the operator. Home is the thing people open.

## Operations carried from Amp and Reverb

Scout is born with the operating pieces Amp and Reverb each earned through an incident; none of them is built fresh. Each row names the incident or ruling it came from.

| Pattern | Where it was learned | In Scout |
| --- | --- | --- |
| QA and prod pair, QA refreshed from prod | Amp v0.16a | Two containers from one image. Proposed ports 8091 (prod) and 8191 (QA), to confirm free on the Forge |
| Release path: update QA, refresh QA from prod, promote on a weekday morning | Amp; adopted for Reverb Nov 16 | Same three scripts from `forge_shell` |
| `promote` migrates a copy first; `up` refuses to rebuild prod from a newer tree; `rollback` exists | Amp v0.16a and v0.16b | Same |
| Stale-mount guard: heartbeat file, `doctor`, `remount` | Amp lost five days of work to a stale bind mount in October, and reset again after the Nov reboot | Same, from day one |
| Nightly backup with an off-box copy | Amp v0.16a | Same. The ledger is the asset; it is the first thing backed up |
| `/health` as a deploy gate | Reverb slice 8 | Blocks on: database writable, heartbeat fresh, schema current. Warns on: a source failing, last backup old, a cap above 80% |
| JSON logs to stdout with rotation | Reverb slice 8 | Same |
| Alerts by email from the shared Forge sender, Signal for the loud tier | Resend replaced SMTP in September; shared sender since Nov 9 | Through the shell's notifier. Moves to Cue when Cue is lifted into the shell |
| Secrets in `/forge/secrets.env` and `/forge/secrets.qa.env`, no inline comments | A parsing bug leaked a token fragment during Reverb's deploy | Same. New keys: `SERPAPI_KEY`; from S2 the courier keys |
| QA writes are recorded, not sent | Amp's QA runs on a read-only Meta token | QA replays saved pulls and never calls a paid source or a courier |
| Probe before page | Reverb's Meta publish probe ran before any UI existed | Every outside dependency has a hand-run probe script in slice S1a |
| Days-left on anything that expires | A 60-day Meta token expired silently on Nov 9 | Sources page shows key age and plan renewal where the API reports it |
| Operator runs scripts, never types commands | Standing rule since Sept 6 | Every step in a deploy note is one script |
| Never bring up two things that page on the same night | Pairing rule, Sept 6 | Scout's first night is not shared with any other first night |

How the build itself runs, same as Amp and Reverb:

1. This spec goes to Grok with the prompt at the end. Rulings come back as FINE, SHOULD or MUST per item and are folded in as a dated "Grok review" section.
2. Each slice is built with its tests, then an independent adversarial review runs on the diff before anything is packaged. Every finding is fixed or answered.
3. The zip and the as-built notes go back to Grok for a review of the build, not the prompt.
4. QA first. Tests pass inside the image. Then promote.
5. An "as built" section is added to this doc per slice, so the doc and the box never drift apart.

## Build slices, gates and acceptance tests

Four slices, each ending in a proof rather than a feature list; nothing in a later slice starts until the proof holds. S1 is one batch on purpose: the shell and deploy scripts already exist, so the page, the adapters and the scorer no longer need separate sittings.

| Slice | Builds | Proof it must pass |
| --- | --- | --- |
| S0 closeout | No code. The five September rows are voided with the reason written on each, and five new rows are written with resolvers frozen from pulls made that day | The five old rows read void. Five new rows exist with every resolver field filled, and the first of them resolves cleanly by rule |
| S1a probes | Six hand-run scripts, listed below | Each prints PASS. Probes 1, 2, 5 and 6 block S1; probes 3 and 4 only cut a source |
| S1 | Container at `/forge/scout` on the shell with QA and prod; the S0 ledger imported; adapters for Amp, Reverb, Shopify, SerpApi and (if its probe passed) Creative Center; proposer; scorer with the single gate; local-model extractor; `phrases` with its constraint; five pages; Sunday digest; `apparel_trends.json` written with no reader yet | Four clean weeks of nightly runs, counted from the first night every S1 adapter is green. Sources page green. At least one discovered term reaches Watch. The operator has cleared the Rulings queue each week |
| S2 | Claude and Grok couriers; forecasts flowing into the ledger; Grok live X on Watch+ terms; monthly calibration report; Hopper reads the export; phrase candidates and motive tags offered to Amp; the Life lane as v0.3 planned it | First 10 forecasts resolved. Calibration report 1 exists. One phrase bank has been used in live copy. One Scout idea has been voted on in Hopper |
| S3 | Labs lane, Pinterest, Etsy's official API if commerce breadth is thin, Gemini as quarterly cold reviewer | The operator has adopted at least one proposed tag and one proposed instrument |

The six probes, run in one sitting before any page exists:

1. SerpApi solo pull: the same term, `today 5-y`, pulled twice an hour apart, returns identical values for every closed week. The plan's price and monthly quota are read off the account page.
2. SerpApi rising-related: one seed returns a list, and the call count matches what the cap assumes.
3. Creative Center: the hashtag pages for apparel read without a login. A fail drops it from S1 with no replacement.
4. Shopify: the existing read-only app can return search terms and reviews. A missing scope is named.
5. Amp and Reverb: each returns vocab, copy rows with stats, and post text over forge-net. If either needs a new read-only endpoint, that is a small release in that tool, listed in Open calls.
6. Local model: from inside a container, Qwen at the Windows host IP returns schema-valid phrase extraction on 40 real texts.

Acceptance tests that ship with S1, each a named test in the suite:

- A forecast's resolver cannot be edited after creation.
- A finding cannot be saved at tier Finding with no phrase rows.
- A phrase with a source outside the five is refused by the database.
- A probation term never appears in the digest or the export.
- A discovered term that has not reached Watch in 4 weeks retires.
- Own data never adds to `breadth_sources` or `breadth_families`.
- Every Trends pull has exactly one term.
- A hit cap degrades to free sources, pages once, and the run finishes.
- QA makes no outbound call to a paid source or a courier.
- A schema-invalid model response is retried once, then refused.
- The export is renamed into place and its hash is recorded.
- The digest holds at most 12 findings.

Proposed order against the calendar, for Jeremy and Grok to rule on: Grok round this week; S0 closeout and probes on any evening, since neither deploys anything; S1 built as soon as the rulings are folded in; S1's first prod night on or after Dec 2, clear of Black Friday through Cyber Monday. Starting S1 early matters because its gate is four weeks of clock time that no amount of building shortens.

## Open operator calls

Nine things only Jeremy can answer. The first decides whether the frozen spec's own condition ("no v0.4 unless S0 refuses a row") was ever tested.

- [ ] **S0 rows.** Did row 001 (`bigfoot`) get resolved on Sept 20, and are `scout-s0-forecasts.yaml` and the two evidence CSVs on the Forge? All five rows are past their dates. Grok's ruling is to void all five and write five new ones, so this is now only a check that nothing was resolved that I have no record of.
- [ ] **Name.** "Scout" was provisional in September. Keep it?
- [ ] **Footer line.** "Scout reads widely, proposes, and keeps score. A person rules." Yours to reword.
- [ ] **Readers.** Who besides you sees Scout during S1's four weeks?
- [ ] **Read endpoints.** If probe 5 shows Amp or Reverb needs a new read-only endpoint, is that allowed inside Amp's narrowed freeze (no schema change, no change to packet numbers)?
- [ ] **Motive on Amp copy rows.** One new column in Amp. Proposed for Amp's first release after Dec 1.
- [ ] **Budget.** SerpApi at up to $40 a month from S1's first night. Still right?
- [ ] **Order.** Hopper H1 first, with Scout S1 right behind so its four-week clock starts early. Or the reverse?
- [ ] **Hand-built or Foundry.** Proposed: built in chat like Amp and Reverb. Foundry is not built, and Scout should not wait on it.

## Grok review 1 (Nov 19)

Grok ruled v0.4 buildable as written: 11 FINE, 3 SHOULD, no MUST, and no doctrine reopened. First thing to build is the S0 closeout and the probes, then S1.

| # | Item | Ruling | What changed in this doc |
| --- | --- | --- | --- |
| 1 | The four renames | FINE. None is a doctrine change | Nothing |
| 2 | S0 | Void the five September rows with the reason "resolve dates passed, no outcome recorded", and write five new ones. Does not reopen v0.3 | S0 closeout row in the slices table; Open calls item 1 |
| 3 | `phrases` table with a closed enum | FINE | Nothing |
| 4 | S1 as one batch | SHOULD. The risk is the four-week clock starting on a broken adapter | The clock now starts on the first night every S1 adapter is green. The digest archive page is cut (item 14) |
| 5 | The six probes | FINE. SerpApi and the local model block; Creative Center and Shopify scope only cut a source | Probes line in the slices table. Grok did not rule on probe 5 (Amp and Reverb reads); I have it blocking, since phrase banks cannot exist without it |
| 6 | QA replays only | FINE | Nothing |
| 7 | `/health` lists | FINE | Nothing |
| 8 | Reads from Amp and Reverb | SHOULD: read-only endpoints over nightly copies | Endpoints are the rule; a copy is the fallback. This makes Open calls item 5 a real dependency |
| 9 | S2 courier code built during the wait | SHOULD: allowed if it cannot run | Built behind a switch that defaults off, with a test that no courier call leaves while it is off |
| 10 | Life lane in S2 | FINE as frozen | Nothing |
| 11 | `idea_text` | Template only. A local model later if it stays on the Forge. Never a cloud model | Contract rules |
| 12 | Twelve findings against Hopper's top 5 | FINE | Nothing |
| 13 | Order and first nights | FINE | Nothing |
| 14 | Gates and the one cut | Four clean weeks, Sources green, one discovered term at Watch, Rulings cleared weekly. Cut: the Digests archive page | App surface |

Grok's flag, adopted: the Sunday digest was still a text report. The email is now a short notice with a link; Home is the thing people open.

From Grok's context round, adopted:

- No Labs signal rides inside S1. Grok ruled that a Labs flag would be the lane cut reopened by the back door. Labs stays S3.
- Scout stays out of judgment calls: the family-friendly pivot, whether to lean into the Latino audience, real people against AI models as a brand stance, the site as a studio, Threadlink. It can show evidence beside them and nothing more.
- What makes the ledger credible to a Labs prospect: closed, dated, binary rows with frozen resolvers, both couriers disagreeing in the open, and a calibration table. What makes it a toy: unscored rows, averaged probabilities, forecasts that roll forward.

Not adopted, and why:

- **Grok's five candidate forecast rows.** Three resolve against Scout's own score table ("reaches Watch by week X"), which makes Scout the judge of its own forecast and breaks the frozen-resolver rule. One ("a phrase bank of 10 exists by W52") is a task we control, not a forecast. The five new S0 rows get written the September way: an outside series, numbers frozen from a pull on the day.
- **Grok's seed term list as written.** Bare words like "bear", "wolf", "sovereign" and "fandom" are hopeless on Google Trends, and "free shipping" and "turning point" are copy findings, not trend terms. The seeds come from Amp's vocab as specced, with qualified phrases added by the operator.
- **Three of the ten Apparel questions.** Whether stacked interests beat single ones, whether free shipping is still the best line, and whether second-person copy wins are Amp's questions, answered from its own proof table. Scout does not redo them.
- **First-pass motives.** "Inner work" and "Self-knowledge" are not in the set of seven. The motives stay unassigned until a phrase bank exists, as the doctrine says.

## Grok review 2 (Nov 19, evening)

Grok read the folded doc and confirmed it with no new rulings: every adoption matches, the rejections stand (his forecast rows, the bare seed terms, the three questions that belong to Amp), and frozen doctrine is untouched. He also agreed Scout is built by hand, not held for Foundry. Build order is unchanged: S0 closeout and the six probes, then S1.

## Grok review prompt

Paste this with two attachments: this doc exported, and the frozen v0.3 (`scout-spec-v0.3.md`). The Hopper spec goes in the same sitting so the shared contract is ruled on once.

```text
Grok review request: Scout v0.4, build layer on a frozen doctrine

You froze Scout's doctrine at v0.3 on Sept 16 and said no v0.4 unless S0 refused a
forecast row. S0 was never closed: all five rows are past their resolve dates with no
outcome on record. Meanwhile Amp, Reverb and Warp were built, and forge_shell exists
(identity, switcher, theme, help, feedback widget into Warp, deploy scripts, JSON logs,
/health deploy gate, alerts). v0.4 claims to change no doctrine. It adds a page, a QA
and prod pair, probes, a written contract with Hopper, and rebased slices.

Your rulings through round 3 stand. Rule on each item as FINE, SHOULD or MUST, with
one line of reason.

A. Doctrine boundary
 1. The four renames (Mixpost text to Reverb post text; Forge Ads to Amp; inspiration
    engine to Hopper; rulings on a page instead of a digest reply). Is any of them a
    doctrine change in disguise?
 2. S0: resolve the five September rows from saved evidence, or void them and write
    five new ones? Which keeps the ledger honest, and does the answer reopen v0.3?
 3. A `phrases` table whose source column is a closed enum of the five allowed sources,
    with row F-2026-38-005 resolved by query instead of audit. Accept?

B. Build shape
 4. S1 as one batch: container on the shell, five adapters, proposer, scorer,
    extractor, six pages, digest, export. Right size, or where is the cut? What fails
    in one batch that smaller slices would have caught?
 5. The six probes. Which is missing? Which should block S1, and which should only cut
    a source?
 6. QA replays recorded pulls and never calls a paid source or a courier. Enough
    fidelity to trust the scorer, or does QA need a small live budget?
 7. /health: blocks a deploy on database, heartbeat and schema; warns on a failing
    source, an old backup and a cap above 80 percent. Anything in the wrong list?
 8. Reads from Amp and Reverb: their read-only endpoints, or a nightly read-only copy
    of each SQLite file? Which is less fragile for three apps on one host?
 9. S1's gate is four clean weeks. May S2's courier code be built and left switched
    off during the wait, or does that break "nothing later starts until the proof
    holds"?

C. Scope
10. The Life lane sits in S2 as frozen. Revenue is the priority and Apparel is the
    lane with revenue behind it. Does Life hold, or slip to S3?
11. `idea_text` in the Hopper export: a template (theme, motive, top phrase), the
    local model, or Claude? Hopper refuses to send idea text to a cloud model.
12. Twelve findings a week into Hopper at score zero, against Hopper's top-5 nightly
    cap. Is that the whole flood guard, or does Hopper need a per-source ceiling?

D. Sequence
13. Hopper H1 first with Scout S1 right behind, first Scout prod night on or after
    Dec 2 and never the same night as Hopper's first runner night. Right order?
14. Your gates for S1, and the single thing you would cut.

Be blunt. The team does not read text reports, so flag anywhere this design still
assumes someone will read a digest. Flag anywhere the page quietly gives Scout a pen
it was not given in v0.3.

End with one line: is v0.4 buildable as written, and what is the first thing to build.
```
