# Stored outer engine integration — source-only proposal

User selected «План engine-интеграции». Scope: this design and source inspection only. No installed UE edits, generated patch application, engine/plugin build, tests, DLL replacement, installation or editor calls. Current plugin's tested outer gate remains closed. All new API names below are **proposed**, not installed capabilities or commands that can be called now.

## Chosen boundary

Expose a small **out-of-line UObjectBase member** implemented inside CoreUObject, where the member can legally inspect its own OuterPrivate. Do not expose an address/reference to the wrapper, add a plugin friend, use offsets or include ObjectHandlePrivate.h from the plugin.

Initial implementation supports only local (`REMOTE=0`) engine configurations, including late resolution enabled. Remote semantics remain Unsupported. This is not a module override of UE_WITH_OBJECT_HANDLE_LATE_RESOLVE: keep the actual engine configuration intact and inspect the stored wrapper before extraction.

Use a separately built custom-engine plugin variant. Default existing plugin sources keep the integration disabled; no new hard engine import in the default build. Do not attempt to install a custom-export-linked plugin into the stock engine.

## Proposed files / responsibilities

Paths are relative to a separately scoped matching UE5.6 source checkout, **not changes made to the installed engine**:

| File | Proposed change |
| --- | --- |
| `Runtime/CoreUObject/Public/UObject/StoredOuterObservation.h` (new) | Versioned primitive result/status declarations, feature marker, capability query declaration. No EngineWire/Editor dependency. |
| `Runtime/CoreUObject/Public/UObject/UObjectBase.h` | Include the declaration or forward-declare its result type; declare exported const observation member. No new fields, virtual functions or UObject layout changes. |
| `Runtime/CoreUObject/Private/UObject/UObjectBase.cpp` | Implement member at engine boundary. Inspect OuterPrivate's const access-tracked wrapper through the existing owning-member access, never by calling GetOuter. |
| `Runtime/CoreUObject/Private/UObject/StoredOuterObservation.cpp` (new) | Capability query/context helper if separation improves organization; keep private storage access in the member. |
| CoreUObject native test area, location to confirm in matching checkout | State/ordering/unchanged-wrapper tests under a separately reviewed safe fixture design. No plugin raw storage writes. |
| Plugin `McpBPOwnershipSCSWalkOuter.h/.cpp` | Later opt-in adapter for this capability, preserving the existing stock-engine refusal path. |
| Plugin module build rules | Later explicit opt-in default0, only for a matched custom-engine artifact set. Do not change UE handle flags, public include paths to private engine headers or engine settings. |

Need a matching engine source/build toolchain and all required dependencies. The installed engine's reference headers alone are **not** evidence that a full engine build is available or reproducible. Neither RunUAT BuildPlugin nor rebuilding one plugin can add an export to CoreUObject.

## API sketch (design, not a compilable patch)

Proposed names: `FStoredOuterObservationV1`, `EStoredOuterObservationStateV1`, `QueryStoredOuterObservationCapabilityV1`, `UObjectBase::ObserveStoredOuterV1`.

Primitive result: fixed-width version/size, state enum, reserved fields zeroed, nullable borrowed `const UObject*` only for ResolvedObject. Distinct states: Unsupported, RefusedContext, NullInput (adapter/free-function boundary), Unresolved, ResolvedNull, ResolvedObject, Invalid. A member cannot safely be invoked on nullptr; the adapter handles null before dispatch. Never call a null object's member because another UE getter happens to tolerate it.

Capability query: version, result size, supported semantics and actual engine-side late/remote configuration. Query has no object input and no metadata initialization/loading. It must match the plugin's compiled declaration before any observation. Version1 attests only stored-wrapper observation without resolution/read tracking; it does not attest lifetime, global atomicity, path formatting or SCS ownership. Remote=1 yields Unsupported, not a fallback to ordinary getter.

Implementation sequence:

1. Initialize a fixed failure result, without object names or paths. Check game thread and engine shutdown/active-or-pending GC phases before touching the input. CoreUObject cannot depend on GEditor: the plugin must separately impose editor-idle/no-PIE/BP-not-compiling policy.
2. Require an already-live borrowed source object. Check its invalid/garbage/unreachable/destroying state using reviewed primitives; these checks cannot make a dangling C++ pointer safe.
3. Obtain `OuterPrivate.GetAccessTrackedObjectPtr()` as a **const wrapper reference**, then copy the wrapper to a local. The accessor merely exposes the existing wrapper to owning code; do not call its Get/conversion. Verify copy semantics introduce no resolution/tracking before implementation acceptance.
4. Inspect the local wrapper's IsResolved. If false, return Unresolved with no pointer extraction, path formatting, loading or property repair.
5. For confirmed-resolved storage only, use the engine's audited no-resolve/no-tracking extraction helper on the local wrapper. Null yields ResolvedNull. Non-null is checked under the borrowed lifetime policy, then yields ResolvedObject. Avoid TObjectPtr::Get if it introduces read tracking or another resolution route; use the actual reviewed engine helper rather than inventing a new reinterpret cast.
6. Do not overwrite OuterPrivate or normalize the handle. No callback/event invocation, reference resolver, class/CDO getter, path/name formatter or engine serializer. Return only the scoped observation.

