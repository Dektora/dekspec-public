"""Exact language comparison over the IB-176 O-9 path universe.

Regex bodies are lowered to Thompson NFAs. Each edge carries Unicode intervals.
All interval endpoints (including the universe predicates) partition Unicode
into finitely many classes; every character in a class has identical behavior.
A breadth-first traversal of the two subset automata and the universe DFA
therefore decides equality for ALL paths, including arbitrarily deep paths.
Resource exhaustion raises ProofLimit; it is never evidence of equivalence.

Only the small regex subset emitted by this package is accepted. The stdlib
regex parser is private, so unknown operations fail closed, rather than being
silently ignored if Python changes its representation.
"""

from __future__ import annotations

import re
from collections import deque
from functools import lru_cache
from re import _parser as parser

MAX_CODEPOINT = 0x10FFFF
ALL = ((0, MAX_CODEPOINT),)


class ProofLimit(ValueError):
    """No proof was established within the supported language/resource bounds."""


def _complement(ranges):
    out, start = [], 0
    for low, high in sorted(ranges):
        if start < low:
            out.append((start, low - 1))
        start = max(start, high + 1)
    if start <= MAX_CODEPOINT:
        out.append((start, MAX_CODEPOINT))
    return tuple(out)


def _without_slash(ranges):
    return tuple(
        interval
        for low, high in ranges
        for interval in ((low, min(high, 46)), (max(low, 48), high))
        if interval[0] <= interval[1]
    )


def _charset(op, value):
    name = str(op)
    if name == "LITERAL":
        return ((value, value),)
    if name == "NOT_LITERAL":
        return _complement(((value, value),))
    if name == "ANY":
        # All regex dots are DOTALL here. Components' non-DOTALL dot differs
        # only on newline, which the universe rejects everywhere.
        return ALL
    if name == "IN":
        ranges, negate = [], False
        for item, arg in value:
            if str(item) == "NEGATE":
                negate = True
            elif str(item) == "LITERAL":
                ranges.append((arg, arg))
            elif str(item) == "RANGE":
                ranges.append(tuple(arg))
            else:
                raise ProofLimit(f"Unsupported class operation: {item}")
        return _complement(ranges) if negate else tuple(ranges)
    raise ProofLimit(f"Unsupported character operation: {op}")


class _NFA:
    def __init__(self, expressions):
        self.edges = []
        self.epsilon = []
        self.start = self.state()
        self.end = self.state()
        for expression in expressions:
            self.sequence(parser.parse(expression, re.DOTALL), self.start, self.end)

    def state(self):
        if len(self.edges) >= 4096:
            raise ProofLimit("Pattern exceeds the 4096-state NFA proof limit")
        self.edges.append([])
        self.epsilon.append([])
        return len(self.edges) - 1

    def sequence(self, sequence, start, end):
        current, no_slash = start, False
        for op, value in sequence:
            name = str(op)
            if name == "FAILURE":
                return
            if name == "ASSERT_NOT":
                direction, body = value
                if direction != 1:
                    raise ProofLimit("Unsupported lookbehind")
                if not body:  # fnmatch's impossible range, e.g. [z-a]
                    return
                if [(str(o), v) for o, v in body] != [("LITERAL", ord("/"))]:
                    raise ProofLimit("Unsupported lookahead")
                no_slash = True
                continue
            target = self.state()
            if name in {"LITERAL", "NOT_LITERAL", "ANY", "IN"}:
                ranges = _charset(op, value)
                self.edges[current].append((_without_slash(ranges) if no_slash else ranges, target))
            else:
                if no_slash:
                    raise ProofLimit("A class guard must precede one character")
                if name == "SUBPATTERN":
                    _, add_flags, del_flags, body = value
                    if add_flags or del_flags:
                        raise ProofLimit("Unsupported inline flags")
                    self.sequence(body, current, target)
                elif name == "BRANCH":
                    for branch in value[1]:
                        self.sequence(branch, current, target)
                elif name in {"MAX_REPEAT", "MIN_REPEAT"}:
                    minimum, maximum, body = value
                    if minimum not in (0, 1) or maximum not in (1, parser.MAXREPEAT):
                        raise ProofLimit("Unsupported repetition")
                    begin, finish = self.state(), self.state()
                    self.epsilon[current].append(begin)
                    self.sequence(body, begin, finish)
                    self.epsilon[finish].append(target)
                    if minimum == 0:
                        self.epsilon[current].append(target)
                    if maximum == parser.MAXREPEAT:
                        self.epsilon[finish].append(begin)
                else:
                    raise ProofLimit(f"Unsupported regex operation: {op}")
            current, no_slash = target, False
        if no_slash:
            raise ProofLimit("Unconsumed class guard")
        self.epsilon[current].append(end)

    def closure(self, states):
        todo = list(states)
        reached = set(todo)
        while todo:
            for target in self.epsilon[todo.pop()]:
                if target not in reached:
                    reached.add(target)
                    todo.append(target)
        return frozenset(reached)


@lru_cache(maxsize=1)
def _universe_boundaries():
    # str.isspace is the authority, including Unicode and control whitespace.
    points = {0, MAX_CODEPOINT + 1}
    for char in "/.\\\n":
        points.update((ord(char), ord(char) + 1))
    previous = False
    for code in range(MAX_CODEPOINT + 1):
        whitespace = chr(code).isspace()
        if whitespace != previous:
            points.add(code)
        previous = whitespace
    return frozenset(points)


@lru_cache(maxsize=4096)
def _universe_step(state, char):
    segment, last_space = state
    if char in "\\\n" or (segment == -1 and char.isspace()):
        return None
    if char == "/":
        return (0, False) if segment == 3 else None
    if char == ".":
        segment = 1 if segment in (-1, 0) else 2 if segment == 1 else 3
    else:
        segment = 3
    return segment, char.isspace()


def _transition(machine):
    """Bounded memo owned by a comparison, never by the captured machine."""
    @lru_cache(maxsize=32768)
    def step(states, code):
        return machine.closure(
            target for state in states for ranges, target in machine.edges[state]
            if any(low <= code <= high for low, high in ranges)
        )
    return step


class Comparison:
    """Reusable old language; prove emptiness and equality with candidate unions."""

    def __init__(self, old):
        self.old = _NFA(old)
        self._left_step = _transition(self.old)

    def equal(self, expressions):
        left, right = self.old, _NFA(expressions)
        boundaries = set(_universe_boundaries())
        for machine in (left, right):
            for edges in machine.edges:
                for ranges, _ in edges:
                    for low, high in ranges:
                        boundaries.update((low, high + 1))
        alphabet = tuple(sorted(boundaries)[:-1])

        lstep, rstep = self._left_step, _transition(right)
        start = (left.closure([left.start]), right.closure([right.start]), (-1, False))
        seen = {start}
        todo = deque([start])
        while todo:
            ls, rs, universe = todo.popleft()
            if universe == (3, False) and ((left.end in ls) != (right.end in rs)):
                return False
            for code in alphabet:
                new_universe = _universe_step(universe, chr(code))
                if new_universe is None:
                    continue
                new_left, new_right = lstep(ls, code), rstep(rs, code)
                if not new_left and not new_right:
                    continue
                target = (new_left, new_right, new_universe)
                if target not in seen:
                    if len(seen) >= 50000:
                        raise ProofLimit("Equivalence exceeds the 50000-state product proof limit")
                    seen.add(target)
                    todo.append(target)
        return True
