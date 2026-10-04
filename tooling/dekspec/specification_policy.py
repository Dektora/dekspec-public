"""DekSpec's public policy for using evolving specification references.

Artifact maturity and authorization to execute an IB are separate decisions.
An explicit evolving policy permits PROPOSED ADR/AE sources without changing
those sources' statuses, links, content or lifecycle. Other kinds retain their
existing eligibility rules. Execution clients consume this policy; they do not
own a second readiness-specific version of it.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Collection

from jsonschema import Draft202012Validator
import yaml

from .schemas import load_schema

APPROVED_REFERENCE_STATUSES = frozenset({'ACCEPTED', 'LOCKED', 'COMPLETE', 'ACTIVE'})


class ReferencePolicyError(ValueError):
    """A declared reference policy is malformed or contradictory."""


@dataclass(frozen=True)
class ReferencePolicy:
    mode: str = 'strict'

    def __post_init__(self) -> None:
        if self.mode not in {'strict', 'evolving'}:
            raise ReferencePolicyError(f'Unknown specification.reference_mode: {self.mode!r}')

    def evolving(self, kind_or_ref: str, status: str | None) -> bool:
        kind = kind_or_ref.split('-', 1)[0].upper()
        return self.mode == 'evolving' and kind in {'ADR', 'AE'} and status == 'PROPOSED'

    def allows(self, kind_or_ref: str, status: str | None, *,
               settled: Collection[str] = APPROVED_REFERENCE_STATUSES) -> bool:
        return status in settled or self.evolving(kind_or_ref, status)

    def notice(self, ref: str, status: str | None) -> str:
        return (f'{ref} remains {status}; specification.reference_mode=evolving permits this ADR/AE '
                'reference without promoting its lifecycle. Its current text and hash are used; '
                'implementation still requires an independently authorized IB and current evidence.')

    @property
    def stamp(self) -> dict[str, str | int]:
        return {'mode': self.mode, 'revision': 1}


def load_policy(repo_root: Path) -> ReferencePolicy:
    """Read the specification policy, fail visibly for malformed declarations.

    Validate the published policy subschema rather than requiring unrelated
    initialization fields in legacy execution-only configuration files.
    """
    path = Path(repo_root) / '.dekspec/config.yaml'
    if not path.is_file():
        return ReferencePolicy()
    try:
        source = path.read_text(encoding='utf-8')
        raw = yaml.safe_load(source)
        node = yaml.compose(source)
    except (OSError, yaml.YAMLError) as exc:
        raise ReferencePolicyError(f'Cannot read specification policy in {path}: {exc}') from exc
    if not isinstance(raw, dict):
        raise ReferencePolicyError(f'Expected a configuration mapping in {path}')
    old = raw.get('implement')
    if isinstance(old, dict) and 'linked_ae_statuses' in old:
        raise ReferencePolicyError('The unreleased implement.linked_ae_statuses setting was replaced; '
                                   'remove it and use specification.reference_mode: strict or evolving')
    if 'specification' not in raw:
        return ReferencePolicy()
    if isinstance(node, yaml.MappingNode):
        declarations = [value for key, value in node.value if key.value == 'specification']
        if len(declarations) > 1:
            raise ReferencePolicyError('Duplicate specification policy declarations')
        if declarations and isinstance(declarations[0], yaml.MappingNode):
            keys = [key.value for key, _ in declarations[0].value]
            if len(keys) != len(set(keys)):
                raise ReferencePolicyError('Duplicate key in specification policy')
    policy = raw['specification']
    schema = load_schema('dekspec_config')['properties']['specification']
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise ReferencePolicyError(f'Invalid specification.reference_mode policy in {path}: {errors[0].message}')
    return ReferencePolicy(policy.get('reference_mode', 'strict'))
