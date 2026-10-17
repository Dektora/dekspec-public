<!--
Hides: where each lean rule is defined in DekSpec's specifications and how the engine enforces it; read by a project's owner and coordinator.
Public: the guide `lean-adoption`, printed unchanged in any project by `dekspec resource doc lean-adoption` from the installed release; its sections below, in the order a project acts; the switch as a YAML block to add to `.dekspec/config.yaml`; each `dekspec` or `dekbuilder` command it shows in a fenced line or inline code span, among them `dekspec ib new`, `dekspec ib accept` and `dekspec ib unblock`.
Readers never need DekSpec's rule numbers or file layout: each step gives the exact setting, command or sentence and what it commits the project to; a rule number may follow only as a reference.
Errors designed away: no project keeps a copy, since the guide comes from its installed release; a shown command the release lacks fails the guide's check, naming the line, so none ships. Topic coverage and order are judged by review.
Alternatives: a reference arranged by rule source (exposes where rules live) or a checklist plus a page per topic (several names, order lost); one page of ordered steps won, read top to bottom with nothing else open.
-->

# Switching a project to lean construction

This guide is for a project's owner and its coordinator, the agent that runs construction. Read it top to bottom and act in the order it gives. Every command it shows exists in the release that ships it. Read it again at any time with `dekspec resource doc lean-adoption`; keep no copy of your own, so the guide you read always matches the release you run.

**Lean** is a lighter way to build an Implementation Brief. A brief chooses it with the line `**Authority policy:** lean`. Briefs in the other forms, `delegated` and `legacy`, are built exactly as before, so a project can switch lean on and still build some briefs the old way.

**What lean changes:**

- A brief is one page: its outcome, its scope, its design intent, its acceptance conditions with the tests that prove them, and a first guess at the files. Nothing else is required.
- The acceptance tests are written by a separate test author in the brief's own pull request, as its first commit. They never land on `main` failing, and the red-test check is never lifted to let them.
- A brief's evidence is bound to its own change: its diff, its tests and what steers them, and the specifications it follows. A change elsewhere on `main` does not make it stale.
- Your full test suite runs in CI, on the brief merged with `main`, before the brief lands. It is not one of the brief's acceptance conditions.
- Briefs land one at a time through a queue, and each lands only when that CI run passes.
- A normal-risk brief needs no reference build before acceptance.

**What lean keeps, for every brief:**

- Only the owner approves. Accepting a brief is the approval.
- The test author, the builder and the reviewers are separate agents, each with its own name and its own fresh context.
- Every new acceptance test fails first, on its own assertion, before any code is written for it.
- The builder can neither change an acceptance test nor record a verdict on its own work.
- Nothing completes without tests that ran and passed.
- The execution records are only ever added to, and a stopped run resumes from them.
- Each Intent keeps one outcome test.

(Reference: ADR-079.)

## Two example projects

Two generic projects illustrate the steps. Neither is a real project.

- **Project A:** a TypeScript project with vitest and pnpm and a Postgres service in CI, its builders on another host.
- **Project B:** a small TypeScript project with vitest and pnpm on a self-hosted runner.

Where the two differ, the step says so.

## Before you start

Have each of these in place before you switch lean on.

1. **A release with lean, installed from the public mirror.** Install DekSpec and DekBuilder from the same release tag, 0.130.0 or later. DekBuilder runs the construction, so it is required:

   ```bash
   pipx install "git+https://github.com/Dektora/dekspec-public.git@v0.130.0"
   pipx inject dekspec --include-apps "dekbuilder @ git+https://github.com/Dektora/dekspec-public.git@v0.130.0#subdirectory=products/dekbuilder"
   dekspec sync
   ```

   `dekspec sync` writes `.dekspec-version`. Commit that file: the `lean gate` CI job reads it at the base of each pull request to know which release judges the change.

2. **A test runner lean supports.** Lean supports pytest and vitest. Each acceptance condition of a lean brief names tests of one of them. Both example projects use vitest.

3. **A command that prepares a fresh checkout.** The builder works in a new worktree, and the test author's commit is checked in a clean checkout. Put the command that installs your dependencies under `integration.worktree_setup` in `.dekspec/config.yaml`. For both example projects:

   ```yaml
   integration:
     worktree_setup: pnpm install --frozen-lockfile
   ```

