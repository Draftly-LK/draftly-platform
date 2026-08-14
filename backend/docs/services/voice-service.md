# voice-service — implementation design

Official model reference:
[Gemini 3.1 Flash Live Preview](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-live-preview).

Companion to `backend/backend-implementation-plan-v0.md`,
`research-service.md`, `document-service.md`, and `memory-service.md`.

## 1. Scope decision

**Voice ships in V0 if the schedule allows, otherwise in V1.** The design,
guardrails, and contracts below are settled either way; only the delivery date
is open, and it is a scheduling call rather than a design one.

This was previously stated three different ways: plan §2.2 listed voice as an
explicit non-goal, `research-service.md` open decision 3 repeated "explicitly
V1", and §1 of this document made Gemini Live the committed primary V0 model.
All three now read from this section, and plan §2.2 has been updated to
"schedule-gated" rather than "non-goal".

Two consequences for other services:

- `memory_service` carries the voice hooks in §6 and §8 of its own document as a
  **conditional** contract. The four `voice.*` events are registered
  (`events.md` §5.12), and a build without the voice service simply has no
  publisher for them. Memory must not require them to function.
- Nothing else may depend on voice. The guardrails in §9 are what make that
  safe: voice produces a candidate transcript and never reaches another service
  on its own.

### Engine

When it ships, it uses the **Gemini Live API with
`gemini-3.1-flash-live-preview`** as the primary voice model. Input
transcription is enabled with:

```python
input_audio_transcription = {}
```

The first and only V0 voice surface is the assistant composer microphone:

```text
Microphone
→ Gemini Live partial transcript
→ stored transcript event + session-memory episode
→ Gemini Live final transcript
→ stored candidate transcript
→ user reviews or edits
→ user confirms
→ user explicitly submits the text
```

The transcript is never submitted automatically. Voice does not directly ask
the assistant a question, create or verify a matter fact, edit prescribed
wording, clear a finding, or approve a draft.

Google Speech-to-Text `chirp_2` and `gemini-3.6-flash` are not active runtime
engines. They remain possible benchmark or fallback adapters if the primary
model fails the approved evaluation (§12).

The SRS still classifies voice as conditional V1 scope and must be updated to
the schedule-gated position before the microphone is shown as a committed
feature.

## 2. Languages

The V0 evaluation covers:

- Sinhala;
- English;
- Tamil;
- switching languages between sentences; and
- switching languages inside one sentence.

Language support in provider documentation is not treated as proof of legal
dictation accuracy. V0 acceptance requires a labelled Sri Lankan
legal-dictation benchmark containing legal terms, names, dates, amounts, deed
numbers, parcel identifiers, and statutory references.

## 3. Where the service sits

```text
Assistant composer microphone
        ↓
api/v1/transcriptions.py
        ↓
application/voice_service.py
        ↓
LiveTranscriptionPort
        ↓
GeminiLiveAdapter
        ↓
gemini-3.1-flash-live-preview
```

Supporting ports are:

- `ObjectStoragePort` for the original recording;
- `TranscriptRepositoryPort` for transcript versions;
- `SessionMemoryPort` for source-linked partial, final, edited, and confirmed
  transcript episodes;
- `IdentityPort` for the authenticated user and ephemeral Live API access;
  and
- `AuditPort` for capture, transcription, editing, confirmation, and later
  use.

The model name belongs in deployment configuration and the
`TranscriptionSession` record. It must not be hardcoded throughout application
or domain code.

## 4. What is stored

Yes, transcripts are stored. The service preserves the complete review
history, not only the latest text.

### 4.1 Permanently stored records

- **VoiceCapture** — the original audio recording, checksum, duration, media
  type, matter or user scope, creator, and capture time.
- **TranscriptionSession** — provider, model, API mode, start/end time,
  language hints, outcome, and connection metadata that contains no audio or
  transcript text.
- **TranscriptEvent** — every partial, final, interrupted, and closed provider
  event in arrival order, including session, sequence, provider event ID,
  event type, text where present, receive time, and supersession link.
- **CandidateTranscript** — the final transcript returned by Gemini Live,
  marked `candidate` and linked to its recording and session.
- **TranscriptRevision** — every user-edited version, linked to the version it
  supersedes, with editor and timestamp.
- **ConfirmedTranscript** — the exact transcript version the user confirms,
  with confirmer and timestamp.
- **AuditEvent** — capture, transcription completion/failure, revision,
  confirmation, submission, and deletion or retention actions.
