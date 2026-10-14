"""Attribute carried units from record receipts, without supplying authority.

Receipts establish only original membership and Git boundaries. All acceptance,
review, baseline and integration decisions still belong to the final candidate.
A single unit keeps the existing working-tree scope semantics.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
import subprocess
from typing import Any

from dekspec.execution.history import record_versions
from dekspec.execution.record import EXECUTION_DIRNAME
from dekspec.execution.scope import (
    ScopeError, ScopeReport, _git, anchor_in_history, changed_files, evaluate_scope,
    predates_run, resolve_base,
)


@dataclass
class Attribution:
    base: str
    ranges: list[dict[str, Any]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    reports: dict[str, ScopeReport] = field(default_factory=dict)

    def scope_for(self, ident):
        """One constituent's scope result, plus candidate-wide proof failures."""
        if not self.ranges and not self.problems:
            return None
        report = deepcopy(self.reports.get(ident, ScopeReport(self.base)))
        report.ranges = self.ranges
        report.base = self.base
        if self.problems:
            # Invalid attribution cannot isolate a sibling's protections.
            # Keep every observed protection refusal visible while the
            # candidate-wide provenance errors continue to deny eligibility.
            for sibling, scope in self.reports.items():
                if sibling != ident:
                    report.violations.extend(deepcopy(v) for v in scope.violations
                                             if v.get('kind') == 'protected-surface')
        report.violations.extend({'kind': 'range-attribution', 'ib': ident, 'detail': p}
                                 for p in self.problems)
        return report

    @property
    def binding(self):
        return self.ranges


def _ancestor(root, before, after):
    return bool(before and after) and not _git(
        root, 'rev-list', '--max-count=1', before, '--not', after).strip()


def _corroborated_receipts(engine, ident, states):
    """Receipts prove a unit only when recorded starts corroborate selection.

    A diagnostic subset can have a perfectly intact receipt but cannot split
    concurrently started work. Keep such receipts in history without using
    them as boundaries; a later joint receipt can still establish the unit.
    """
    root = engine.repo_root
    starts = {i: next((e for e in events if e.type == 'run.started'), None)
              for i, (_, events, _) in states.items()}
    committed = _git(root, 'show', f'HEAD:{EXECUTION_DIRNAME}/{ident}/record.jsonl', check=False)
    for event in states[ident][1]:
        if (event.type != 'evidence.recorded' or event.data.get('kind') != 'delivery'
                or event.data.get('overall') != 'passed'):
            continue
        candidate = _receipt_range(engine, event, ident)
        if candidate is None:
            continue
        members = candidate['ibs']
        boundary, head = candidate['base_commit'], candidate['head_commit']
        if event.data.get('ranges'):
            # A composed receipt may close its then-open unit, but cannot
            # redefine an already proved one. Require its exact run-start
            # references and committed receipt, not caller-selected membership.
            if event.hash not in committed or not set(members) <= set(event.data.get('ibs', [])):
                continue
            if any(not starts.get(i) or not any(
                    s.get('record') == f'{EXECUTION_DIRNAME}/{i}/record.jsonl'
                    and s.get('seq') == starts[i].seq and s.get('hash') == starts[i].hash
                    and s.get('revision') == starts[i].data.get('commit')
                    for s in candidate.get('sources', [])) for i in members):
                continue
        # Malformed/rewritten OIDs are diagnosed by the normal range validator.
        # They cannot establish that a concurrent peer lies outside the unit.
        if not boundary or not head or not all(anchor_in_history(root, oid) for oid in (boundary, head)):
            yield event, candidate
            continue
        if any(not starts[i]
               or not anchor_in_history(root, starts[i].data.get('base_commit'))
               or not _ancestor(root, starts[i].data.get('base_commit'), boundary)
               or not anchor_in_history(root, starts[i].data.get('commit'))
               or not _ancestor(root, starts[i].data.get('commit'), head)
               for i in members if i in starts):
            continue
        if any(i not in members and start
               and any(_same_unit_start(root, start, starts[m].data.get('base_commit'), head)
                       for m in members if m in starts and starts[m])
               for i, start in starts.items()):
            continue
        yield event, candidate