Review must trace the chosen copy/extraction/null/validity helpers in the exact engine commit, including conditional branches. The sketch does not itself prove their behavior or the absence of ABA drift. No supported implementation exists until that review and separately authorized verification are complete.

## Lifetime remains a separate acquisition contract

This minimal API does not pin either object. Caller protects the source through entry and immediately admits/pins the resolved outer under the reviewed synchronous game-thread interval. No yielding, user code, forced GC or event pumping is allowed. Need to review whether any helper can reenter or whether explicit destruction can occur; double IsValid is not a lock. If this interval cannot be justified, redesign the engine API to acquire scoped protection internally and specify its release/ABI effects before coding—not an undocumented guard added midway.

Plugin guard cap392 includes source, outer-chain objects and all other held observations. Chain depth/cycle bounds and pre/post wrapper/name observations remain necessary. Before/after equality means only no detected drift, not an atomic snapshot. Strong reference acquisition mutates GC bookkeeping and may delay collection, as already disclosed in guard design.

## Plugin linkage / compatibility

Proposed project macro `ENGINEWIRE_WITH_STORED_OUTER_ACCESSOR` defaults0. It is an integration opt-in for a separate variant, **not** a redefinition of engine ABI/handle configuration. Only the enabled branch includes the new public engine header and references its exported query/member. Header marker/version mismatch must fail compilation; query mismatch must refuse before object access.

Important limitation: a statically imported new CoreUObject export missing from a stock DLL prevents plugin loading before any runtime gate. A version query does NOT make that case gracefully recoverable. Therefore enabled variant must ship only with its matched custom engine; retain default disabled variant for stock engine. Dynamic optional-export discovery is a different design with platform/module-lifetime/ABI review and is not silently included in this plan.

No hot copying DLLs into the current installation or loading the custom variant into an active stock editor. Use separate engine output, temporary host and compatible descriptors/BuildId/module manifests. Broader binary dependency changes require the normal engine build process, not renaming one DLL. Existing seven live plugin binaries and project assets stay untouched.

## Separate authorization stages

1. **Source preparation only:** confirm exact engine checkout/revision/license/dependencies, review helper semantics, prepare proposed source diff in a separate location; no patching the installed engine. Requires a destination and explicit edit scope.
2. **Custom engine build:** separately approve target/platform/configuration, resource/disk/time budget and failure/no-retry policy. Do not assume CoreUObject-only replacement is sufficient.
3. **Matched plugin staging build:** separate permission; confirm stock variant stays disabled and no live installation occurs.
4. **Isolated native verification:** exact tests, safe transient storage fixtures, handle/load/tracking observations, permitted GC bookkeeping, startup effects and no-auto-retry agreed in advance. Non-null reads and any unresolved-wrapper setup must be explicitly scoped.
5. **Live isolated-asset capture:** a later independent decision after bounded chain/walk and complete caller accounting are implemented and verified. Engine accessor tests alone do not authorize this.

No stage is granted by selecting this plan. Existing2/2 remains configuration-refusal evidence; existing17/17 remains helper/reference-accounting evidence. Do not relabel them as integration tests.

## Acceptance and stop conditions

- Exact state distinctions, no stored-wrapper rewrite/handle-resolution/read-tracking/load callbacks, bounded diagnostics, correct supported/unsupported capability gates, null checked before member dispatch.
- Safe fixtures for resolved-null/resolved/unresolved observations without relying on illegal plugin access or forged dangling pointers. If an unresolved outer fixture cannot be legally constructed, report that coverage absent; do not fake it with ordinary property wrappers.
- Explicit engine macro/version/artifact receipts, per-test states/warnings/errors and unchanged live plugin/asset hashes within agreed scope.
- Failure or unexpected loads/dirty changes stop the attempt; no automatic retry, fallback getter, engine flag toggle, repair, live installation or asset save.
- No claim of working live inventory until lifetime/bootstrap, bounded chain formatting, generated hierarchy/handler/config evidence and coherent capture gaps are independently addressed.

## Next decision needed

Before engine source work: choose/confirm a separate matching engine source checkout and approve a bounded source-only diff there. Until then this remains a concrete design, not an engine patch or a build request. No additional refusal-only test run is proposed.