4. **An issue workspace.** When a review loop runs out of rounds with only minor findings open, the brief completes and each open finding is filed as a follow-up issue in `.beads-issues`, with ids starting `<project>-iss-`. If that workspace is missing, the completion is refused. Create it once, with `br` installed, and commit `.beads-issues/`:

   ```bash
   dekspec dependencies install br
   dekspec beads init --project-prefix shop
   ```

   Here `shop` stands for your project's short name.

5. **CI on GitHub where you can require a check.** The `lean gate` job must be a required check on `main`. Project B's job runs on its self-hosted runner; that is enough, as long as GitHub reports the check.

6. **A Constitution and an accepted Intent.** You will change your Constitution's wording (see "Change your Constitution"), and each lean brief hangs from an accepted Intent.

7. **A coordinator that can start fresh agents.** Lean needs four separate agents per brief, started by the coordinator. See "The four workers" for what any host must provide.

## Switch lean on

Add this block to `.dekspec/config.yaml`, keeping the rest of the file as it is:

```yaml
# Lean construction is switched on in this project.
execution:
  lean: true
```

If the file already has an `execution:` block, add the `lean: true` line to it rather than writing a second block. There is no command that sets this switch; edit the file. Land the change on `main` on its own, before your first lean brief. CI reads the switch from the base of each pull request, so a pull request cannot switch lean on for itself. If your CI runs DekSpec's delivery gate, this file counts as code there, and the change needs the independent review your gate asks of any code change that carries no brief.

**What the switch changes:**

- `dekspec ib accept` and `dekspec ib start` take briefs whose policy is `lean`. With the switch off they refuse them.
- `dekspec ib new` writes the lean form by default. Ask for the old form with `--form delegated`.

**What it leaves alone:** every `delegated` and `legacy` brief, accepted or not, keeps its meaning and is built as before. A brief's policy is part of what the owner accepted, so changing the policy of an accepted brief sends it back to PROPOSED for acceptance again. Any value other than `true` means off.

## The four workers, and how the coordinator dispatches them

Four agents build each lean brief, one after another. Each starts fresh, with no memory of the others, under its own name. DekBuilder names them and writes each one's instructions:

| Worker | Its name | What it does |
|---|---|---|
| Test author | `test-author-IB-NNN` | Designs the interface of any new module, writes stub files for it, then writes the acceptance tests. Every new test must fail on its own assertion. |
| Floor reviewer | `floor-reviewer-IB-NNN` | Checks the test author's commit: each test against the condition it proves, and the design of any stub. Records `pass` or `fail`. |
| Builder | `builder-IB-NNN` | Writes the code until the brief's own tests pass. It may fill in the stubs and change no other file the test author wrote. |
| Reviewer | `reviewer-IB-NNN` | Reviews the finished change against the brief and records `pass` or `fail`. |

The test author and the floor reviewer are new with lean; the builder and the reviewer are the workers you already have. The four names must stay different, and no agent may play two parts for one brief: the builder is never the test author, and the agent that judged a brief's tests never reviews its code. DekSpec refuses a verdict or record that breaks this.

**The order never changes:** the test author writes the tests, and DekBuilder commits them as one commit; the floor reviewer judges that commit; only after it passes does the builder start; the brief's own tests run; the reviewer judges the change; the brief completes and joins the landing queue. A failed floor review sends the test author back with the findings. A failed code review sends the builder back. A builder that finds a stub's interface wrong stops and says why; the brief goes back to the test author, at most twice, and after that it stops for the owner.

**The coordinator's loop.** Name the Intent, or the briefs, you want built, and ask DekBuilder for the next steps:

```bash
dekbuilder wave next "INT-007" --json
```

For each `dispatch` action in the result, start one fresh agent whose prompt is the action's `prompt`, word for word, with nothing added or removed. When it returns, acknowledge it with the action's `ack_request` and dispatch id:

```bash
dekbuilder implement ack "<ack_request>" --dispatch <id>
```

Call `dekbuilder wave next` again once every worker of the round has returned and been acknowledged, and repeat until nothing is left. `dekbuilder wave status "INT-007"` shows where each brief stands without changing anything. The coordinator never writes tests or code, records a verdict, completes a brief or merges by hand: DekBuilder does every mechanical step, including the commits, the queue, the push and the merge.

A lean brief is built and delivered alone, on its own branch. Its branch is not pushed and its pull request is not opened until it reaches the head of the landing queue. Then CI runs once on the brief merged with `main`, and the brief lands only when the `lean gate` check and every other required check pass. If that run fails, the brief goes back to its builder.

