# Proposed native checks — DRAFT ONLY

`AccessorTests.cpp.fragment.txt` contains three text-only Automation candidates for a **matched custom-engine plugin variant**: Capability, PackageResolvedNull, WrongThread. They are NOT in the engine patch or active plugin sources, NOT compiled, discovered or run. Existing project source-case count51 is unchanged. Existing2/2 and17/17 receipts do not cover them.

## Intended scope

- Capability compares linked engine declaration/version/sizes/macros without an object input. It still needs the new CoreUObject exports and an ABI-compatible binary pair before plugin loading.
- PackageResolvedNull observes an existing engine-owned rooted transient package; no NewObject/load/strong-reference acquisition/forced GC. Dirty and RootSet are compared. A local, idle valid call is expected to return ResolvedNull; remote expects Unsupported.
- WrongThread passes that existing rooted package to one worker invocation, which must return before reading private object storage. Main thread waits for completion. This is not a race/destruction stress fixture and does not allow arbitrary unowned inputs.

The two object-bearing cases require `-McpStoredOuterAccessorDraftTests`, an isolated Temp/opencode `BeholderStructureTestHost`, game-thread setup/idle editor and explicit future authorization for non-null engine member invocation and worker refusal probing. The opt-in differs from previous guard bookkeeping and transient Blueprint opt-ins; do not reuse those grants as permission. If host/GC context refuses, record failure, not an automatic retry or permissive skip.

## Deliberately missing

Resolved **non-null** outer, unresolved outer storage, malformed/type-unsafe unresolved storage, direct private-wrapper equality, callback-instrumented resolution/read-tracking/load counts, unrooted survival, all GC phase/refusal paths, shutdown and capability mismatch matrices. No forged-pointer inputs, private-field offsets or whole-object memory rewrites are proposed.

ObjectHandleTest.cpp's engine-native resolution tracking fixtures are reference designs, not automatically usable plugin dependencies. Legal construction/observation of an actual stored unresolved outer still needs an engine-owned fixture and explicit source/execution scope; ordinary unresolved property wrappers would not test OuterPrivate.

These three candidates are a first smoke scope ONLY. Passing them would not certify no-resolution semantics, lifetime safety, supported engine integration acceptance, full SCS capture, effective inheritance, native ownership, recovery, reparent or motion.

## Boundaries

- No tests may run before separate custom engine/plugin builds and explicit exact-run permission.
- No tests/build/install/patch apply authorized by this document.
- `StoredOuterV1.unapplied.patch` and its existing apply-check receipt remain unchanged: that patch contains only accessor implementation/header changes, not these tests or the adapter.
- A future test patch must be separately assembled against an approved checkout; no engine-native test source is silently installed by adding a .txt file here.
