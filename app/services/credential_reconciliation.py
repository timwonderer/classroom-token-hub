"""Pure classification for principal credential reconciliation (FEAT-IDEN-108, SPEC-IDEN-002 §VII).

Identity owns one classification, shared by principal mode (a lifecycle boundary) and,
later, scheduled mode. It compares the *exact credential identifiers* a provider lists for
ONE principal with that principal's local authority and decides, for each, whether it may
ever be a candidate for remote retirement. It reads and writes nothing, calls no provider
and never imports an inventory entry into local state: an inventory is evidence about the
provider, never proof of activation.

Matching is by credential id only, never by label, nickname, timestamp or key. Two
spellings of the same id that differ only in base64 alphabet or padding (the equivalence
``passkey_service`` already applies when it confirms a deletion) are one credential, so a
provider that re-encodes an id cannot make an activated binding look provider-only. The
provider's own spelling is what a deletion later uses.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from app.services.passkey_service import credential_match_key


class CredentialClass(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    RETIRING = "retiring"
    PROVIDER_ONLY = "provider_only"


@dataclass(frozen=True)
class Classification:
    """The outcome of one classification.

    ``provider`` maps each provider-listed id (the provider's own spelling) to its class.
    ``unexpectedly_absent`` holds locally activated ids the provider did not list, excluding
    the id being retired (its absence is the intended effect). ``deferred`` is true when
    provider-only entries were protected because a lawful pending registration has no
    known credential id yet.
    """

    provider: dict[str, CredentialClass]
    unexpectedly_absent: tuple[str, ...]
    deferred: bool

    @property
    def provider_only(self) -> tuple[str, ...]:
        return tuple(i for i, c in self.provider.items() if c is CredentialClass.PROVIDER_ONLY)


def classify_inventory(
    *,
    provider_ids: Iterable[str],
    active_ids: Iterable[str],
    pending_id: str | None = None,
    retiring_id: str | None = None,
    pending_registration_unknown: bool = False,
) -> Classification:
    """Classify one principal's exact provider inventory against current local authority.

    ``active_ids`` are the principal's locally activated credential ids (the retiring one
    is among them until its local binding is removed). ``pending_id`` is the open
    operation's recorded candidate, if known; ``retiring_id`` its recorded old/retiring id.
    ``pending_registration_unknown`` says a lawful registration is in flight whose
    credential id is not yet known: every entry that would be provider-only is then
    protected as pending, because inventory must not be used to guess the result.

    Precedence is retiring, then pending, then active; anything else is provider-only
    (or protected pending when the registration is unknown). Pure.
    """
    active = {credential_match_key(i) for i in active_ids}
    pending = None if pending_id is None else credential_match_key(pending_id)
    retiring = None if retiring_id is None else credential_match_key(retiring_id)

    provider: dict[str, CredentialClass] = {}
    listed: set[str] = set()
    deferred = False
    for credential_id in provider_ids:
        key = credential_match_key(credential_id)
        listed.add(key)
        if key == retiring:
            provider[credential_id] = CredentialClass.RETIRING
        elif key == pending:
            provider[credential_id] = CredentialClass.PENDING
        elif key in active:
            provider[credential_id] = CredentialClass.ACTIVE
        elif pending_registration_unknown:
            provider[credential_id] = CredentialClass.PENDING
            deferred = True
        else:
            provider[credential_id] = CredentialClass.PROVIDER_ONLY

    absent = tuple(
        i for i in active_ids
        if credential_match_key(i) not in listed and credential_match_key(i) != retiring
    )
    return Classification(provider=provider, unexpectedly_absent=absent, deferred=deferred)