**Hosts.** On any host, the coordinator must be able to start a fresh agent for each dispatch, hand it the prompt unchanged, wait for it to finish, and acknowledge it. The worker runs the `dekspec` commands its prompt gives, under the name its prompt gives. In this release, the coordinator dispatches all four workers through DekBuilder and runs each as its own sub-agent on the coordinator's own host. On Claude Code, `/dekspec:implement INT-007` runs this loop for you; on another host, the coordinator runs the commands above itself. Builders on another host, such as Codex or Amp, are not covered for lean briefs in this release. A project whose builders run on another host, like Project A, keeps building those briefs `delegated` until a later release covers it. It can still switch lean on and build its other briefs lean with the coordinator's own workers.

## Normal risk, and how your project defines it

Every lean brief carries one risk line, and in this release lean accepts only one value:

```text
**Risk:** normal
```

`dekspec ib accept` refuses a lean brief whose risk is `high`, missing or anything else. Write a brief that is not normal risk in the `delegated` form; it is built the old way, with its tests prepared, reviewed and proved before acceptance. The owner approves each brief's risk level when he accepts the brief: accepting a brief with `**Risk:** normal` is his approval that it is normal risk. The `/dekspec:write-ibs` skill asks the owner to approve each brief's level before it writes the brief.

Write your project's own definition in its Constitution, Article 5 (Development Workflow). A starting definition to adapt:

> **Risk of a brief.** A brief is high risk when it changes how this project's own work is judged: its CI workflows and required checks, its test configuration and test setup files, or its DekSpec settings in `.dekspec/config.yaml`. It is also high risk when it touches authentication and permissions, payments and money, or data migrations. Every other brief is normal risk. Only a normal-risk brief is written lean. The owner approves each brief's risk level when he accepts it.

Replace the three examples in the second sentence with your project's own dangerous areas.

## Change your Constitution

Your Constitution may still require things lean removes, and it does not yet say what lean adds. Change it in the same pull request as the switch, or before it. The sample wording below is a starting point; put each line in the article that already covers the subject, usually Article 3 (Quality Standards) or Article 5 (Development Workflow).

**Remove, or limit to briefs that are not lean:**

1. *Tests landing failing on `main`, with the red-test check lifted meanwhile.* Replace it with:
   > A lean brief's acceptance tests are written in the brief's own pull request, as the test author's first commit. They never land on `main` failing, and the red-test check is never lifted for them.
2. *A scratch reference build before acceptance.* Replace it with:
   > A normal-risk lean brief is accepted without a reference build. Its new tests are shown to fail on their own assertions at the test author's commit, and to pass at the builder's.
3. *Floor-review rows in each brief.* Replace it with:
   > A lean brief carries no floor-review rows. The floor reviewer's verdict is kept in the brief's execution record.
4. *Acceptance commands that run the whole suite.* Replace it with:
   > A lean brief's acceptance conditions name its own tests. The full suite runs in CI, on the brief merged with `main`, before the brief lands; it is never an acceptance condition.

**Add:**

1. *A required `lean gate` check.*
   > The CI check `lean gate` is required on `main`. A pull request without a passing `lean gate` never lands.
2. *The owner approves each brief's risk level.*
   > The owner approves each brief's risk level by accepting the brief. Only a normal-risk brief is written lean, by the definition of risk in Article 5.
3. *Four separate identities.*
   > Each lean brief is built by four separate agents, test author, floor reviewer, builder and reviewer, each in its own fresh context and under its own name. No agent takes two of these parts for one brief.

If your Constitution says that no CI runs off your own machines, as Project B's might, say instead that the `lean gate` job runs on your self-hosted runner and is reported to GitHub as a required check.

## Make the `lean gate` check required

The job you need is on its own page, shipped with this release:

```bash
dekspec resource doc lean-gate-ci
```

That page holds a complete GitHub Actions job named `lean gate` and says what to change in it. In short:

1. Copy the job into a workflow file of your project, such as `.github/workflows/lean-gate.yml`.
2. Change the parts the page marks as yours: the runner line, the language setup and the services your tests need. Project A adds its Postgres service there; Project B sets the runner line to its self-hosted runner. The job needs your runner, dependencies and services because it runs the brief's tests at the test author's commit.
3. Leave the judging step exactly as it is. It installs the DekSpec release named by `.dekspec-version` at the pull request's base and judges with that release only, so a pull request cannot change its own judge.
4. Make `lean gate` a required check on `main`, under exactly that name, in your branch protection or ruleset. DekBuilder lands a lean brief only when this check is reported on its pull request and passed; a missing `lean gate` is never a pass.

