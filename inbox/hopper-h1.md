# Hopper — Build Spec v0.4 (for Grok)

Nov 19, 2026 · @Jeremy

## Status

Hopper v0.3 went through two Grok rounds (Sept 22) and stopped one step short of freeze: three ticks from Jeremy were never recorded. This version keeps every frozen ruling, asks for those three ticks, and adds the build layer that Amp, Reverb and Warp have taught us since. The earlier text is [Hopper Spec v0.3](https://claude.ai/artifact/AvdJ7TH9PV8CVmDTmeQEBE).

| Item | State on Nov 19 |
| --- | --- |
| Doctrine, lifecycle, runner rules, data tables, refuse lines | v0.3, frozen after round 2 except the three ticks. See Open calls, item 1 |
| Idea bank and page (old I0) | Not built |
| Runner | A demo kit exists from Sept 22 (`hopper_export_templates.py`, `hopper_demo.py`): it pulls workflow templates from ComfyUI's job history and runs one idea to a gallery folder. Not a service |
| ComfyUI | Running on the Forge at D:\\ComfyUI, Windows-native, started by hand. Run-window watcher installed |
| Warp | Live on QA and prod with its own review queue and a "send to Hopper" action that has nowhere to send yet |
| Scout | Spec frozen, not built |

What changed underneath v0.3, and what v0.4 does about it:

| Since September | Effect on Hopper |
| --- | --- |
| Warp reviews everything in its own queue before Plane. Plane Intake is no longer the landing spot | A promotion lands as a card in Warp's review queue. "Warp is the only Plane client" stands unchanged |
| Warp is live now, not a future dependency | The Warp handoff moves from the third phase into the first slice |
| `forge_shell` exists (identity, switcher, theme, help, feedback widget, deploy scripts, health gate, alerts) | Hopper mounts it on day one instead of copying Forge Ads' page code |
| Amp and Reverb run a QA and prod pair with promote and rollback | Hopper gets the same pair. The "I0 is a weekend" cut grows by that much |
| Luma voice spec names `hopper.add_idea` as a command | Hopper exposes one intake endpoint that the page, Warp, Scout and Luma all use |
| Jeremy wants bigger build batches (Oct 23) | Four phases become three slices plus a parked public door |

## Doctrine and refuse lines

**Hopper: the bin and the rabbit. Ideas go in. People decide what comes out. Warp is the only gate into Plane.** That line is the page footer. The ten doctrine lines are v0.3's, shortened; two are amended and marked.

1. **Ideas live outside Plane.** Plane holds committed work. Hopper holds everything before that, and most of it may die there quietly.
2. **People decide, Hopper proposes.** Votes, reviews and promotions are human acts, recorded by name.
3. **Anyone on the roster can promote, and one name is enough.** *Amended:* v0.3 listed four people by name; v0.4 says "the roster", which is the `users` table. A seat is a row, not a code change. Promotions are append-only. A submitter may promote their own idea.
4. **Warp is the only Plane client.** *Amended:* a promotion becomes a card in Warp's review queue, not a Plane Intake item. Hopper never writes to Plane.
5. **All generation is local and free.** ComfyUI on the Forge, models cleared for the use, no paid nodes. Overnight is Hopper's window; daytime GPU belongs to people.
6. **Visibility is a byproduct.** No reports on people.
7. **Every source is equal at the gate.** A Scout finding, a transcript line and a shower thought all enter at score zero. Source is a tag, not a rank.
8. **Forge work does not live in Hopper.** Bugs and features go through the feedback widget to Warp.
9. **Same build pattern as the rest of the Forge.**
10. **Wrong in public, quiet in private; never the reverse.** The Board is the whole picture. Names are kept so an act can be attributed. Names are not a view. (Tick 1 of 3.)

Refuse lines, all carried from v0.3: never writes to Plane; never promotes, publishes or spends on its own; never uses paid or cloud generation; never interrupts a person's GPU job; never blocks a submission with a model; never renders a third-party character, logo or licensed face (the prompt writer strips them and says so); never scrapes social platforms for ideas; never stores more about a public submitter than the idea and a display name; never sends idea text to a cloud model; never reports on people; never auto-deletes an idea; never holds Forge work. Added in Grok review 1: paid-ad copy variants never go on the Board; they belong in Amp.

Build-layer refusals added in v0.4:

- The runner never starts a night it cannot finish cleanly. A failed preflight (ComfyUI, Ollama, disk, workflow files, model files) skips the night and says which check failed.
- QA never queues GPU work. QA's runner writes the prompts and stops, so a test never takes the card from a person or from prod's night.
- Intake has one door. The page, Warp, Scout and Luma all post to the same endpoint, and the same rules run on each.
- A package is written whole to a temp folder and renamed. Warp never reads half a package.

## Where Hopper sits

Hopper holds everything before commitment; the one crossing into work is Promote, and a named person makes it.

&#91;embedded content: Hopper's loop: intake to promotion, then Warp and Plane\]

The top row is play and belongs to Hopper. The bottom row is work: Warp reviews the package and is the only thing that writes to Plane. An idea can also be promoted straight from the Board with no concepts attached.

| Neighbour | Its job | Hopper's relation |
| --- | --- | --- |
| Scout | Finds and proves trends | Feeds ideas in at score zero, tagged with motive |
| Warp | Reviews incoming work; sole Plane client | Receives promotions; sends idea-shaped items back |
| Plane | Committed work, in three workspaces | Never touched by Hopper |
| ComfyUI, Ollama | Local image generation and prompt writing | Used overnight, queued behind people |
| Amp, Reverb | Paid ads and organic posts | Downstream of committed work, never of Hopper |
| Architect, later Foundry | Builds Forge software | Builds Hopper; is never fed by it |

## Idea lifecycle

Six states, unchanged from v0.3. People move an idea into Submitted, Reviewed, Promoted and Parked. Two states are set by rule: Shortlisted, when an idea's vote score clears the bar, and Generated, when the runner finishes the night's batch.

| State | Means | How it gets there | Rules |
| --- | --- | --- | --- |
| Submitted | On the Board, open for votes | Any intake door | One vote per person per idea; a second tap removes it. A team submission whose text exactly matches an existing team idea is refused with a link to it |
| Shortlisted | In the queue for the next night | Score clears the bar | The bar is a number in config, not a judgment |
| Generated | Concept images exist | The runner | Set by the runner, never by a person |
| Reviewed | At least one person has thumbed the concepts | One thumb | One notes box per idea, overwritten, last editor logged. The notes ride to the next night |
| Promoted | Someone said make it | Any roster member, one name | Promoter ticks the winning concepts first. Zero concepts is allowed and the confirm says so. Append-only |
| Parked | Not now | Any roster member | Nothing is deleted. Parked ideas can be revived. The runner ignores them |

Scores are computed, never stored. Vote score is the sum of votes, each decayed with a 14-day half-life. Concept score is net thumbs. The half-life and the shortlist bar are config numbers; neither score is stored.

Three rules for the bar and the night's list, set by Jeremy on Nov 21. An idea clears the bar when its score is at or above it. Once an idea is Shortlisted it stays Shortlisted, even if its score later drops below the bar, until a person moves it. When two shortlisted ideas have the same score, the older one goes first, then the one with the lower id.

Rules for intake, set by Jeremy on Nov 21. Text that is empty or only spaces is refused. A person submits only as themself, and a service submits only under its own system name. A service submitting as itself may use any source on the list. When more than one refusal applies, the door gives the first of these: not on the roster, wrong submitter, empty text, bad lane, bad source. The closed door comes first, so someone off the roster learns nothing else. The reasons travel as the codes not\_on\_roster, wrong\_submitter, empty\_text, bad\_lane and bad\_source, and the page turns them into words.

Rules for duplicates, set by Jeremy on Nov 21. The hash is the SHA-256 of the idea's text exactly as it was typed, with no trimming and no change of case, so "Squatch" and "squatch" are different ideas. Only a team submission that matches a team idea is a duplicate. A team idea blocks an exact copy whatever state it is in, parked and promoted included. The refusal carries the id of the idea it copies, and the page turns that id into a link. If the same text is ever stored twice as a team idea, the lower id is the one given.

Rules for the package, set by Jeremy on Nov 21. The package holds only the concepts the promoter ticked, in the order they ticked them. A ticked concept that is not one of the idea's own concepts is an error, and no package is built. Concept files are named concept-1, concept-2 and so on in that order, and reference images are named ref-1, ref-2 and so on in the order they were stored. Each keeps its own file ending. A promotion with no concepts still carries the idea's reference images. People appear by display name and never by email. A submitter or promoter with an @ in it is a person, and anything else is a system name, which is shown as it is. A person with no display name is an error, and no package is built. The time is written in UTC, to the second, ending in Z. The scout block is filled only when the idea's source is scout: finding\_id is the idea's source\_ref and motive is its scout\_motive. evidence\_url is always null for now, because Hopper does not store one yet. An idea with no lane or no reviewer notes has null for them. With no concepts, the promote confirm adds "No concepts attached." after its sentence.

Merging two duplicates is a human act: keep one text, fold votes one per person, set `merged_into` on the loser and park it. The Merge view says, "Your vote on the other idea is folded, not doubled."

The Board shows Submitted, Shortlisted, Generated and Reviewed. Parked and Promoted are search-only, so the Board never becomes a graveyard.

The promote confirm reads: "This hands a package to Warp. It will show up in Warp's review queue." A mistaken promotion is declined in Warp, not undone here.

## Intake doors

Seven ways an idea gets in, all through one endpoint (`POST /api/ideas`, shared-secret header on forge-net, Access identity on the page). Three are in the first slice.

| Door | Who or what | How it arrives | Slice |
| --- | --- | --- | --- |
| Team page | Anyone on the roster | Submit: one idea, or a pasted list split by line, optional reference image, optional lane (Apparel, Content, Story) | H1 |
| Seed import | Josh's notes, Steph's list, existing content ideas | A named script with a dry run. Hashes each line; running it twice does no harm | H1 |
| Warp | "Send to Hopper" on a Warp review card | Warp posts the card's text with source set to warp, and puts where the card came from (meeting, tool feedback) in source\_ref | H1 |
| Scout | Findings that clear Scout's single gate | Hopper reads `apparel_trends.json` and creates one idea per candidate, tagged with motive and a link back. Score zero | H3 |
| Calls and live content | Meet notes, podcast and live recordings | Warp's meeting pass is the one reader: task-shaped items stay in Warp, idea-shaped items come here | H3 |
| Luma | "Add an idea to the Hopper" by voice or text | Forge Dispatch calls the same endpoint as the signed-in person | H3, when Dispatch exists |
| Public | Website form, replies to a monthly post | A moderation queue the team clears first | Parked (H4) |

What every door sends: `text`, `lane`, `source`, `submitter` (a roster email or a system name), and optionally `source_ref`, `scout_motive`, an image. The lane value is lowercase on every door and in the package (apparel, content, story); the page shows the labels capitalised.

What every door gets back: the idea id, or a refusal with the reason. The automatic refusals are an exact duplicate of a team idea, a submitter not on the roster, and a service key submitting as a person. Each service has its own key and submits under its own system name; a service key may not submit as a person. Luma is the one exception, and it passes the signed-in person's Access identity, which Hopper checks itself.

The public door still starts without a build: a monthly "send us your idea" post, replies pasted into Submit by hand. The form is built only after that post has shown people reply, and only after a lawyer has written the terms.

## The overnight runner

The runner wakes at 10 PM, takes the top five shortlisted ideas, and has up to twenty concepts in the Gallery by morning without anyone opening ComfyUI. Its rules are v0.3's. What is new is where it runs and what it checks first.

1. **Preflight.** ComfyUI answers, Ollama answers, free disk is above the floor, both workflow files exist, both model files exist by name. Any miss skips the night and names the check.
2. **Shortlist.** Top N shortlisted ideas by score. Config: N = 5, 4 prompts per idea, 14-day vote half-life. Each idea's notes string rides along.
3. **Prompt writer.** Local Qwen turns one idea into four prompts: two for Qwen-Image Turbo, two for FLUX.2 Klein 4B. It works from a house style file plus four example prompt pairs that Jeremy or Josh write before the first night. Third-party marks and characters are stripped first, and the Gallery says so.
4. **Submit.** The runner copies a saved API-format workflow, patches three fields (prompt text, seed, filename prefix), tags the job `hopper`, and posts it. It never edits the graph. Node ids live in config.
5. **Wait rules.** A person's job running at 10 PM: queue behind it. Still blocked at 2 AM: stop and report `blocked_by_user_job`. No new job after 5 AM. Never interrupt anyone. (Tick 2 of 3.)
6. **Record.** Every image is a row: idea, model, model file, prompt, seed, path. Files land in a dated folder per idea.
7. **Morning message.** One message with status (`ok`, `partial`, `skipped`, `failed`, `blocked_by_user_job`), the concept count, the model files loaded and a Gallery link.

Placement, which v0.3 left loose:

| Piece | Where | Why |
| --- | --- | --- |
| Runner | A small Windows-side worker beside ComfyUI, started by a scheduled task (Grok review 1, item 4) | ComfyUI and Ollama are both native on Windows, so the runner talks to both on localhost. No WSL2 NAT in the path. The Sept 22 demo kit already runs this way on ComfyUI's own Python |
| Hopper container | WSL2 Docker, forge-net | Holds the bank, the pages and the API. It never calls ComfyUI or Ollama |
| Between them | The runner calls Hopper's API on localhost: fetch the shortlist, report preflight, post each concept row, close the run | One direction only. If Hopper is down the runner skips the night; if the runner is down Hopper's health row says no run was reported |
| Concept files | A folder on the Forge's large drive, written by the runner and mounted read-only into the container | Images are big; the nightly SQLite backup stays small |
| Run-window watcher | Windows task, already installed | Leaves `hopper`-tagged jobs alone; the runner owns the 2 AM and 5 AM edges |
| QA | No GPU work. The runner's dry mode against QA writes prompts and stops | A test never takes the card |

Known weak point: ComfyUI is still started by hand and does not come up on boot. Until that is fixed, a reboot means a skipped night and a morning message that says so. The fix belongs to the Forge infra sitting, not to Hopper.

The demo kit from Sept 22 already does steps 4 and 6 for one idea. H2 turns it into the worker; it does not start over.

Video, upscale and background removal stay out of the nightly run. They run only on Promoted ideas, by request, in H3.

## Data model

One SQLite file per environment. Six tables are v0.3's; two are added for the runner and for audit.

| Table | Row means | Key columns | From |
| --- | --- | --- | --- |
| `users` | One allowed person | email (from Access), display\_name, role (member, operator), active | v0.3, plus role |
| `ideas` | One idea | id, text, text\_hash (unique where source = team), lane, source (team, seed, warp, scout, transcript, luma, public), source\_ref, submitter, created, state, image\_path, reviewer\_notes, notes\_by, notes\_at, scout\_motive, merged\_into | v0.3, with three more source values |
| `votes` | One person's vote on one idea | idea\_id, user, created; unique on (idea\_id, user) | v0.3 |
| `concepts` | One generated image | id, idea\_id, run\_id, model, model\_file, prompt, seed, file\_path, style\_file\_hash, stripped\_marks | v0.3 |
| `reviews` | One person's thumb on one concept | concept\_id, user, value, created; unique on (concept\_id, user) | v0.3 |
| `promotions` | One promotion, append-only | idea\_id, promoted\_by, created, concept\_ids, package\_path, warp\_ref, warp\_outcome | v0.3. `plane_ref` becomes `warp_ref`: Warp's card id, with the outcome Warp reports back |
| `runs` | One night | id, run\_date, status, started, ended, preflight\_json, ideas, concepts, note | New. The morning message and the health row both read it |
| `events` | One state change | idea\_id, from\_state, to\_state, by, ts | New. Append-only. Reviving, parking, merging and purging are all visible after the fact |

Reference images live under an uploads folder per idea and travel in the promoted package. Concept files live on the large drive, outside the backed-up data folder.

The public door adds one table when it is built: `inbox`, holding only the idea text, a display name and the credit checkbox.

Migrations are additive and numbered, with a `schema_version` row. `promote` runs every migration on a copy of prod's file first.

## Contracts with other tools

Hopper has one output, the promotion package, and one reader of it, Warp. Everything else is an input.

| Tool | Direction | What crosses | Slice |
| --- | --- | --- | --- |
| Warp | Out | The promotion package, as a card in Warp's review queue | H1 |
| Warp | In | "Send to Hopper" cards; later, idea-shaped lines from meeting notes | H1, H3 |
| Warp | In | Outcome of a promotion: accepted (with where it landed) or declined | H1 |
| Warp | Out | Bugs and ideas about Hopper itself, through the shell's feedback widget. Never onto the Board | H1 |
| ComfyUI | Out | API-format workflow jobs tagged `hopper` | H2 |
| Ollama | Out | Idea text to the local prompt writer. Nothing goes to a cloud model | H2 |
| Scout | In | `apparel_trends.json` | H3 |
| Luma / Forge Dispatch | In | `hopper.add_idea` through the intake endpoint | H3 |
| Amp, Reverb | None | Both are downstream of committed work, never of Hopper | None |

The promotion package is one folder per promotion:

```json
{
  "schema": 1,
  "promotion_id": 41,
  "idea": {"id": 318, "text": "...", "lane": "apparel", "source": "team", "source_ref": null, "submitter": "Josh"},
  "promoted_by": "Steph",
  "promoted_at": "2026-12-08T15:02:00Z",
  "reviewer_notes": "...",
  "scout": {"finding_id": null, "motive": null, "evidence_url": null},
  "concepts": [
    {"file": "concept-1.png", "model": "flux2-klein-4b", "prompt": "...", "seed": 1234}
  ],
  "reference_images": ["ref-1.jpg"]
}
```

Rules on the package:

- `concepts` may be empty. Studio work can start from a sentence.
- Warp proposes the project from `lane` (Apparel and Content ideas go to the Apparel workspace; a Story idea carries no workspace proposal). A person confirms in Warp's review, like every other card.
- Hopper posts the package once. If Warp is down, the package waits on disk and Hopper retries; a promotion is never lost and never sent twice (`promotion_id` is the key).
- The package reaches Warp by HTTP post to Warp's intake on forge-net. Probe 4 proves that path before H1 is built.

The Scout contract, written identically in the Scout spec: Hopper reads `apparel_trends.json` once a week, creates one idea per candidate with `source = scout`, `source_ref = finding_id`, `scout_motive = motive`, at score zero. A `finding_id` already seen is skipped. An unknown `schema` number is refused. Scout sends at most 12 a week, which with the top-5 nightly cap is the whole anti-flood rule.

## App surface

Five views for the team and one for the operator, and the page opens on the Board. Amp taught us that Steph and Josh stay away from a tool with too much on the screen, so nothing else is added in v1.

| View | What it does | Slice |
| --- | --- | --- |
| Board | Every open idea, newest first, with score and source tag. One tap to vote, tap again to take it back. Filter by lane or source | H1 |
| Submit | One box, optional image, optional lane. Paste-a-list mode splits lines into ideas | H1 |
| Promote | On any idea: the confirm with its consequence, the promoter's name, the package written | H1 |
| Merge | Pick two ideas, keep one text, fold votes one per person | H2 |
| Gallery | Last night's concepts grouped by idea, raw prompt under each image, thumbs, one notes box per idea, checkboxes to pick winners | H2 |
| Nights (operator) | The `runs` table: each night's status, preflight result, counts | H2 |

The page still has no comment threads, assignments or due dates. The moment an idea needs those it is a project, and Warp has it.

Roles: `member` (the roster) can do everything on the five views. `operator` (Jeremy) also sees Nights, edits config, and can purge an idea, which is logged.

From `forge_shell`, unchanged: Access identity check, header with the app switcher, theme, help bubbles, the bug-and-idea widget that files into Warp, doctrine footer. An email that is not on the roster gets a polite closed door.

Hostnames: ideas.threadpower.com and ideas-qa.threadpower.com, with hopper.threadpower.com as an alias, behind Cloudflare Access. Both are added in the remotely managed tunnel's ingress list with the same setup script Reverb and Warp use.

The page must work on a phone. Ideas arrive in the moment.

## Operations carried from Amp and Reverb

Hopper is born with the operating pieces Amp and Reverb each earned through an incident; none is built fresh. Each row names where it came from.

| Pattern | Where it was learned | In Hopper |
| --- | --- | --- |
| QA and prod pair, QA refreshed from prod | Amp v0.16a | Two containers from one image. Proposed ports 8093 (prod) and 8193 (QA), to confirm free on the Forge |
| Release path: update QA, refresh QA from prod, promote on a weekday morning | Amp; adopted for Reverb Nov 16 | Same three scripts from `forge_shell` |
| `promote` migrates a copy first; `up` refuses to rebuild prod from a newer tree; `rollback` exists | Amp v0.16a and v0.16b | Same |
| Stale-mount guard: heartbeat file, `doctor`, `remount` | Amp lost five days of work to a stale bind mount in October | Same, from day one. Hopper has two mounts (data, concept files), and `doctor` checks both |
| Nightly backup with an off-box copy | Amp v0.16a | The SQLite file and uploads. Concept images are not backed up; they can be rerun from prompt and seed |
| `/health` as a deploy gate | Reverb slice 8 | Blocks on: database writable, heartbeat fresh, schema current. Warns on, read only from Hopper's own rows: last night failed, the last preflight reported ComfyUI or Ollama unreachable or disk below the floor, a package waiting on Warp. /health never calls ComfyUI or Ollama |
| Per-attempt record and a retry button instead of redo | Reverb slice 8, replacing Mixpost's recreate-the-post | `runs` and `events` tables. A failed night can be rerun by the operator inside the window |
| JSON logs to stdout with rotation | Reverb slice 8 | Same |
| Alerts by email from the shared Forge sender | Shared sender since Nov 9 | The morning message and any failed night. Moves to Cue when Cue is lifted into the shell |
| Secrets in `/forge/secrets.env`, no inline comments | Token fragment leaked during Reverb's deploy | Same. Hopper needs only the shared forge-net token; it has no outside keys |
| QA writes are recorded, not sent | Amp's QA uses a read-only Meta token | QA writes prompts and never queues a GPU job. QA's promote writes a package and never posts it to prod Warp |
| Probe before page | Reverb's Meta publish probe | Three hand-run probes in slice H0 |
| Fewer pages per role | Steph and Josh were not using Amp until their home was trimmed | The Board is the home. Operator-only pages stay out of the team's menu |
| No one is pinged about other people | Warp ruling, Nov 9 | The only message Hopper sends is the morning one |
| Operator runs scripts, never types commands | Standing rule since Sept 6 | Every deploy step is one script, including the Windows side |

How the build itself runs, same as Amp and Reverb:

1. This spec goes to Grok for review. Rulings come back as FINE, SHOULD or MUST per item and are folded in as a dated "Grok review" section.
2. Each slice is built with its tests, then an independent adversarial review runs on the diff before anything is packaged.
3. The zip and as-built notes go back to Grok for a review of the build.
4. QA first. Tests pass inside the image. Then promote.
5. An "as built" section is added to this doc per slice.

## Build slices, gates and acceptance tests

Three slices and a parked fourth, each ending in a proof; nothing later starts until the proof holds. v0.3's I0 is one batch now, with the Warp handoff pulled forward, because the shell and deploy scripts already exist.

| Slice | Builds | Proof it must pass |
| --- | --- | --- |
| H0 probes | Four hand-run scripts, listed below | Each prints PASS, or names what must be fixed before H2 |
| H1 the bank | Container at `/forge/hopper` on the shell with QA and prod; `users`, `ideas`, `votes`, `promotions`, `events`; the intake endpoint; Board, Submit, Promote; the package and its post to Warp; Warp's "send to Hopper"; seed import with dry run | A promotion appears as a card in Warp's review queue with a complete package. The seed import run twice adds nothing the second time |
| H2 the night | `concepts`, `reviews`, `runs`; preflight; prompt writer with the style file; the runner with its three timing rules; two saved workflows; Gallery; Merge; Nights; morning message | Five shortlisted ideas produce twenty concepts by morning. One round of notes has changed the next night's output |
| H3 the feeds | Scout's export; idea-shaped lines from Warp's meeting pass; Luma intake; reference images fed to Klein; model file hashes on concept rows; upscale, background removal and a 5B teaser for Promoted ideas only; pruning of concept files for ideas parked over 90 days | A Scout finding has entered and been voted on like any other idea. A promoted idea with picked concepts has been accepted in Warp. Landing in Plane is Warp's proof, not Hopper's |
| H4 the public door (parked) | The form, the `inbox` table, moderation as a Board filter, the credit checkbox | Not scheduled. Needs the monthly post to have drawn replies, and the lawyer's terms |

The four probes, run in one sitting before any page exists:

1. From a Windows script beside ComfyUI, post one `hopper`-tagged job to ComfyUI on localhost using a saved API workflow. The image lands in the concept folder, and the script reports the result to Hopper's API.
2. Start a person-style job first, then the probe job. The probe queues behind it, and the run-window watcher leaves it alone.
3. From the same script, the local prompt writer returns four schema-valid prompts for each of three sample ideas using a draft style file. One sample names a third-party character and comes back stripped.
4. Warp QA accepts a sample package and shows it as a card. Warp's "send to Hopper" posts to a test URL.

Before H2's first night, two things only people can do: Jeremy or Josh write the house style file and four example prompt pairs, and one of them bakes and exports the two workflows (Qwen-Image Turbo, Klein 4B) from graphs already running on the box.

Acceptance tests that ship with their slice, each a named test in the suite:

- A second vote by the same person removes the first; it never adds.
- An exact duplicate of a team idea is refused with a link; a Scout or public twin is accepted.
- A promotion row cannot be updated or deleted.
- A promotion with zero concepts writes a valid package, and the confirm says "No concepts attached."
- Merge folds a shared voter once.
- A package is posted to Warp exactly once across retries and restarts.
- An email not on the roster gets the closed door on every route, including the intake endpoint.
- The runner starts nothing after 5 AM and stops waiting at 2 AM.
- A failed preflight writes a `skipped` run that names the check, and queues nothing.
- A parked idea is never picked by the runner.
- QA never posts to ComfyUI.
- A stripped mark is recorded on the concept row and shown in the Gallery.

Proposed order against the calendar, for Jeremy and Grok to rule on: Grok round this week; H0 probes on any evening; H1 built as soon as the rulings are folded in. H1 uses no GPU and pages nobody, so its first prod day does not have to wait for Dec 1. H2's first night comes after Cyber Monday, and not on the same night as Scout's first run.

## Open operator calls

Ten things only Jeremy can answer. The first three are the ticks v0.3 has been waiting on since Sept 22; ticking them freezes doctrine.

- [ ] **Tick 1, doctrine 10.** "Wrong in public, quiet in private; never the reverse. Names are kept so an act can be attributed. Names are not a view."
- [ ] **Tick 2, GPU at 10 PM.** Queue behind a person's job, give up at 2 AM, start nothing after 5 AM.
- [ ] **Tick 3, credit line.** No individual name on a product by default. The public form gets a "credit this name if we make it" checkbox.
- [ ] **Roster.** The rows in `users` on day one, with each person's sign-in email.
- [ ] **Morning message.** v0.3 said a Signal group of four with no contractors in it, but two of the four it named are contractors. Proposed: an email from the shared Forge sender to roster members who want it, until Cue takes over.
- [ ] **Lanes.** Apparel, Content, Story. Still the right three?
- [ ] **Starting numbers.** Shortlist bar, N = 5, 4 prompts per idea, 14-day half-life. Grok proposes a bar of 2.0. With a 14-day half-life, two votes cast the same day sum to about 1.95, so 2.0 means three voters in practice; 1.5 would mean two.
- [ ] **Night 0 owners.** Who writes the house style file and the four example prompt pairs, and who bakes the two workflows?
- [ ] **Concept folder.** The path on the large drive where concept images live.
- [ ] **Order.** Hopper H1 first, with Scout S1 right behind. Or the reverse?

## Grok review 1 (Nov 19)

Grok ruled v0.4 buildable as written: 12 FINE, 4 SHOULD, no MUST. First thing to build is the H0 probes, then H1. The three ticks are still open and still freeze doctrine.

| # | Item | Ruling | What changed in this doc |
| --- | --- | --- | --- |
| 1 | Roster instead of four names; promotion to Warp's review queue | FINE | Nothing |
| 2 | Warp handoff in H1 | FINE | Nothing |
| 3 | One intake endpoint | FINE, with a hole: a service on forge-net could submit as a roster member | Intake doors: each service has its own key and its own system name, and may not submit as a person |
| 4 | Runner in the container reaching the Windows host by IP | SHOULD: a small Windows-side runner beside ComfyUI breaks less | Adopted. The overnight runner section and probes 1 to 3 are rewritten around a Windows-side runner |
| 5 | QA never queues GPU work | FINE | Nothing. A one-image smoke job stays optional |
| 6 | `runs` and `events` tables | FINE | Nothing |
| 7 | Package posted once, retried from disk | FINE. Breaks if Warp's intake format changes or the package path moves | Probe 4 already pins the format; the package path is under the backed-up data folder |
| 8 | Concept images not backed up | SHOULD: only if style file, seed and model file name are recorded from day one | `style_file_hash` added to `concepts` |
| 9 | `/health` block and warn lists | FINE | Nothing |
| 10 | H1 as one batch | SHOULD: cut Merge if unused | Merge moves to H2, where v0.3 had it |
| 11 | Starting shortlist bar | 2.0 | Recorded in Open calls with the arithmetic; Jeremy's number to set |
| 12 | Twelve Scout findings against top 5 | FINE as the whole flood guard | Nothing |
| 13 | Morning message | SHOULD: opt-in email from the shared Forge sender; no Signal group with contractors | Matches the proposal. Still Jeremy's tick |
| 14 | H1's first prod day before Dec 1 | FINE | Nothing |
| 15 | Hopper H1, then Scout S1; H2's night after Cyber Monday | FINE | Nothing |
| 16 | Gates and the one cut | Every roster member submits and votes from their own phone; one promotion lands in Warp complete. Cut: Merge | Merge cut as above. The own-device gate was removed on Nov 21: a human act is not a gate |

From Grok's context round, adopted:

- Three lanes are right for day one. Labs content, collabs, Threadlink and games have no home in Hopper yet and are not forced into Content.
- A fifth refusal joins the list: paid-ad copy variants belong in Amp, not on the Board.
- The five views are the right size. Nothing is added to them.

Not adopted, and why:

- **Grok's Apparel seed list.** Most of it is products already on sale (Baked, Dragon, the Medusa hoodie). Hopper holds things not yet made. The seed import stays what the spec says: Josh's notes, Steph's list and the unmade ideas from our own history.
- **"Free-shipping threshold callouts" as an Apparel idea.** That is ad copy, which Grok's own refusal list sends to Amp.
- **Three details I cannot find in our chats:** a Squatch Mode "Independent" design, an embroidered footprint cap, and zip or cropped hoodies. Grok marked them as from history. Jeremy to confirm before any of them is seeded.

## Grok review 2 (Nov 19, evening)

Grok read the folded doc and confirmed it with no new rulings: every adoption matches, the three rejections stand, and frozen doctrine is untouched. The spec is ready to freeze on Jeremy's ticks. Build order is unchanged: H0 probes on the Windows side, then H1.

Note, Nov 21: that review covers the doc as it stood on Nov 19. The Nov 21 fold of the architect-run round 1 rulings has not been reviewed by Grok, and this spec is not frozen.