def _receipt_range(engine, event, ident):
    if not event.data.get('ranges'):
        return {'ibs': event.data.get('ibs', []), 'base_commit': event.data.get('base_commit'),
                'head_commit': event.data.get('commit')}
    return next((r for r in event.data['ranges'] if ident in r['ibs']
                 and _record_only_between(engine, r['head_commit'], event.data.get('commit'))), None)


def _record_only_between(engine, before, after):
    """A receipt can follow its content head only through lifecycle changes.

    Check every edge, not the net diff: an implementation edit and its revert
    cannot masquerade as bookkeeping. Merged side history is included too.
    """
    root = engine.repo_root
    if not all(anchor_in_history(root, oid) for oid in (before, after)):
        return False
    if before == after:
        return True
    if not _ancestor(root, before, after):
        return False
    contracts = [engine.contract(i) for i in engine.delivery_ibs()]
    for commit in _git(root, 'rev-list', f'{before}..{after}').split():
        try:
            edges = _commit_edges(root, commit)
        except ScopeError:
            return False
        for parent, end, changes in edges:
            report = evaluate_scope(root, contracts, base=parent, end=end, changes=changes,
                                    check_impact=False, spec_root=engine.spec_root)
            allowed = set(report.exempt + report.bookkeeping)
            if report.violations or any(p not in allowed for c in changes
                                        for p in (c.path, c.old_path) if p):
                return False
    return True


def _unit_receipt(root, ident, start, histories):
    """Keep original membership while allowing that unit's proved head to advance.

    A joint diagnostic after an unfinished side was merged cannot turn the
    side into a range overlapping an earlier proof. Its own receipt is needed.
    """
    first = latest = None
    for event, candidate in histories[ident]:
        peers = [histories[p][0][1] for p in candidate['ibs']
                 if p != ident and histories.get(p)]
        if start and any(ident not in peer['ibs']
                         and not _ancestor(root, start.data.get('commit'), peer['head_commit'])
                         and not _ancestor(root, peer['head_commit'], start.data.get('commit'))
                         for peer in peers):
            continue
        key = (tuple(sorted(candidate['ibs'])), candidate['base_commit'])
        if first is None:
            first = key
        if key == first:
            latest = event, candidate
    return latest


def _same_unit_start(root, start, boundary, head):
    """A diagnostic cannot split concurrent work or a same-base continuation.

    Include the base itself: /implement authorizes and starts there. A later
    start that still reaches back across this receipt is also part of the
    unfinished unit, rather than proof of an overlapping independent range.
    Starts on independent side histories remain eligible for range validation.
    """
    commit = start.data.get('commit')
    if not anchor_in_history(root, commit):
        return False
    if _ancestor(root, boundary, commit) and _ancestor(root, commit, head):
        return True
    start_base = start.data.get('base_commit')
    return (anchor_in_history(root, start_base)
            and _ancestor(root, start_base, boundary)
            and _ancestor(root, head, commit))