- **SessionMemory episode** — an immutable, non-authoritative memory entry that
  points to the corresponding `TranscriptEvent` or transcript version.

Partial, candidate, and edited transcripts are never overwritten. The current
text is resolved through version and supersession links.

### 4.2 Partial transcript storage

Every live partial fragment is stored as an immutable `TranscriptEvent` and
ingested into session memory as a verbatim episode. The episode carries a
source pointer to the event, so memory is never the only place the fragment
exists.

Gemini may revise the same utterance repeatedly. When a newer partial arrives,
it supersedes the earlier partial for current-session retrieval. When the final
transcript arrives, it supersedes all live partials for the current transcript.
The partial event history remains queryable for audit, debugging under approved
access, and memory reconstruction.

Partial episodes use a dedicated `voice-live` thread in session memory. They
may support immediate conversational continuity, but they do not trigger
long-term note reconsolidation. The final, edited, or confirmed transcript
triggers note consolidation and becomes the current remembered text.

Partial fragments must not be written to application logs, analytics, traces,
or error reports. Their retention follows the approved audio/transcript policy.

### 4.3 Meaning of confirmation

Confirmation means only:

> The user has reviewed this transcript and accepts it as the text they intend
> to use next.

It does not verify any legal fact contained in the text. If confirmed text is
later used to propose a matter particular, that particular still passes
through the verification service and a lawyer decision.

## 5. Domain models

In `domain/voice.py`:

### VoiceCapture

```text
id
matter_id?
storage_key
checksum
duration_ms
mime_type
captured_by
captured_at
retention_state
```

### TranscriptionSession

```text
id
capture_id
provider
model
state
started_at
finished_at?
outcome?
correlation_id
```

### TranscriptEvent

```text
id
session_id
sequence
provider_event_id?
event_type = partial | final | interrupted | failed | closed
text?
received_at
supersedes_event_id?
```

### CandidateTranscript

```text
id
session_id
capture_id
text
status = candidate
created_at
```

### TranscriptRevision

```text
id
transcript_id
supersedes_version_id
text
edited_by
edited_at
reason?
```

### ConfirmedTranscript

```text
id
transcript_version_id
confirmed_by
confirmed_at
```

State model:

```text
TranscriptionSession:
created → connecting → streaming → finalising → completed
                    ↘ failed

Transcript:
partial → superseded by newer partial → superseded by final candidate
candidate → edited → confirmed
          ↘ discarded
```

No transcript state includes `verified`, `approved`, or `authoritative`.

## 6. Port

The V0 port represents a streaming session rather than a batch transcription
job:

```python
class LiveTranscriptionPort(Protocol):
    async def open_session(
        self,
        capture_id: UUID,
        language_hints: list[str],
    ) -> LiveTranscriptionSession: ...
```

The session emits:

```text
partial
final
interrupted
failed
closed
```

The `GeminiLiveAdapter` implements this port. A later provider must implement
the same application-level events without changing transcript storage or
review rules.

The application stores every emitted event before publishing its identifier to
session memory. An outbox or equivalent retryable event handoff ensures a
temporary memory-service failure cannot lose the voice event or block the live
transcript.

## 7. Methods and endpoints

### create_session

`POST /api/v1/transcriptions/sessions`

Authorise the user, create the capture/session records, issue narrowly scoped
ephemeral access for the Live API flow, and audit `voice.session-created`.
Permanent provider credentials never reach the browser.

### finalise_transcription

`POST /api/v1/transcriptions/{session_id}/finalise`

Store the completed original recording, verify its checksum, store the final
Gemini transcript as an immutable candidate version, complete the session, and
audit `voice.transcribed`.

### record_transcript_event

Internal application operation called for every Gemini Live event. Append the
event with its session sequence, establish its supersession link, and publish a
source-linked episode to `SessionMemoryPort`. A final event supersedes earlier
partials for current retrieval but does not delete them.

### get_transcription

`GET /api/v1/transcriptions/{session_id}`

Return the final candidate, revision history, and confirmation state. Access is
matter-scoped when the capture belongs to a matter and user-scoped otherwise.

### revise_transcription

`POST /api/v1/transcriptions/{session_id}/revisions`

Create a new transcript version. Never update the provider transcript or a
previous user revision in place.

### confirm_transcription

`POST /api/v1/transcriptions/{session_id}/confirm`

Confirm one exact transcript version. The operation does not submit it to
another service.

There is deliberately no generic `apply transcript` endpoint. Asking a
research question, adding a note, or proposing a matter particular is a
separate authenticated and audited user action.

## 8. Gemini Live configuration

The adapter uses:

