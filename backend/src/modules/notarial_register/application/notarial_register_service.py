"""Notarial register application service."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.notarial_register.domain.errors import (
    MatterAccessDeniedError,
    RegisterAccessDeniedError,
    UnapprovedInstrumentError,
)
from src.modules.notarial_register.domain.models import (
    AddProtocolInput,
    Attestation,
    AttestationState,
    CollectionInput,
    CreateAttestationInput,
    MonthlyReturnPeriod,
    MonthlyReturnState,
    ProtocolCopyKind,
    ProtocolRecord,
    ProtocolState,
    RegisterEntriesPage,
    RegisterEntry,
    RegisterEntryFilters,
    RegisterEntryState,
    RegistrationAcknowledgementInput,
    RegistrationDefectInput,
    RegistrationSubmission,
    RegistrationSubmissionInput,
    RegistrationSubmissionState,
    SourceKind,
)
from src.modules.notarial_register.domain.policies import (
    assert_state_transition,
    register_year_for,
    require_capability,
    require_practising_notary_actor,
    validate_export_source,
)
from src.modules.notarial_register.ports import (
    ApprovedInstrumentPort,
    AttestationRepository,
    ClockPort,
    EventPort,
    MatterAccessPort,
    MonthlyReturnRepository,
    ProtocolRepository,
    RegisterRepository,
    RegistrationSubmissionRepository,
)
from src.platform.request_context import RequestContext


class NotarialRegisterService:
    def __init__(
        self,
        *,
        attestation_repo: AttestationRepository,
        register_repo: RegisterRepository,
        protocol_repo: ProtocolRepository,
        registration_repo: RegistrationSubmissionRepository,
        monthly_return_repo: MonthlyReturnRepository,
        approved_instrument_port: ApprovedInstrumentPort,
        matter_access: MatterAccessPort,
        audit_port: AuditPort,
        event_port: EventPort,
        clock: ClockPort,
    ) -> None:
        self._attestations = attestation_repo
        self._register = register_repo
        self._protocol = protocol_repo
        self._registration = registration_repo
        self._monthly = monthly_return_repo
        self._approved = approved_instrument_port
        self._matter_access = matter_access
        self._audit = audit_port
        self._events = event_port
        self._clock = clock

    async def record_attestation(
        self, ctx: RequestContext, matter_id: str, input: CreateAttestationInput
    ) -> Attestation:
        require_practising_notary_actor(ctx)
        if matter_id != input.matter_id:
            raise MatterAccessDeniedError()
        if not await self._matter_access.is_member(ctx.actor_id, matter_id):
            raise MatterAccessDeniedError()

        validate_export_source(
            source_kind=input.source_kind,
            export_id=input.export_id,
            external_reason=input.external_reason,
        )

        draft_version_id: str | None = None
        content_hash: str | None = None
        if input.source_kind == SourceKind.EXPORT:
            assert input.export_id is not None
            approved = await self._approved.load_approved_export(
                user_id=ctx.actor_id,
                matter_id=matter_id,
                export_id=input.export_id,
                use_fixture=input.approved_instrument_fixture,
            )
            if approved is None:
                raise UnapprovedInstrumentError()
            draft_version_id = approved.draft_version_id
            content_hash = approved.content_hash

        attestation_id = f"att_{uuid.uuid4().hex}"
        now = self._clock.now()
        attestation = Attestation(
            id=attestation_id,
            user_id=ctx.actor_id,
            matter_id=matter_id,
            instrument_kind=input.instrument_kind,
            registration_regime=input.registration_regime,
            source_kind=input.source_kind,
            export_id=input.export_id,
            draft_version_id=draft_version_id,
            content_hash=content_hash,
            attestation_clause_definition_id=input.attestation_clause_definition_id,
            attestation_clause_version=input.attestation_clause_version,
            attestation_conditions=input.attestation_conditions,
            notary_user_id=ctx.actor_id,
            practising_jurisdiction_id=input.practising_jurisdiction_id,
            registration_jurisdiction_id=input.registration_jurisdiction_id,
            instrument_language=input.instrument_language,
            attested_at=input.attested_at,
            place_of_execution=input.place_of_execution,
            executants=input.executants,
            witnesses=input.witnesses,
            consideration_recorded=input.consideration_recorded,
            state=AttestationState.ATTESTED,
            version=1,
            external_reason=input.external_reason,
        )

        register_year = register_year_for(input.attested_at)
        serial = await self._register.allocate_serial(
            notary_user_id=ctx.actor_id,
            register_year=register_year,
        )
        register_entry = RegisterEntry(
            id=f"re_{uuid.uuid4().hex}",
            user_id=ctx.actor_id,
            notary_user_id=ctx.actor_id,
            register_year=register_year,
            serial_number=serial,
            attestation_id=attestation_id,
            entry_date=input.attested_at.date(),
            instrument_kind=input.instrument_kind,
            party_summary_ref=input.party_summary_ref,
            consideration_ref=input.consideration_ref,
            folio_ref=input.folio_ref,
            state=RegisterEntryState.ACTIVE,
            cancellation_reason=None,
            created_at=now,
        )

        protocol = ProtocolRecord(
            id=f"pr_{uuid.uuid4().hex}",
            attestation_id=attestation_id,
            copy_kind=ProtocolCopyKind.ORIGINAL,
            storage_ref=None,
            physical_location=None,
            custodian_user_id=ctx.actor_id,
            issued_to=None,
            issued_at=None,
            returned_at=None,
            retention_class="notarial-protocol",
            state=ProtocolState.HELD,
        )

        await self._attestations.create(attestation)
        await self._register.create_entry(register_entry)
        await self._protocol.create(protocol)
        await self._track_attestation_in_period(ctx, attestation)

        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                matter_id=matter_id,
                actor=ctx.actor_id,
                action="instrument.attested",
                target_type="instrument",
                target_id=attestation_id,
                correlation_id=ctx.correlation_id,
            )
        )
        await self._events.publish(
            user_id=ctx.actor_id,
            event_type="instrument.attested",
            aggregate_id=attestation_id,
            payload={
                "instrumentId": attestation_id,
                "matterId": matter_id,
                "attestedAt": input.attested_at.isoformat(),
                "registrationRegime": input.registration_regime.value,
                "notaryUserId": ctx.actor_id,
                "practisingJurisdictionId": input.practising_jurisdiction_id,
                "registrationJurisdictionId": input.registration_jurisdiction_id,
            },
            correlation_id=ctx.correlation_id,
        )
        return attestation

    async def get_attestation(
        self, ctx: RequestContext, matter_id: str, attestation_id: str
    ) -> Attestation:
        if not await self._matter_access.is_member(ctx.actor_id, matter_id):
            raise MatterAccessDeniedError()
        attestation = await self._attestations.get_by_matter(
            ctx.actor_id, matter_id, attestation_id
        )
        if attestation is None:
            raise MatterAccessDeniedError()
        return attestation

    async def add_protocol(
        self, ctx: RequestContext, attestation_id: str, input: AddProtocolInput
    ) -> ProtocolRecord:
        require_practising_notary_actor(ctx)
        attestation = await self._attestations.get(ctx.actor_id, attestation_id)
        if attestation is None:
            raise MatterAccessDeniedError()

        record = ProtocolRecord(
            id=f"pr_{uuid.uuid4().hex}",
            attestation_id=attestation_id,
            copy_kind=input.copy_kind,
            storage_ref=input.storage_ref,
            physical_location=input.physical_location,
            custodian_user_id=input.custodian_user_id or ctx.actor_id,
            issued_to=None,
            issued_at=None,
            returned_at=None,
            retention_class=input.retention_class,
            state=ProtocolState.HELD,
        )
        created = await self._protocol.create(record)
        register_entry = await self._register.get_entry_for_attestation(
            ctx.actor_id, attestation_id
        )
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                matter_id=attestation.matter_id,
                actor=ctx.actor_id,
                action="instrument.protocol-recorded",
                target_type="instrument",
                target_id=attestation_id,
                correlation_id=ctx.correlation_id,
            )
        )
        await self._events.publish(
            user_id=ctx.actor_id,
            event_type="instrument.protocol-recorded",
            aggregate_id=attestation_id,
            payload={
                "instrumentId": attestation_id,
                "protocolNumber": created.id,
                "registerEntryId": register_entry.id if register_entry else "",
            },
            correlation_id=ctx.correlation_id,
        )
        return created

    async def record_registration_submission(
        self, ctx: RequestContext, attestation_id: str, input: RegistrationSubmissionInput
    ) -> RegistrationSubmission:
        require_practising_notary_actor(ctx)
        attestation = await self._load_owned_attestation(ctx, attestation_id)
        assert_state_transition(
            attestation.state,
            {AttestationState.ATTESTED, AttestationState.REGISTRATION_DEFECTIVE},
        )

        now = self._clock.now()
        existing = await self._registration.get_for_attestation(ctx.actor_id, attestation_id)
        if existing is None:
            submission = RegistrationSubmission(
                id=f"rs_{uuid.uuid4().hex}",
                attestation_id=attestation_id,
                user_id=ctx.actor_id,
                state=RegistrationSubmissionState.SUBMITTED,
                registry_id=input.registry_id,
                submitted_at=now,
                acknowledged_at=None,
                defect_notes=None,
                version=1,
            )
            await self._registration.create(submission)
        else:
            submission = existing
            submission.state = RegistrationSubmissionState.SUBMITTED
            submission.registry_id = input.registry_id
            submission.submitted_at = now
            submission.version += 1
            await self._registration.update(submission)

        attestation.state = AttestationState.REGISTRATION_SUBMITTED
        attestation.version += 1
        await self._attestations.update(attestation)
        await self._audit_and_event(
            ctx,
            attestation,
            action="instrument.registration-submitted",
            event_type="instrument.registration-submitted",
            payload={
                "instrumentId": attestation_id,
                "submittedAt": now.isoformat(),
                "registryId": input.registry_id,
            },
        )
        return submission

    async def record_registration_acknowledgement(
        self, ctx: RequestContext, attestation_id: str, input: RegistrationAcknowledgementInput
    ) -> Attestation:
        require_practising_notary_actor(ctx)
        attestation = await self._load_owned_attestation(ctx, attestation_id)
        assert_state_transition(attestation.state, {AttestationState.REGISTRATION_SUBMITTED})

        now = self._clock.now()
        submission = await self._registration.get_for_attestation(ctx.actor_id, attestation_id)
        if submission is None:
            submission = RegistrationSubmission(
                id=f"rs_{uuid.uuid4().hex}",
                attestation_id=attestation_id,
                user_id=ctx.actor_id,
                state=RegistrationSubmissionState.ACKNOWLEDGED,
                registry_id=input.registry_reference,
                submitted_at=None,
                acknowledged_at=now,
                defect_notes=None,
                version=1,
            )
            await self._registration.create(submission)
        else:
            submission.state = RegistrationSubmissionState.ACKNOWLEDGED
            submission.acknowledged_at = now
            if input.registry_reference:
                submission.registry_id = input.registry_reference
            submission.version += 1
            await self._registration.update(submission)

        attestation.state = AttestationState.REGISTRATION_ACKNOWLEDGED
        attestation.version += 1
        await self._attestations.update(attestation)
        await self._audit_and_event(
            ctx,
            attestation,
            action="instrument.registration-acknowledged",
            event_type="instrument.registration-acknowledged",
            payload={
                "instrumentId": attestation_id,
                "acknowledgedAt": now.isoformat(),
                "outcome": input.outcome,
            },
        )
        return attestation

    async def record_registration_defect(
        self, ctx: RequestContext, attestation_id: str, input: RegistrationDefectInput
    ) -> Attestation:
        require_practising_notary_actor(ctx)
        attestation = await self._load_owned_attestation(ctx, attestation_id)
        assert_state_transition(
            attestation.state,
            {AttestationState.REGISTRATION_SUBMITTED, AttestationState.REGISTRATION_ACKNOWLEDGED},
        )
        submission = await self._registration.get_for_attestation(ctx.actor_id, attestation_id)
        if submission is None:
            submission = RegistrationSubmission(
                id=f"rs_{uuid.uuid4().hex}",
                attestation_id=attestation_id,
                user_id=ctx.actor_id,
                state=RegistrationSubmissionState.DEFECTIVE,
                registry_id=None,
                submitted_at=None,
                acknowledged_at=None,
                defect_notes=input.defect_notes,
                version=1,
            )
            await self._registration.create(submission)
        else:
            submission.state = RegistrationSubmissionState.DEFECTIVE
            submission.defect_notes = input.defect_notes
            submission.version += 1
            await self._registration.update(submission)

        attestation.state = AttestationState.REGISTRATION_DEFECTIVE
        attestation.version += 1
        await self._attestations.update(attestation)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                matter_id=attestation.matter_id,
                actor=ctx.actor_id,
                action="instrument.registration-defective",
                target_type="instrument",
                target_id=attestation_id,
                reason=input.defect_notes,
                correlation_id=ctx.correlation_id,
            )
        )
        return attestation

    async def record_collection(
        self, ctx: RequestContext, attestation_id: str, input: CollectionInput
    ) -> Attestation:
        require_practising_notary_actor(ctx)
        attestation = await self._load_owned_attestation(ctx, attestation_id)
        assert_state_transition(
            attestation.state,
            {
                AttestationState.REGISTRATION_ACKNOWLEDGED,
                AttestationState.REGISTERED,
            },
        )
        ready_at = input.ready_at or self._clock.now()
        attestation.state = AttestationState.COLLECTED
        attestation.version += 1
        await self._attestations.update(attestation)
        await self._audit_and_event(
            ctx,
            attestation,
            action="instrument.collection-ready",
            event_type="instrument.collection-ready",
            payload={
                "instrumentId": attestation_id,
                "readyAt": ready_at.isoformat(),
            },
        )
        return attestation

    async def list_register_entries(
        self, ctx: RequestContext, filters: RegisterEntryFilters
    ) -> RegisterEntriesPage:
        notary_user_id = filters.notary_user_id or ctx.actor_id
        if notary_user_id != ctx.actor_id:
            raise RegisterAccessDeniedError()
        items, total = await self._register.list_entries(ctx.actor_id, filters)
        return RegisterEntriesPage(items=items, total=total)

    async def list_monthly_periods(
        self, ctx: RequestContext, notary_user_id: str | None = None
    ) -> list[MonthlyReturnPeriod]:
        target = notary_user_id or ctx.actor_id
        if target != ctx.actor_id:
            raise RegisterAccessDeniedError()
        return await self._monthly.list_for_notary(ctx.actor_id, target)

    async def certify_period(self, ctx: RequestContext, period_id: str) -> MonthlyReturnPeriod:
        require_capability(ctx, "register.certify-return")
        require_practising_notary_actor(ctx)
        period = await self._monthly.get(ctx.actor_id, period_id)
        if period is None or period.notary_user_id != ctx.actor_id:
            raise RegisterAccessDeniedError()
        if period.state not in (MonthlyReturnState.OPEN, MonthlyReturnState.CLOSED):
            from src.modules.notarial_register.domain.errors import InvalidAttestationStateError

            raise InvalidAttestationStateError("Period cannot be certified in its current state.")

        period.state = MonthlyReturnState.CERTIFIED
        period.certified_by = ctx.actor_id
        period.certified_at = self._clock.now()
        period.version += 1
        updated = await self._monthly.update(period)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                actor=ctx.actor_id,
                action="register.period-certified",
                target_type="register-period",
                target_id=period_id,
                correlation_id=ctx.correlation_id,
            )
        )
        return updated

    async def close_monthly_period(
        self,
        ctx: RequestContext,
        *,
        notary_user_id: str,
        period_start: date,
        period_end: date,
    ) -> MonthlyReturnPeriod:
        """Close the open period for the month, or create a nil CLOSED return."""
        period_start_dt = datetime.combine(period_start, datetime.min.time(), tzinfo=UTC)
        existing = await self._monthly.find_open_for_month(
            ctx.actor_id, notary_user_id, period_start_dt
        )
        if existing is not None:
            instrument_ids = list(existing.instrument_ids)
            is_nil = len(instrument_ids) == 0
            existing.is_nil_return = is_nil
            if is_nil:
                existing.components = ["nil-return"]
                existing.component_states = {"nil-return": "pending"}
            existing.state = MonthlyReturnState.CLOSED
            existing.version += 1
            saved = await self._monthly.update(existing)
        else:
            instrument_ids = []
            period = MonthlyReturnPeriod(
                id=f"mrp_{uuid.uuid4().hex}",
                user_id=ctx.actor_id,
                notary_user_id=notary_user_id,
                period_start=period_start,
                period_end=period_end,
                instrument_ids=instrument_ids,
                is_nil_return=True,
                components=["nil-return"],
                component_states={"nil-return": "pending"},
                certified_by=None,
                certified_at=None,
                submitted_at=None,
                acknowledged_at=None,
                state=MonthlyReturnState.CLOSED,
                version=1,
            )
            saved = await self._monthly.upsert_open_period(period)

        await self._events.publish(
            user_id=ctx.actor_id,
            event_type="register.monthly-period-closed",
            aggregate_id=saved.id,
            payload={
                "notaryUserId": notary_user_id,
                "periodStart": period_start.isoformat(),
                "periodEnd": period_end.isoformat(),
                "instrumentIds": instrument_ids,
            },
            correlation_id=ctx.correlation_id,
        )
        return saved

    async def _track_attestation_in_period(
        self, ctx: RequestContext, attestation: Attestation
    ) -> None:
        period_start = attestation.attested_at.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        if period_start.tzinfo is None:
            period_start = period_start.replace(tzinfo=UTC)
        next_month = (period_start + timedelta(days=32)).replace(day=1)
        period_end = next_month - timedelta(days=1)
        period = await self._monthly.find_open_for_month(
            ctx.actor_id, attestation.notary_user_id, period_start
        )
        if period is None:
            period = MonthlyReturnPeriod(
                id=f"mrp_{uuid.uuid4().hex}",
                user_id=ctx.actor_id,
                notary_user_id=attestation.notary_user_id,
                period_start=period_start.date(),
                period_end=period_end.date(),
                instrument_ids=[attestation.id],
                is_nil_return=False,
                components=["deed-list"],
                component_states={"deed-list": "open"},
                certified_by=None,
                certified_at=None,
                submitted_at=None,
                acknowledged_at=None,
                state=MonthlyReturnState.OPEN,
                version=1,
            )
            await self._monthly.upsert_open_period(period)
        elif attestation.id not in period.instrument_ids:
            period.instrument_ids.append(attestation.id)
            period.is_nil_return = False
            period.version += 1
            await self._monthly.update(period)

    async def _load_owned_attestation(
        self, ctx: RequestContext, attestation_id: str
    ) -> Attestation:
        attestation = await self._attestations.get(ctx.actor_id, attestation_id)
        if attestation is None:
            raise MatterAccessDeniedError()
        return attestation

    async def _audit_and_event(
        self,
        ctx: RequestContext,
        attestation: Attestation,
        *,
        action: str,
        event_type: str,
        payload: dict[str, str | int | bool | list[str] | None],
    ) -> None:
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                matter_id=attestation.matter_id,
                actor=ctx.actor_id,
                action=action,
                target_type="instrument",
                target_id=attestation.id,
                correlation_id=ctx.correlation_id,
            )
        )
        await self._events.publish(
            user_id=ctx.actor_id,
            event_type=event_type,
            aggregate_id=attestation.id,
            payload=payload,
            correlation_id=ctx.correlation_id,
        )