def resolve_ranges(engine, base=None, *, closing=()) -> Attribution:
    """Resolve and validate all carried units, including unowned history.

    The earliest start-corroborated receipt fixes membership; subsequent
    composed receipts cannot rewrite it. A new active unit can instead use its
    recorded start base. Missing old metadata never invents a split.
    """
    root = engine.repo_root
    actual = resolve_base(root, base or engine.base)
    result = Attribution(actual)
    ids = engine.delivery_ibs(base)
    active = [i for i in ids if engine.contract(i).status not in {'DEPRECATED', 'SUPERSEDED'}]
    from dekspec.execution.engine import ExecutionError

    states = {}
    for ident in active:
        try:
            states[ident] = engine.state(ident)
        except ExecutionError as exc:
            result.problems.append(f'{ident}: range record is unreadable: {exc}; restore intact history')
    if result.problems:
        return result
    histories = {i: list(_corroborated_receipts(engine, i, states)) for i in states}
    units = {}
    for ident, (_, events, st) in states.items():
        start = next((e for e in events if e.type == 'run.started'), None)
        selected = _unit_receipt(root, ident, start, histories)
        receipt = None
        if selected:
            receipt, candidate = selected
            members = tuple(sorted(candidate['ibs']))
            boundary = candidate['base_commit']
            head = candidate['head_commit']
        else:
            members = ()
            boundary = start.data.get('base_commit') if start else None
            head = None
        # Missing metadata is the original same-unit case, never a split proof.
        key = (members, boundary) if members else ((), boundary)
        unit = units.setdefault(key, {'ibs': [], 'base_commit': boundary, 'head_commit': head,
                                      'sources': [], '_receipts': []})
        unit['ibs'].append(ident)
        if receipt:
            unit['_receipts'].append((ident, receipt, candidate))
            if unit['head_commit'] != head:
                result.problems.append(f'{ident}: contradictory range head receipts; restore original unit history')
    # A moved base between starts is not proof of separate deliveries. Until
    # a delivery receipt establishes a constituent, all unfinished IBs retain
    # the existing same-unit scope rules (including partial-merge recovery).
    if len(units) <= 1 or not any(unit['_receipts'] for unit in units.values()):
        return result

    if _git(root, 'for-each-ref', '--format=%(refname)', 'refs/replace').strip():
        result.problems.append('range provenance is ambiguous with replacement objects; restore original Git history')
    grafts = Path(_git(root, 'rev-parse', '--git-path', 'info/grafts').strip())
    if not grafts.is_absolute():
        grafts = root / grafts
    if grafts.exists() and grafts.read_bytes().strip():
        result.problems.append('range provenance is ambiguous with graft metadata; restore original Git history')

    # Several independent receipts must describe disjoint, complete membership.
    for (members, _), unit in units.items():
        own = unit['ibs']
        if members and set(members) != set(own):
            result.problems.append(f'{own}: range membership {members} conflicts with carried IBs; restore all records')
        boundary = unit['base_commit']
        head = unit['head_commit']
        for ident in own:
            _, events, st = states[ident]
            anchor = (st.pre_execution_baseline or {}).get('commit')
            start = next((e for e in events if e.type == 'run.started'), None)
            for label, oid in [('base', boundary), ('authorization anchor', anchor),
                               ('run anchor', start.data.get('commit') if start else None),
                               *([('head', head)] if head else [])]:
                if not anchor_in_history(root, oid):
                    result.problems.append(f'{ident}: range {label} {oid} is missing or nonancestor; restore original history')
            if head and anchor_in_history(root, anchor) and anchor_in_history(root, head) and not _ancestor(root, anchor, head):
                result.problems.append(f'{ident}: range head precedes authorization anchor; restore boundaries')
        if boundary and head and anchor_in_history(root, boundary) and anchor_in_history(root, head):
            if not _ancestor(root, boundary, head):
                result.problems.append(f'{own}: range base is not an ancestor of its head; restore boundaries')
        for ident, receipt, candidate in unit['_receipts']:
            rel = f'{EXECUTION_DIRNAME}/{ident}/record.jsonl'
            current = engine.record(ident).path.read_text(encoding='utf-8')
            versions = record_versions(root, rel, actual)
            if any(not current.startswith(text) for _, text in versions):
                result.problems.append(f'{ident}: range record history was rewritten; restore its append-only record')
            sources = [(revision, text) for revision, text in versions
                       if receipt.hash in text and current.startswith(text)]
            refs = {**receipt.data.get('executed', {}), **receipt.data.get('relies_on', {})}
            for member in own:
                reference = refs.get(member, {})
                evidence = next((e for e in states[member][1]
                                 if e.seq == reference.get('seq') and e.hash == reference.get('hash')
                                 and e.type == 'evidence.recorded' and e.data.get('kind', 'ib') == 'ib'), None)
                if (evidence is None or reference.get('record') != member
                        or not anchor_in_history(root, evidence.data.get('commit'))
                        or not _ancestor(root, evidence.data.get('commit'), receipt.data.get('commit'))
                        or evidence.data.get('fingerprint') != receipt.data.get('fingerprint')
                        or (evidence.data.get('scope') or {}).get('base') != receipt.data.get('base_commit')):
                    result.problems.append(f'{member}: range receipt does not bind its original verification; restore source references')
            if not sources:
                result.problems.append(f'{ident}: range receipt #{receipt.seq} lacks committed provenance; commit original records')
            else:
                revision, _ = sources[-1]
                if receipt.data.get('ranges'):
                    # Preserve the corroborated start references when the first
                    # composed receipt is committed; that commit adds no authority.
                    unit['sources'].extend(s for s in candidate['sources']
                                           if s not in unit['sources'])
                else:
                    unit['sources'].append({'record': rel, 'seq': receipt.seq, 'hash': receipt.hash,
                                            'revision': revision})
        if not head:
            # An unfinished last unit is bounded by its recorded start base and
            # today's candidate. It cannot absorb any earlier constituent.
            unit['head_commit'] = _git(root, 'rev-parse', 'HEAD').strip()
            unit['_open'] = True
            for ident in own:
                start = next((e for e in states[ident][1] if e.type == 'run.started'), None)
                if start is None:
                    continue
                unit['sources'].append({'record': f'{EXECUTION_DIRNAME}/{ident}/record.jsonl',
                                        'seq': start.seq, 'hash': start.hash,
                                        'revision': start.data.get('commit')})
        result.ranges.append({k: v for k, v in unit.items() if not k.startswith('_')})
    if result.problems:
        return result

    claimed = {}
    for number, unit in enumerate(units.values()):
        excluded = [actual, unit['base_commit']]
        starts = [next(e for e in states[i][1] if e.type == 'run.started').data['commit']
                  for i in unit['ibs']]
        unit['_starts'] = starts
        for previous in units.values():
            if previous is unit or not previous['_receipts']:
                continue
            prior_head = previous['head_commit']
            # A start after a proved delivery can carry that delivery's history
            # even when its recorded base is main. A boundary cutting through
            # that delivery remains contradictory, not an ownership exclusion.
            if (all(_ancestor(root, prior_head, start) for start in starts)
                    and (_ancestor(root, unit['base_commit'], actual)
                         or _ancestor(root, prior_head, unit['base_commit']))):
                excluded.append(prior_head)
        commits = _git(root, 'rev-list', '--reverse', '--topo-order', unit['head_commit'],
                       '--not', *excluded).split()
        unit['_commits'] = commits
        for commit in commits:
            claimed.setdefault(commit, []).append(number)

    # Once a receipt proves membership, an unproved side cannot erase it.
    # Its provisional candidate head may overlap that range; the ordinary
    # ownership checks below must refuse that overlap with recovery guidance.
    # Same-unit fallback is confined to the no-proof case above.
    unit_list = list(units.values())
    _extend_active_tails(engine, unit_list, states, claimed, actual, closing)
    result.ranges = [{k: v for k, v in unit.items() if not k.startswith('_')}
                     for unit in unit_list]

    # One traversal owns reconstruction and diagnostics. Reuse immutable Git
    # edges within this resolution, never across changed candidates/config.
    edge_cache = {}

    def commit_edges(commit):
        if commit not in edge_cache:
            try:
                edge_cache[commit] = _commit_edges(root, commit)
            except ScopeError as exc:
                result.problems.append(str(exc))
                edge_cache[commit] = []
        return edge_cache[commit]

    shared_preparation = {}
    owned_paths = set()
    for number, unit in enumerate(units.values()):
        boundary, head = unit['base_commit'], unit['head_commit']
        commits = unit['_commits']
        edges = []
        for commit in commits:
            edges.extend(commit_edges(commit))
        if unit.get('_open'):
            edges.extend((head, end, changed_files(root, head, end)) for end in (None, ''))
        owned_paths.update(p for _, _, changes in edges for c in changes
                           for p in (c.path, c.old_path) if p)
        contracts = [engine.contract(i) for i in unit['ibs']]
        for ident in unit['ibs']:
            st = states[ident][2]
            anchor = (st.pre_execution_baseline or {}).get('commit')
            preparation_commits, preparation_paths = _preparation(
                root, commits, edges, anchor, boundary, actual, engine.spec_root)
            report = _range_scope(engine, contracts, edges, boundary,
                                  None if unit.get('_open') else head)
            for parent, commit, changes in edges:
                edge = evaluate_scope(root, contracts, base=parent, end=commit, changes=changes,
                                      pre_run_paths=(preparation_paths if commit in preparation_commits
                                                     else frozenset()),
                                      check_impact=False, spec_root=engine.spec_root)
                for field_name in ('violations', 'exempt', 'bookkeeping', 'pre_run',
                                   'unplanned_in_scope', 'notes'):
                    target = getattr(report, field_name)
                    target.extend(v for v in getattr(edge, field_name) if v not in target)
                preparation = set(edge.pre_run + edge.exempt + edge.bookkeeping)
                shared_preparation[(number, commit)] = shared_preparation.get((number, commit), True) and (
                    not edge.violations and all(c.path in preparation for c in changes))
            refused_paths = {v.get('path') for v in report.violations}
            report.pre_run = [p for p in report.pre_run if p not in refused_paths]
            result.reports[ident] = report

    for commit, owners in claimed.items():
        if len(owners) > 1 and not all(shared_preparation.get((owner, commit), False) for owner in owners):
            members = [unit_list[n]['ibs'] for n in owners]
            paths = sorted({p for _, _, changes in commit_edges(commit) for c in changes
                            for p in (c.path, c.old_path) if p})
            result.problems.append(f'range ownership overlaps at {commit} for constituents {members} '
                                   f'on paths {paths}; '
                                   'a recorded boundary cuts another unit or a side unit lacks its own passing receipt. '
                                   'Verify the side unit on its original branch, commit its passing receipt and merge it again; '
                                   'for a boundary cutting another unit, restore the original authorized history')

    # Independent side ranges may share ancestry, but conflicting path content
    # needs an authorized integration resolution, not an ours merge.
    for a, b in combinations(units.values(), 2):
        if _ancestor(root, a['head_commit'], b['head_commit']) or _ancestor(root, b['head_commit'], a['head_commit']):
            continue
        fork = _git(root, 'merge-base', a['head_commit'], b['head_commit']).strip()
        left = {p for c in changed_files(root, fork, a['head_commit']) for p in (c.path, c.old_path) if p}
        right = {p for c in changed_files(root, fork, b['head_commit']) for p in (c.path, c.old_path) if p}
        for path in sorted(left & right):
            if _entry(root, a['head_commit'], path) != _entry(root, b['head_commit'], path):
                result.problems.append(f"{a['ibs']} / {b['ibs']}: conflicting range ownership of {path}; authorize and review the resolution")

    # Outside proved ranges only existing lifecycle bookkeeping is allowed.
    # Every side parent is traversed; merges may carry identical parent bytes.
    contracts = [engine.contract(i) for i in ids]
    for commit in _git(root, 'rev-list', f'{actual}..HEAD').split():
        if commit in claimed:
            continue
        for parent, end, changes in commit_edges(commit):
            _unowned(engine, result, contracts, parent, end, changes)
    if not any(unit.get('_open') for unit in units.values()):
        _unowned(engine, result, contracts, _git(root, 'rev-parse', 'HEAD').strip(), None,
                 changed_files(root, 'HEAD'))
        _unowned(engine, result, contracts, _git(root, 'rev-parse', 'HEAD').strip(), '',
                 changed_files(root, 'HEAD', ''))
    # Backstop the edge traversal against the actual landing-base diff. A
    # carried path must occur in an owned edge or qualify as lifecycle data.
    for end in (None, ''):
        missing = [c for c in changed_files(root, actual, end)
                   if any(p not in owned_paths for p in (c.path, c.old_path) if p)]
        _unowned(engine, result, contracts, actual, end, missing)
    result.problems = list(dict.fromkeys(result.problems))
    return result


