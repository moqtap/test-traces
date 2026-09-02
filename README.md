# moqtap/test-traces

Checked-in session recordings for the MoQT tooling ecosystem. Where
[`moqtap/test-vectors`](https://github.com/moqtap/test-vectors) holds wire
vectors for the IETF protocol drafts, this repository holds files in the
container formats the tooling around those drafts writes — formats that are
not standardised, and are versioned by their own specifications rather than by
a draft number.

Today that is one format: `.moqtrace`.

## Quick start

```bash
git clone https://github.com/moqtap/test-traces.git
```

```bash
npm install --save-dev @moqtap/test-traces
```

Read `moqtrace/manifest.json`, open each file listed under a case's `files`,
and check your reader against what the case declares.

## Repository layout

```
moqtrace/
  manifest.json        machine-readable index: every case, its expectations
  <case>/
    js.moqtrace        written by @moqtap/trace
    rust.moqtrace      written by moqtap-trace
    capture.moqtrace   recorded from a session with a third-party relay
schema/                JSON Schema for the manifest
scripts/               CI validation scripts
```

# `.moqtrace` conformance corpus

Files that both implementations of the format read as part of their test
suites:

- **JavaScript** — [`@moqtap/trace`](https://github.com/moqtap/moqtap-js/tree/master/packages/trace),
  over `cbor-x`
- **Rust** — [`moqtap-trace`](https://github.com/moqtap/moqtap), over `ciborium`

The format is specified in
[SPEC.md](https://github.com/moqtap/moqtap-js/blob/master/packages/trace/SPEC.md).
Its Interoperability section states the rule this corpus enforces:

> An implementation that cannot round-trip the corpus is not conformant,
> whatever this document says.

## Why it exists

A test suite that reads only bytes it wrote itself is blind in a specific way:
an encoder always agrees with its own decoder, including on conventions nobody
else implements. Two such conventions are what SPEC.md's encoding rules are
about, and neither implementation's own suite could see either.

- `cbor-x` writes a number past 2^32 as a CBOR float64. Every epoch
  millisecond timestamp is such a number, and a decoder reading integers finds
  `startTime` missing and rejects the file.
- `cbor-x` wraps a byte string in RFC 8746 tag 64. A decoder reading major
  type 2 sees no bytes at all, which silently empties raw wire bytes, object
  payloads, track names and trace ids.

`v2-float-ints` and `v2-tag64` are files in those shapes. A conformant reader
accepts them, because files written that way exist.

## Cases

The two files of a case are **not byte-identical, and are not meant to be**.
`ciborium` writes an integer in the narrowest form that holds it, `cbor-x`
writes a BigInt in eight bytes, and they order map keys differently. Both are
legal CBOR carrying the same values — which is the property the corpus checks.
A test compares decoded content, never bytes.

`manifest.json` describes each case, including its declared format version,
segment count, header fields, event count and a histogram of event types. The
six the spec names — a version-1 file, a non-segmented version-2 file, a
segmented version-2 stream, an unknown event type, an unknown perspective, and
a truncated file — are `v1-basic`, `v2-basic`, `v2-segmented`,
`v2-unknown-event`, `v2-unknown-perspective` and `v2-truncated`.

`v2-extra-keys` is the case for the rule that "unknown keys MUST be ignored"
means *read past*, not *discard*: known event types carrying keys no reader
knows, which must still be there after a read-modify-write. Every key in it is
`x-` prefixed, the range SPEC.md reserves for private use and promises never to
define, so no future revision can claim one and turn the fixture into a test of
something else.

`v2-header-extra` is that same rule one level up, and the only file here
carrying an unrecognised key in the *header*. Three maps there have keys the
spec names — the header itself, `"segment"` and `"sampling"` — and each keeps
its own store, so this case puts one key name in all three with three different
values: a reader that merged them emits the segment's private key at the top
level. Its `"transport": 42` is a key the format *does* define, carrying a value
no reader can use, which reaches a store through the ordinary field path rather
than through a hand-built file. Two more of its stored values are there for the
encoders: an integral float and a byte string under tag 64, the two shapes the
spec requires a writer to normalise wherever they sit — including inside a store
it never looked at, which is the one place the two implementations could
silently differ.

`v2-control-msg-map` and `v2-msg-absent` are the pair for Event 0's `"msg"`.
The first holds the three shapes a conforming writer produces — a populated
snake_case map, an empty map for a message nothing was decoded from, and a
nested map. The second omits the key entirely, which the spec forbids a writer
to do and requires a reader to survive: Event 0 is a type sampling MUST NOT
drop, so rejecting the omission discards exactly what the format promises to
keep. The shipped Rust reader did that until this case existed. A fourth shape
— a `"msg"` that is not a map at all — needs no case of its own, because every
`capture-*` file already carries a Rust debug string there.

`v2-headers-level-flow` is the case for a `"headers"` recording, where the
stream-header identifiers are the only way to group anything: no payload is
kept and no level of this format records the bytes of a `SUBGROUP_HEADER`, a
fetch header or a datagram header, so `"ta"`, `"sg"`, `"fri"` and `"g"` are
all the file has to say which track a stream carried. Its three streams share
one track alias on purpose — legal, ordinary, and the reason the alias alone
cannot key a flow.

The `capture-*` cases are real sessions, not constructed ones: a `moqtap peek`
or `moqtap intercept` run against `cloudflare/moq-rs` or `meetecho/imquic`,
covering drafts 16, 18 and 19. Nothing in them was designed to be readable,
which is their value — a corpus written entirely by the tools under test can
only contain shapes those tools already thought of.

## Using it from a third implementation

Nothing here is specific to the two reference implementations. Read
`moqtrace/manifest.json`, open each file listed under `files`, and check that
your reader agrees with the case's `version`, `segments`, `protocol`,
`perspective`, `detail`, `eventCount` and `eventTypes`. Then check that every
file of a case decodes to the same content as every other, and that writing
what you decoded and reading it back gives you the same thing.

`eventTypes` keys are the `"e"` discriminants as decimal strings, so an event
type no version of the spec defines — `"99"` in `v2-unknown-event` — appears
under its own number rather than being folded into anything.

## Regenerating

The bytes are committed, so a change to a case has to be regenerated in both
languages and both files committed. Running only one generator fails the
corpus test rather than drifting quietly, and the failure names the file
nobody updated.

```bash
# JavaScript half, from moqtap-js/packages/trace
bun run src/__tests__/corpus/generate.ts

# Rust half, from moqtap
cargo run -p moqtap-trace --example generate_corpus

# then reindex, from moqtap-js/packages/trace
bun run src/__tests__/corpus/manifest.ts
```

The `capture-*` files are not regenerated. They are recordings of sessions
that happened, and rerecording them would produce different traffic under the
same name.

## Validating

```bash
python scripts/validate.py       # manifest against the bytes, no dependencies
npm ci && npm run validate:schema  # manifest against the JSON Schema
```

## License

MIT