```text
model: gemini-3.1-flash-live-preview
input audio transcription: enabled
input audio: raw 16-bit PCM, 16 kHz preferred
languages under evaluation: Sinhala, English, Tamil, and mixed speech
authentication: ephemeral client token or approved server-mediated session
```

Automatic voice activity detection may be used initially. The implementation
must send the audio-stream-end event when the user stops recording so buffered
audio is flushed and a final transcript can be received.

The model is a preview dependency. Its identifier, availability, API changes,
and deprecation notices must be monitored. Replacement is a configuration and
adapter change, not a domain-model migration.

## 9. Hard guardrails

1. **Candidate only.** A provider transcript is always a candidate.
2. **User review required.** The user must review or edit and confirm the final
   text before using it.
3. **No silent fact verification.** Voice cannot set a verified or corrected
   matter particular.
4. **No prescribed-wording changes.** Voice cannot alter locked template text.
5. **No approval.** Voice cannot approve a draft or clear a blocker.
6. **No automatic downstream action.** The voice service does not call the
   research, note, verification, drafting, or approval services on its own.
7. **No audit bypass.** Capture, final transcript, edits, confirmation, and
   downstream use are audited.
8. **Version history preserved.** Provider and user transcript versions are
   append-only.
9. **Memory has provenance.** Every remembered voice fragment points to a
   persisted `TranscriptEvent` or transcript version.

## 10. Privacy and retention

Audio and transcripts are confidential client material:

- matter-scoped or capturing-user-scoped access only;
- encrypted in transit and at rest;
- protected object storage for audio;
- no audio or transcript content in ordinary logs, traces, analytics, or error
  reports;
- no real client recordings in development, demonstrations, or benchmarks
  without formal approval and anonymisation where possible;
- provider region, retention, training use, deletion, and processor terms
  approved before real recordings are sent; and
- deletion and retention events recorded in the audit history.

The system stores recordings and final transcript versions by default so a user
can review how the transcript was produced. The exact retention period and
whether confirmed audio may later be deleted are policy decisions that must be
approved before live client use. Transcript retention must preserve any record
required to explain a downstream matter action.

## 11. Failure behaviour

- Connection failure produces an explicit failed session and allows the user
  to type instead.
- Silence, noise, clipped audio, or unintelligible speech produces no automatic
  downstream action.
- Interrupted sessions preserve their audit metadata but do not create a
  misleading final transcript.
- Rapid language switching, names, and numbers remain review priorities even
  when the transcript appears fluent.
- Missing final provider event does not promote the last partial fragment to a
  final transcript.
- Memory-service failure does not lose the persisted provider event; the
  outbox retries episode ingestion.
- Provider retirement disables the feature safely until an approved adapter or
  model configuration is available.

## 12. Evaluation and tests

### Functional tests

- open session, stream audio, receive partials, receive final, and persist the
  final candidate;
- persist every partial in sequence and ingest a source-linked memory episode;
- supersede partial episodes when a newer partial or final transcript arrives
  while retaining historical retrieval;
- revise the candidate twice and preserve all three versions;
- confirm one exact version and retain the confirmation identity/time;
- deny cross-matter transcript and audio access;
- verify that partial fragments appear only in protected transcript storage
  and session memory, never in logs or analytics;
- provider failure leaves no false final transcript; and
- prove the voice service cannot verify facts, change locked wording, resolve
  findings, or approve drafts.

### Provider benchmark

Use labelled recordings covering:

- Sinhala, English, and Tamil separately;
- inter-sentence and intra-sentence code-switching;
- multiple Sri Lankan accents and speakers;
- quiet rooms, ordinary laptop/phone microphones, and moderate background
  noise; and
- names, legal terminology, dates, amounts, deed numbers, parcel references,
  and statutory sections.

Report:

- word and character error rates;
- critical-identifier accuracy;
- time to first partial transcript;
- final transcript latency;
- user correction rate;
- failed/disconnected session rate; and
- cost per minute and per completed transcript.

The primary model remains provisional until the team approves the benchmark
thresholds and the model passes them.

## 13. Deferred options

The following are intentionally outside the simple V0 runtime:

- automatic second-engine comparison;
- `chirp_2` verification or fallback;
- `gemini-3.6-flash` audio recovery;
- Azure Speech integration;
- voice-controlled document changes;
- spoken assistant responses;
- long meeting transcription;
- speaker diarisation; and
- automatic promotion of partial transcript text into long-term memory notes.

They may be added behind the same domain and review boundaries after V0
evaluation shows a concrete need.