def _preparation(root, commits, edges, anchor, boundary, actual, spec_root):
    """Qualify owned preparation at authorization, never at an arbitrary edge.

    Intermediate authoring revisions need not equal the final anchor. Only
    ordinary pre-authorization commits can use its allowance: every merge and
    later edit is judged normally. Both bases must leave the path untouched,
    and this unit must itself have changed it by authorization; an earlier
    constituent's change alone supplies no preparation provenance.
    """
    eligible = {commit for commit in commits if _ancestor(root, commit, anchor)
                and len(_git(root, 'rev-list', '--parents', '-n', '1', commit).split()) == 2}
    origins = {}
    for parent, commit, changes in edges:
        if commit in eligible:
            for change in changes:
                for path in (change.path, change.old_path):
                    if path:
                        origins.setdefault(path, parent)
    paths = frozenset(path for path, origin in origins.items()
                      if _entry(root, origin, path) != _entry(root, anchor, path)
                      and all(predates_run(root, base, anchor, path, spec_root, end=anchor)
                              for base in {boundary, actual}))
    return eligible, paths


def _range_scope(engine, contracts, edges, boundary, end):
    """Net disclosure/impact from owned edges; scope is judged on those edges.

    A single base-to-head diff cannot express a range after main and earlier
    units were merged. For each path compare with the parent before its first
    owned edit. Imported changes never introduce a path into this net, while
    the caller checks even transient edits and each merge resolution.
    """
    origins = {}
    changes = []
    for parent, _, edge_changes in edges:
        for change in edge_changes:
            for path in (change.path, change.old_path):
                if path:
                    origins.setdefault(path, parent)
            if change not in changes:
                changes.append(change)
    changed_at = {parent: {p for c in changed_files(engine.repo_root, parent, end)
                           for p in (c.path, c.old_path) if p}
                  for parent in set(origins.values())}
    net = [c for c in changes if any(p in changed_at[origins[p]]
                                    for p in (c.path, c.old_path) if p)]
    impact = evaluate_scope(engine.repo_root, contracts, base=boundary, end=end,
                            changes=net, spec_root=engine.spec_root)
    return ScopeReport(boundary, changes=net, missing_spec_impact=impact.missing_spec_impact)


