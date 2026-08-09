"""Unit tests for AuthService — no DB required."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest

from src.modules.auth.application.auth_service import AuthService
from src.modules.auth.domain.errors import (
    AccountPendingError,
    CapabilityDeniedError,
    EmailRequiredError,
    PracticeStatusError,
    StepUpRequiredError,
)
from src.modules.auth.domain.models import (
    AccountStatus,
    Role,
    User,
    UserIdentity,
)
from src.modules.auth.ports import AuditEventInput, IdentityClaims
from src.platform.request_context import RequestContext

# ── Fakes ─────────────────────────────────────────────────────────────────────


class FakeIdentityPort:
    def __init__(self, claims: IdentityClaims | None = None) -> None:
        self._claims = claims

    async def validate_token(self, token: str) -> IdentityClaims:
        if self._claims is not None:
            return self._claims
        return IdentityClaims(
            issuer="stub",
            subject=token,
            verified_email="solo@example.com",
        )


class FakeUserIdentityRepo:
    def __init__(
        self,
        *,
        by_subject: UserIdentity | None = None,
        by_email: UserIdentity | None = None,
    ) -> None:
        self._by_subject = by_subject
        self._by_email = by_email
        self.created: list[UserIdentity] = []

    async def find_by_subject(self, issuer: str, subject: str) -> UserIdentity | None:
        return self._by_subject

    async def find_by_verified_email(self, email: str) -> UserIdentity | None:
        return self._by_email

    async def create(self, identity: UserIdentity) -> UserIdentity:
        self.created.append(identity)
        if self._by_subject is None:
            self._by_subject = identity
        return identity


class FakeUserRepo:
    def __init__(self, users: dict[str, User] | None = None) -> None:
        self._users: dict[str, User] = users or {}
        self.created: list[User] = []

    async def get(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return None

    async def create(self, user: User) -> User:
        self._users[user.id] = user
        self.created.append(user)
        return user

    async def update(self, user: User) -> User:
        self._users[user.id] = user
        return user


class FakeAuditPort:
    def __init__(self) -> None:
        self.events: list[AuditEventInput] = []

    async def record(self, event: AuditEventInput) -> None:
        self.events.append(event)


def make_ctx(role: Role = Role.REVIEWER) -> RequestContext:
    return RequestContext(
        actor_id="usr_test",
        account_role=role,
        correlation_id="corr_test",
    )


def make_service(**kwargs: object) -> AuthService:
    defaults: dict = {
        "identity_port": FakeIdentityPort(),
        "user_identity_repo": FakeUserIdentityRepo(),
        "user_repo": FakeUserRepo(),
        "audit_port": FakeAuditPort(),
    }
    defaults.update(kwargs)
    return AuthService(**defaults)


def _active_user(user_id: str = "usr_existing", role: Role = Role.APPROVER) -> User:
    now = datetime.now(tz=UTC)
    return User(
        id=user_id,
        display_name="Existing",
        account_status=AccountStatus.ACTIVE,
        role=role,
        notary_registration=None,
        jurisdiction=None,
        created_at=now,
        updated_at=now,
    )


class TestAuthorize:
    @pytest.mark.asyncio
    async def test_reviewer_denied_approve_capability(self):
        svc = make_service()
        ctx = make_ctx(role=Role.REVIEWER)
        with pytest.raises(CapabilityDeniedError):
            await svc.authorize(ctx, "draft.approve")

    @pytest.mark.asyncio
    async def test_approver_granted_approve_capability(self):
        svc = make_service()
        ctx = make_ctx(role=Role.APPROVER)
        await svc.authorize(ctx, "draft.approve")

    @pytest.mark.asyncio
    async def test_matter_id_does_not_affect_capability_check(self):
        """V0: authorize ignores matter membership; matter_id is accepted for API compat."""
        svc = make_service()
        ctx = make_ctx(role=Role.APPROVER)
        await svc.authorize(ctx, "draft.approve", matter_id="any-matter")


class TestProvisionIdentity:
    @pytest.mark.asyncio
    async def test_auto_provisions_active_approver(self):
        audit = FakeAuditPort()
        users = FakeUserRepo()
        identities = FakeUserIdentityRepo()
        svc = make_service(
            user_repo=users,
            user_identity_repo=identities,
            audit_port=audit,
        )
        user = await svc.provision_identity("token-new")
        assert user.account_status == AccountStatus.ACTIVE
        assert user.role == Role.APPROVER
        assert len(users.created) == 1
        assert len(identities.created) == 1
        assert audit.events[0].action == "user.provisioned"
        assert audit.events[0].user_id == user.id

    @pytest.mark.asyncio
    async def test_missing_verified_email_raises(self):
        port = FakeIdentityPort(IdentityClaims(issuer="stub", subject="s1", verified_email=None))
        svc = make_service(identity_port=port)
        with pytest.raises(EmailRequiredError):
            await svc.provision_identity("t")

    @pytest.mark.asyncio
    async def test_links_identity_when_email_already_registered(self):
        existing = _active_user("usr_existing")
        existing_identity = UserIdentity(
            user_id="usr_existing",
            provider="clerk",
            issuer="other",
            subject="sub-old",
            verified_email="solo@example.com",
            linked_at=datetime.now(tz=UTC),
        )
        users = FakeUserRepo({"usr_existing": existing})
        identities = FakeUserIdentityRepo(by_email=existing_identity)
        audit = FakeAuditPort()
        svc = make_service(
            user_repo=users,
            user_identity_repo=identities,
            audit_port=audit,
        )
        user = await svc.provision_identity("token-new-subject")
        assert user.id == "usr_existing"
        assert len(users.created) == 0
        assert len(identities.created) == 1
        assert identities.created[0].subject == "token-new-subject"
        assert audit.events[0].action == "user.identity.linked"

    @pytest.mark.asyncio
    async def test_idempotent_when_subject_already_linked(self):
        user = _active_user()
        identity = UserIdentity(
            user_id=user.id,
            provider="clerk",
            issuer="stub",
            subject="token-1",
            verified_email="solo@example.com",
            linked_at=datetime.now(tz=UTC),
        )
        svc = make_service(
            user_repo=FakeUserRepo({user.id: user}),
            user_identity_repo=FakeUserIdentityRepo(by_subject=identity),
        )
        result = await svc.provision_identity("token-1")
        assert result.id == user.id


class TestBuildRequestContext:
    @pytest.mark.asyncio
    async def test_context_has_no_org_fields(self):
        user = _active_user("usr_ctx", Role.REVIEWER)
        identity = UserIdentity(
            user_id=user.id,
            provider="clerk",
            issuer="stub",
            subject="tok",
            verified_email="solo@example.com",
            linked_at=datetime.now(tz=UTC),
        )
        svc = make_service(
            identity_port=FakeIdentityPort(
                IdentityClaims(issuer="stub", subject="tok", verified_email="solo@example.com")
            ),
            user_identity_repo=FakeUserIdentityRepo(by_subject=identity),
            user_repo=FakeUserRepo({user.id: user}),
        )
        ctx = await svc.build_request_context("tok")
        assert ctx.actor_id == user.id
        assert ctx.account_role == Role.REVIEWER
        assert not hasattr(ctx, "organisation_id")

    @pytest.mark.asyncio
    async def test_unknown_identity_raises_pending(self):
        svc = make_service()
        with pytest.raises(AccountPendingError):
            await svc.build_request_context("unknown")


class TestSetUserRole:
    @pytest.mark.asyncio
    async def test_role_change_is_audited_with_user_id(self):
        actor = _active_user("usr_actor", Role.APPROVER)
        target = _active_user("usr_target", Role.REVIEWER)
        audit = FakeAuditPort()
        svc = make_service(
            user_repo=FakeUserRepo({actor.id: actor, target.id: target}),
            audit_port=audit,
        )
        ctx = make_ctx(role=Role.APPROVER)
        ctx = RequestContext(
            actor_id=actor.id,
            account_role=Role.APPROVER,
            correlation_id="c1",
        )
        await svc.set_user_role(ctx, target.id, Role.MAINTAINER)
        assert audit.events[0].user_id == actor.id
        assert audit.events[0].action == "user.role.changed"


def _notary_user(
    user_id: str = "usr_test",
    *,
    certificate_valid_until: datetime | None = None,
    jurisdiction: str | None = "Western Province",
) -> User:
    now = datetime.now(tz=UTC)
    if certificate_valid_until is None:
        certificate_valid_until = now + timedelta(days=30)
    return User(
        id=user_id,
        display_name="Notary",
        account_status=AccountStatus.ACTIVE,
        role=Role.APPROVER,
        notary_registration="NP-0001",
        jurisdiction=jurisdiction,
        certificate_valid_until=certificate_valid_until,
        created_at=now,
        updated_at=now,
    )


class TestRequireStepUp:
    @pytest.mark.asyncio
    async def test_rejects_token_bound_to_different_user(self):
        claims = IdentityClaims(
            issuer="stub",
            subject="step-up-subject",
            verified_email="other@example.com",
            auth_time=int(time.time()),
        )
        identity = UserIdentity(
            user_id="usr_other",
            provider="clerk",
            issuer="stub",
            subject="step-up-subject",
            verified_email="other@example.com",
            linked_at=datetime.now(tz=UTC),
        )
        svc = make_service(
            identity_port=FakeIdentityPort(claims),
            user_identity_repo=FakeUserIdentityRepo(by_subject=identity),
        )
        ctx = make_ctx(role=Role.APPROVER)
        with pytest.raises(StepUpRequiredError):
            await svc.require_step_up(ctx, "draft.approve", token="step-up-token")


class TestRequirePractisingNotary:
    @pytest.mark.asyncio
    async def test_rejects_expired_certificate(self):
        user = _notary_user(certificate_valid_until=datetime.now(tz=UTC) - timedelta(days=1))
        svc = make_service(user_repo=FakeUserRepo({user.id: user}))
        ctx = make_ctx(role=Role.APPROVER)
        with pytest.raises(PracticeStatusError):
            await svc.require_practising_notary(ctx)

    @pytest.mark.asyncio
    async def test_rejects_missing_jurisdiction_when_matter_id_set(self):
        user = _notary_user(jurisdiction=None)
        svc = make_service(user_repo=FakeUserRepo({user.id: user}))
        ctx = make_ctx(role=Role.APPROVER)
        with pytest.raises(PracticeStatusError):
            await svc.require_practising_notary(ctx, matter_id="mat_001")
