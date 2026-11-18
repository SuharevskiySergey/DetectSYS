# Static review notes — not verification

All observations here are source inspection. No apply/dry-run/compile/tests/editor execution. Existing production plugin/UE unchanged; snippets use hypothetical exports.

## Reviewed call paths

| Concern | Source finding / draft decision | Limit |
| --- | --- | --- |
| Type-safety before extraction | ObjectHandle.h147–193: local late-resolution bit0 distinguishes unresolved; null/resolved handles count type-safe. A type-unsafe packed reference (low bits3) is unresolved and is refused before raw extraction. | Does not authenticate arbitrary/malformed/dangling pointer bits. No forged-pointer tests proposed. |
| Extraction | ObjectPtr.h879–883 forwards to NoResolveObjectHandleNoRead; ObjectHandle.h468–479 copies the primitive handle and checks resolution before pointer extraction. | Remote branch explicitly unsupported. No custom reinterpret cast added to plugin. |
| Primitive read | ObjectHandle.h517–525 converts primitive resolved storage, without calling ObjectRef.Resolve. | Only within exact reviewed non-remote branch and caller lifetime contract. |
| Wrapper copy | ObjectPtr.h123–147,521–533 can perform GC barrier on wrapper copy. | Engine member draft uses const wrapper reference instead. Result/capability copies contain no TObjectPtr. |
| Read tracking | Chosen extraction helper does not call ResolveObjectHandle/OnHandleRead. IsResolved reads primitive state. | Source finding, not callback-instrumented runtime proof. Helpers must be re-reviewed on actual checkout. |
| Null | Adapter checks null before member call. Engine observation distinguishes resolved-null and unresolved. | Null source is not a null outer observation. |
| Lifetimes | Source pinned before member dispatch; returned outer immediately handed to shared guard set. | Already-live input/outer acquisition interval still requires exclusion of reentrancy/concurrent destruction. Guards are not a lock. |
| Input/result validation | Draft adapter validates exact versions/sizes/macros/reserved fields, enum and pointer-state consistency before pinning returned pointer. | An untrusted engine pointer is not made safe by checking the enum; engine binary must be trusted/matched. |

## Adapter draft

`PluginAdapter.cpp.fragment.txt` is a candidate separate custom-engine branch, deliberately NOT plugged into current sources. It keeps Unresolved/Invalid/Unsupported/Context/Capability errors distinct and never falls back to GetOuter/GetPathName or infers membership from a path. Failure results have no output pointer. After a later failure, already-acquired input guards stay in scope for RAII release and consumed reservations are not rolled back.

No Blueprint allowlist, owner relation, final state baseline, hierarchy selection or serialization is implemented here. They must precede any production use as appropriate; observing an outer is not admission of that owner. Adapter does not resolve a user-provided path or accept a pointer over an external endpoint.

## ABI / capability caveat

V1 declaration/layout must be frozen for a matched artifact set. Returning a C++ struct by value cannot safely negotiate arbitrary incompatible layouts: corruption/loader failure can happen before the size check. Therefore version/size fields detect ordinary semantic mismatches **within an already ABI-compatible build**, not arbitrary wrong DLL safety. New incompatible layouts need new versioned symbols and corresponding adapter, not silent V1 field changes. Static export absence is a load-time failure, not Unsupported. Default stock-engine plugin must not import these symbols.

## Required future checks (NOT prepared/runnable cases)

Subsequent preparation: `AccessorTests.cpp.fragment.txt` and `TEST_SCOPE.md` now sketch ONLY three smoke cases (capability/rooted-package resolved-null/worker refusal). They are text, not runnable/discovered/compiled tests, and do not fulfill the broader requirements below. No actual project test count or verification status changes.

1. Matched custom-engine source/BuildId/artifacts plus disabled stock variant: no accidental export import in default plugin.
2. Context/remote/unsupported/null before object access; negative capability/version/enum/pointer-state matrix using pure result fixtures (no fabricated UObject pointers).
3. Engine-owned legal raw wrapper fixtures for resolved-null/resolved/unresolved/type-unsafe unresolved states. Capture direct stored-wrapper before/after; instrument resolution/read tracking/load events. If impossible to set up legally, document missing coverage rather than forging an outer.
4. Strong-reference acquisition/release under explicit opt-in; source and outer dirty observations; no production asset capture/save. Already-rooted-object tests alone do not prove unrooted survival.
5. Explicitly authorized refusal scenarios for GC phases; no automatic forced collection, flag manipulation, pointer corruption or destruction tests.
6. No event pumping/yielding/callbacks inside acquisition interval; review every callee. Pre/post equality remains drift detection, not ABA/coherence proof.

These requirements are not achieved by the existing2/2 or17/17 receipts. No new Automation cases/counts or successful integration claim are added by this draft review.