def _entry(root, revision, path):
    return _git(root, 'ls-tree', '-z', revision, '--', f':(literal){path}')


def _commit_edges(root, commit):
    """Separate inherited merge content from the merge's own edits.

    Parent equality is not provenance: choosing one parent can discard the
    other's contribution, while a clean textual merge can differ from both.
    Compare to Git's mechanical result; conflicting paths are judged against
    every parent so choosing a side still preserves symbol/path protection.
    """
    parents = _git(root, 'rev-list', '--parents', '-n', '1', commit).split()[1:]
    if len(parents) == 1:
        return [(parents[0], commit, changed_files(root, parents[0], commit))]
    if not parents:
        raise ScopeError(f'range attribution: root commit {commit} has no comparison parent; '
                         'restore connected authorization history')
    left = parents[0]
    conflicts = set()
    for number, right in enumerate(parents[1:], 1):
        merged = subprocess.run(['git', 'merge-tree', '--write-tree', '--name-only', '-z',
                                 left, right], cwd=root, capture_output=True, text=True)
        if merged.returncode not in (0, 1):
            raise ScopeError(f'range attribution: cannot reconstruct merge {commit}: '
                             f'{merged.stderr.strip()}; restore merge provenance')
        parts = merged.stdout.split('\0')
        tree = parts[0]
        if merged.returncode == 1:
            end = parts.index('', 1)
            paths = set(parts[1:end])
            # Directory conflicts need not have unmerged index entries. Add
            # paths from all structured conflict messages, never prose parsing.
            messages = parts[end + 1:]
            while messages and messages[0]:
                count = int(messages[0])
                if messages[count + 1].startswith('CONFLICT'):
                    paths.update(messages[1:count + 1])
                messages = messages[count + 3:]
            if not paths:
                raise ScopeError(f'range attribution: unresolved merge provenance at {commit}; '
                                 'restore a merge with attributable conflict paths')
            conflicts.update(paths)
        if number < len(parents) - 1:
            # An unreachable virtual commit supplies ancestry for the next
            # octopus leg. Like merge-tree's virtual bases, this only writes
            # objects: no ref, index, working file or execution record changes.
            content = (f'tree {tree}\nparent {left}\nparent {right}\n'
                       'author DekSpec <ranges@invalid> 0 +0000\n'
                       'committer DekSpec <ranges@invalid> 0 +0000\n\n'
                       'Mechanical merge comparison\n')
            virtual = subprocess.run(['git', 'hash-object', '-t', 'commit', '-w', '--stdin'],
                                     cwd=root, input=content, capture_output=True, text=True)
            if virtual.returncode:
                raise ScopeError(f'range attribution: cannot reconstruct merge {commit}: '
                                 f'{virtual.stderr.strip()}; restore merge provenance')
            left = virtual.stdout.strip()
    def conflicted(change):
        return any(path == conflict or path.startswith(conflict.rstrip('/') + '/')
                   for path in (change.path, change.old_path) if path for conflict in conflicts)

    edits = changed_files(root, tree, commit)
    edges = [(tree, commit, [c for c in edits
                            if not conflicted(c)])]
    if conflicts:
        for parent in parents:
            edges.append((parent, commit, [c for c in changed_files(root, parent, commit)
                                          if conflicted(c)]))
    return edges


