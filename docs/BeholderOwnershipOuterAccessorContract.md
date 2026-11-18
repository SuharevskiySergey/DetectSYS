# Missing outer accessor — integration contract, not implementation

User subsequently chose source-only engine-integration planning. Concrete proposed files/member API/linkage/authorization stages are in `docs/BeholderOwnershipOuterEngineIntegrationPlan.md`. No installed engine modifications/builds/tests granted; custom export names remain hypothetical. Default plugin gate stays closed.

Status: source-only specification. No engine edits/build/install, plugin code changes, test execution or editor calls. This does NOT authorize those operations. Current outer gate remains closed in the tested late1/remote0/editor-data1 plugin configuration.

## Public-wrapper fallback rejected

Installed UE5.6 sources relative to Engine/Source:

- `Runtime/CoreUObject/Public/UObject/ObjectPtr.h:683–686`: TObjectPtr::GetOuter forwards to FObjectPtr::GetOuter.
- `Runtime/CoreUObject/Private/UObject/ObjectPtr.cpp:56–65`: for resolved non-null input, that function invokes `ResolveObjectHandleNoRead(LocalHandle)->GetOuter()`. The input is already resolved, but the subsequent ordinary UObject GetOuter still takes the previously audited outer conversion path. Checking the returned wrapper's IsResolved is too late to exclude effects during the call.
- The unresolved branch returns packed-reference outer information. `Private/UObject/ObjectHandleIndex.cpp:345–391` reconstructs that information from package/path identifiers, with a weak-object branch that itself calls GetOuter. This is not direct evidence of the present OuterPrivate wrapper on a live object. Manufacturing an unresolved reference from a path would substitute metadata identity and add bookkeeping, not solve stored-wrapper capture.

Therefore neither public-wrapper forwarding nor packed path reconstruction is an accepted bypass. Existing2/2 refusal evidence is unchanged; another identical refusal run would not unblock capture.

## Required capability (hypothetical, no existing API claimed)

An engine-owned integration would need a supported exported operation that observes a live object's stored outer wrapper **inside the owning engine module**, without returning its private storage address. Do not redeclare the existing friend in the plugin or add engine private include paths.

Result states must distinguish:

| State | Meaning |
| --- | --- |
| Unsupported | Engine version/layout/handle configuration not admitted; no object access. |
| RefusedContext | Wrong thread, shutdown, GC phase or excluded execution context. |
| NullInput | No supplied object; NOT an observed null outer. |
| Unresolved | Stored outer wrapper is unresolved; no Get/resolve/path/load. |
| ResolvedNull | Stored wrapper is resolved and null. |
| ResolvedObject | Stored wrapper is resolved and contains a borrowed live object pointer; validity/lifetime gates still apply. |
| Invalid | A resolved pointer fails admitted object-state checks; no payload/path inspection. |

A success boolean alone is inadequate: nullptr must not merge unresolved with resolved-null. Failure diagnostics must be constant/bounded and never format object names/paths. No creation, caching of resolved handles, repair, normalization, dirtying or hierarchy inference.

## Read ordering and lifetime

1. Caller supplies an already-live borrowed object protected through acquisition; a naked pointer is not an authentication mechanism. Engine integration checks context before object storage access.
2. Read/copy the actual stored outer wrapper through engine-owned access; inspect resolution state before converting it to a raw pointer. Only a confirmed-resolved wrapper may be extracted using audited no-resolve/no-tracking semantics. Do not use the current engine-private accessor's name as proof: its non-remote implementation still performs ordinary conversion.
3. Keep the source object protected for all reads. The interval between extracting an outer pointer and pinning it requires an explicitly reviewed synchronous engine/caller contract; the API must not advertise race-free acquisition merely because it checks IsValid twice.
4. Prefer a private capture context owning guards and storage baselines across an entire invocation. No persistent roots, no pointer-based public request parameters, and no borrowed pointer in serialized output. If an exported API returns a temporary strong reference instead, its bookkeeping/ABI/release semantics must be specified and separately authorized.
5. Repeat the same storage observation during final bounded checks. Equal before/after values detect observed drift only, not ABA or atomic coherence. Revisions/mutation exclusion remain a separate unsolved requirement.

## Integration admission

- An explicit versioned engine capability must attest the operation's semantics and handle configuration; the plugin must fail closed when it is absent or incompatible. No module macro override to contradict the engine binary.
- Existing narrow no-late/no-remote gate remains available only within its declared contract; do not make a handwritten boolean claim equivalent to the missing capability.
- Any engine patch, custom build, replacement DLL, live plugin install or real asset capture requires a separately agreed scope. No such work is started here. Standard installed-engine binaries do not gain a new exported capability merely because this document describes one.
- Do not retrofit existing resolved synthetic receipts into acceptance for the new integration. Native implementation and plugin caller need independent compilation/runtime verification under the exact installed artifacts.

## Future evidence needed, not a run plan or permission

Exact states for null/resolved-null/resolved/unresolved; direct stored-wrapper pre/post equality; no handle resolution/loading callbacks; no unintended field/dirty changes; temporary-reference release on every refusal; supported/unsupported capability behavior; explicit thread/GC refusal. Any fixture that constructs unresolved outer storage or changes engine flags needs a separate safe engine-owned design and authorization—no plugin offset writes or forged dangling-pointer tests.

Even a verified accessor would only remove the **storage-observation** blocker. A bounded chain still requires one shared392 guard cap (including outer objects), chain count/depth/cycle bounds, name/outer baselines, bounded text accounting and no-reentrancy review. It would not certify effective inherited selection, full recovery, native ownership, reparent readiness or motion.

## Current decision

Continue source-only work that does not depend on outer admission if useful, but do not claim a working editor inventory. To remove this blocker substantively, a separately scoped engine-integration decision is required. Repeating null/refusal tests or adding unconnected graph helpers is not evidence of progress through this gate.