The job passes every pull request that delivers no lean brief. It also passes, printing `judge predates lean`, while the release at the base has no lean support.

## Review loops: findings, rounds, and when work moves on

Both reviews of a lean brief, the floor review of its tests and the code review of its change, run in loops of rounds, with the same rules.

**Findings and their level.** A reviewer that records `fail` lists each finding that fails the review, with its level: `P1` or `P2`. Anything else goes in its notes and fails nothing. A code-review finding fails the review only when the reviewer is at least 80% confident it is real. It is `P1` when the code behaves wrongly against the brief or its rules, risks security or the loss of data, or breaks one of lean's guarantees; otherwise it is `P2`. A `fail` with no finding listed counts as one `P1`.

**Rounds.** Each failed review sends the work back: the tests to the test author, the code to the builder. The next review is a new round. From round 2 the reviewer is given the earlier rounds' findings and the changes since the last review, and judges whether each finding is fixed, whether a fix broke anything, and the changed lines.

**The limit: five rounds, and one more.** When round 6 fails:

- **With only `P2` findings open,** the loop has ended and the work moves on: an ended floor loop lets the builder start, and an ended code-review loop lets the brief complete. At completion each open finding is filed as a follow-up issue in your project's issue workspace, `.beads-issues`, naming the brief, the loop and the finding, and is recorded with the completion as a known issue. If an issue cannot be filed, the completion is refused and nothing is recorded.
- **With any `P1` finding open,** the loop stops for the owner, naming each `P1` finding. The brief stays stopped until the owner records a decision:

  ```bash
  dekspec ib unblock IB-012 --decision "Rework the discount rounding as the finding says"
  ```

  The decision starts a new loop. The brief's own tests, the red-test check and the test-file guard are never relaxed.

## Write your first lean brief

1. **Create it from the lean form.** With lean switched on, `dekspec ib new` writes a lean brief with the next free number. Give it a short name and its Intent, and name your runner when it is not pytest:

   ```bash
   dekspec ib new order-discount --parent INT-007 --runner vitest
   ```

   It writes `dekspec/impl-briefs/IB-012-order-discount.md` (your number will differ) with `**Authority policy:** lean` and `**Risk:** normal`. The examples below use `IB-012`.

2. **Fill in each section, and add or remove none.** Replace each placeholder with your text and keep the comments.
   - **Outcome:** what is true when the brief is done, as a result, not a task list. For example: "An order with two discounts is charged the total the pricing table gives."
   - **Scope:** the files and folders the change may touch, as patterns from the repository root, one per line, such as `src/orders/**`.
   - **Design intent:** for each new module, and each public interface the brief changes, say in a few lines what it hides, what callers need from it, and what callers must never need to know. Name the module by its path, and give no function names or signatures: the test author designs those. For example: "`src/orders/discount.ts` hides how discounts combine and round. Callers need the amount to charge. They never need to know the rounding rule or the order in which discounts apply." When the brief adds no module and changes no public interface, write `None.`
   - **Acceptance:** each condition says what can be observed, and names the tests that prove it. Name tests of your runner only. A condition must not be a command that runs your whole suite or your integration command; CI runs those. A condition judged by the reviewer instead of a test is allowed beside them, but at least one condition must name tests. For vitest, name a test file, which names every test in it, or one test in it by its full name as vitest reports it:

     ```yaml
     - id: AC-1
       condition: "An order with two discounts is charged the total the pricing table gives."
       verify:
         vitest: ["src/orders/discount.test.ts"]
     ```

     The test file need not exist yet. The test author writes it.
   - **Implementation Hypothesis:** a first guess at the files to change. The builder may change it within the scope.

   Aim for one page. Add a section such as Open Issues or Out of scope only when the brief needs it.

3. **Check it, propose it, and have the owner accept it:**

   ```bash
   dekspec validate dekspec/impl-briefs/IB-012-order-discount.md
   dekspec ib lint IB-012
   dekspec ib propose IB-012
   dekspec ib accept IB-012
   ```

   `dekspec ib accept` is the owner's approval of the brief, its design intent and its risk level. It refuses a lean brief while lean is off, when its risk is not `normal`, when it has no Design intent section, or when no condition names tests of a supported runner, and it says which.

4. **Build it.** Run the coordinator's loop for the Intent, `dekbuilder wave next "INT-007" --json`, as "The four workers" shows. The first dispatch is the test author's.

To write a brief in the old form instead, for a brief that is not normal risk, run `dekspec ib new tidy-errors --parent INT-007 --form delegated`.