def _extend_active_tails(engine, units, states, claimed, actual, closing):
    """An unfinished unit may repair its unique tail, never a later unit's work.

    Completed units remain closed until explicitly reopened. Receipt-only
    commits do not move the content boundary. Every assigned implementation
    edge is subsequently checked against the owning unit's full contract.
    """
    root = engine.repo_root
    proposals = {}
    for number, unit in enumerate(units):
        if unit.get('_open') or any(i in closing or engine.contract(i).status != 'ACCEPTED'
                                     for i in unit['ibs']):
            continue
        head = unit['head_commit']
        if any(_ancestor(root, head, start) for other in units if other is not unit
               for start in other['_starts']):
            continue
        tail = _git(root, 'rev-list', '--reverse', '--topo-order', 'HEAD',
                    '--not', head, actual).split()
        # A side constituent cannot capture another range's commits. An
        # otherwise unique tail remains its owner's regardless of merge order.
        if any(commit in claimed for commit in tail):
            continue
        for commit in tail:
            proposals.setdefault(commit, []).append(number)
        unit['_open'] = True
        for ident in unit['ibs']:
            start = next(e for e in states[ident][1] if e.type == 'run.started')
            source = {'record': f'{EXECUTION_DIRNAME}/{ident}/record.jsonl',
                      'seq': start.seq, 'hash': start.hash,
                      'revision': start.data.get('commit')}
            if source not in unit['sources']:
                unit['sources'].append(source)
    contracts = [engine.contract(i) for i in states]
    for commit, owners in proposals.items():
        if len(owners) != 1:
            continue
        number = owners[0]
        unit = units[number]
        parent = _git(root, 'rev-parse', f'{commit}^1').strip()
        changes = changed_files(root, parent, commit)
        report = evaluate_scope(root, contracts, base=parent, end=commit, changes=changes,
                                check_impact=False, spec_root=engine.spec_root)
        allowed = set(report.exempt + report.bookkeeping)
        # Merge commits need attribution even if their first-parent diff is
        # empty: an ours merge may have discarded incoming base contributions.
        parents = _git(root, 'rev-list', '--parents', '-n', '1', commit).split()[1:]
        if len(parents) > 1 or any(c.path not in allowed for c in changes):
            unit['_commits'].append(commit)
            unit['head_commit'] = commit
            claimed[commit] = owners


def _unowned(engine, result, contracts, base, end, changes):
    # Evaluate with the real contracts to retain the narrow lifecycle policy,
    # then refuse even in-scope implementation: no range owns this edge.
    report = evaluate_scope(engine.repo_root, contracts, base=base, end=end,
                            changes=changes, check_impact=False, spec_root=engine.spec_root)
    allowed = set(report.exempt + report.bookkeeping)
    for change in changes:
        if change.path not in allowed:
            result.problems.append(f"range attribution: unowned {change.path} after recorded heads at {end or 'working tree'}; drop the offending commit from candidate history (a revert does not remove it), discard an uncommitted edit, or deliver the change under a newly authorized brief, then verify and review the final candidate")
