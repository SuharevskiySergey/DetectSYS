# Whole-SCS lifetime policy — UE5.6 source review

Subsequent outer-only exact2 **PASSED2/2**; tested plugin macros late1/remote0/editor-data1 confirm configuration refusal, NOT working outer acquisition. Supported getter branch compiled out. Receipt/details in verification plan; guard17 not rerun. No new non-null object reads/strong refs/outer-chain protection claim.

**New blocking outer-storage finding:** see `docs/BeholderOwnershipOuterStorageReview.md`. GetOuter's non-remote branch implicitly converts TNonAccessTrackedObjectPtr via ResolveObjectHandleNoRead. No-access-tracking is not no-resolution. Do not implement the proposed outer walker on that getter or treat resolved synthetic receipts as unresolved-handle validation. Strong guard17/17 remains scoped reference-accounting evidence; it does not certify outer acquisition. No new execution/code changes.

Latest separately authorized staging build + isolated exact17 **PASSED17/17**, exact names/zero per-test warnings-errors/exit0. Receipt `Saved/BeholderOwnershipSCSWalkGuardTests_cf8d3bcd6eb04ac88e52b81f2c38683a.json`; details/hashes in verification plan. Four guard cases compiled/exercised including rooted-package AddRef/dedup/nested release/shared-budget refusal/dirty-RootSet preservation; prior13 counter/frontier cases passed again. Supersedes unbuilt guard statuses below for tested version only. No unrooted survival/forced GC/pending-GC barrier/explicit destruction/outer-path lifetime validation. Seven live binaries unchanged/host asset files0; prior32 not rerun/not49/49. Further execution needs permission.

## Subsequent source-only guard draft

Four guard Automation cases are now source-prepared in `McpBPOwnershipSCSWalkGuardsTests.cpp`, NOT compiled/run: Defaults/NullIdleContext/WrongThread/BorrowedPackage. Positive package case is behind separate `-McpOwnershipGuardBookkeeping` isolated-host opt-in and would temporarily AddRef an existing rooted transient package; checks duplicate/nested-set counts, shared-budget refusal, release and dirty/RootSet observations. No new UObject/forced GC. Such a test does not validate collection survival or pending-GC barriers; no execution permission granted.49 source cases is not49/49; prior13/13 remains limited to budget/frontier.

`McpBPOwnershipSCSWalkGuards.h/.cpp` now implements a private invocation-local fixed392 strong-guard set, pointer-identity dedup, null no-op, sticky refusal and validity/context rechecks. Checks game thread/editor/no play/shutdown/active GC/pending unhash-purge-reachability before holding objects; rejects unreachable/destroying objects. **Not compiled/run; no caller/tests**. Existing readers unchanged. A borrowed address must already be protected through acquisition; this API cannot validate arbitrary dangling pointers. Destructor RAII must finish synchronously on the game thread before shutdown; it does not make misuse safe or undo reachability changes.

Budget clarification supersedes the role arithmetic below:392 is one hard total INCLUDING any outer-chain objects. External outer chains are not granted an extra allowance; they can exhaust the cap before128 nodes are admitted. This draft holds only explicitly supplied objects and does NOT traverse or validate outer chains, format paths, prove no reentrancy, admit SCS membership, compare raw baselines or enforce a caller's synchronous lifetime. No GC stress tests or native ownership claims. Prior13/13 tests only budget/frontier and does not cover this guard draft.

Status: source inspection only; no implementation, compilation, tests, GC scenarios or editor calls. Exact32 does not cover lifetime protection. Paths below are relative to the installed `Engine/Source/`.

## Findings

| Source | Observed contract |
| --- | --- |
| `Runtime/CoreUObject/Public/UObject/StrongObjectPtr.h:10` | Implementation is included from Core, not a sibling CoreUObject template header. |
| `Runtime/Core/Public/UObject/StrongObjectPtrTemplates.h:22–62,108–120,123–174` | Strong guard accepts an existing raw pointer; construction/Reset calls AddRef; destruction calls Reset/ReleaseUObject. Its IsValid only checks non-null, not UObject validity. No object loader or handle resolver appears in this path. |
| `Runtime/CoreUObject/Private/UObject/StrongObjectPtr.cpp:10–15` | ReleaseUObject calls ReleaseRef except during GExitPurge. Do not promise normal release bookkeeping during shutdown. |
| `Runtime/CoreUObject/Private/UObject/GarbageCollection.cpp:6406–6415` | UObjectBase AddRef/ReleaseRef delegate to FUObjectItem. |
| `Runtime/CoreUObject/Public/UObject/UObjectArray.h:372–415` | AddRef increments the count and sets RefCounted root flags; ReleaseRef decrements it and clears those flags at zero, with transaction bookkeeping. Not an observational no-op. |
| `Runtime/CoreUObject/Private/UObject/GarbageCollection.cpp:641–689` | Root flag changes use GRootsCritical and can change GRoots. Setting flags during pending incremental reachability can call MarkAsReachable. Releasing references does not undo that reachability marking or any delayed collection. |
| `Runtime/CoreUObject/Public/UObject/GCObjectScopeGuard.h:8–9,17–47,55–91` | Scope guards use FGCObject/TObjectPtr and collector callbacks. Single-object guard explicitly warns against trivially relocating containers. Array guard copies the input array; it is not a dynamic queue guard to which later-discovered nodes are automatically added. |
| `Runtime/CoreUObject/Public/UObject/UObjectGlobals.h:937–958` | Separate queries exist for incremental unhash, purge and reachability pending. IsGarbageCollecting alone is not a claim that every incremental phase is idle. |

## Proposed policy for a future implementation

Use invocation-local `TStrongObjectPtr<const UObject>` guards for admitted live objects, after existing resolution and validity gates. This is a design choice, **not an executed or compile-verified helper**. It avoids manual AddToRoot/RemoveFromRoot and container-relocated FGCObject instances, but explicitly permits temporary GC bookkeeping mutation and potentially delayed collection. It does not modify serialized asset properties by itself; that is not a verified no-dirty/no-save result for a complete walk.

Guard rules:

1. Entry requires the game thread, idle synchronous editor context, no shutdown/exit purge, no active GC and no pending incremental unhash/purge/reachability. Query refusal only: never flush GC, force collection, toggle settings or repair object flags to make the call admissible.
2. Caller must supply a currently live, externally owned Blueprint for the duration of initial admission. IsValid cannot safely authenticate an arbitrary dangling C++ pointer. No endpoint should accept a caller-provided numeric pointer or reinterpret a path as that lifetime contract.
3. Validate the borrowed Blueprint and pin it before path/schema/array work. Observe owner/SCS wrappers without resolution; validate each non-null resolved object and acquire its guard before further dereferencing it. Child targets need guards at discovery, **before** enqueueing, not when dequeued later.
4. Stay synchronous: no latent actions, task scheduling, event pumping, callbacks into user/Blueprint code, compilation, loading, CDO creation or explicit GC. Entry-phase queries are preconditions, not a lock against concurrent destruction. Audit every called function before treating this as a safe critical interval.
5. Identity table stores raw pointers only while corresponding guards are alive. Dedupe before acquiring another guard. Null targets do not require guards. A strong guard's IsValid is not a replacement for UObject validity/outer/admission checks on subsequent reads.
6. Final drift comparisons run before guard destruction. Return only pointer-free DTOs. Normal and early-return paths release guards by RAII; never cache or export them. Do not manually restore object root flags or ref-counts from a baseline, because other legitimate owners may change them.

This protects against collection of admitted objects under the reviewed engine contract; it does not prevent explicit destruction, pending-kill transitions, field mutation, editor reentrancy, replacement of array entries or ABA drift. A failed post-check remains refusal, not a claim that no concurrent change occurred.

## Guard budget must be explicit

Whole-walk bounds must include objects used only for pointer-path observations/final comparison, not merely the128 node payloads. Proposed per-invocation upper bound:

- Owner observations: at most8 distinct guards (Blueprint, package, generated class, generated-by target, BP/class SCS targets, BP/class handler targets); duplicates consume one slot. Unsupported extra ownership relations refuse rather than silently expand this set.
- Nodes: at most128 guards.
- Node component-class/template observations: at most256 guards (two per node; dedupe shared targets).
- Total maximum392 guards. An identity lookup may use the same fixed maximum; all guards remain invocation-local. Refuse before acquisition when the next distinct object would exceed the limit.

Do not traverse or guard the entire external template/class outer hierarchy just to claim a fixed bound. Existing path formatting may touch outer chains: audit its lifetime assumptions separately. Generated superclass traversal, template flag reads and arbitrary external payload access remain outside this guard model. If owner admission actually needs more than the eight listed roles, revise the design before implementation, not the running limit dynamically.

The392 bound is proposed, not enforced or runtime verified. Refcount bookkeeping and root-set internals may allocate beyond this local count. There is no peak-memory guarantee.

## Remaining blockers / next implementation boundary

Additional source finding: `Runtime/CoreUObject/Private/UObject/UObjectBaseUtility.cpp:38–82` implements GetPathName by recursively calling outer.GetPathName, then consulting outer class and outer's outer class for delimiters, and appending FName text. It does not bound outer depth, protect that chain with local strong guards or pre-admit output length. No loading/event callback is visible in this function body, but that alone does not audit all callees. The recursive formatter must not be treated as a bounded/fully guarded operation just because the starting target was pinned. A future formatter needs separately bounded, validated and lifetime-protected outer-chain observations, or a documented caller lifetime guarantee; the proposed392 guards do not yet include arbitrary external outer chains. No live formatter is implemented.

- Audit bootstrap/callee reentrancy and path formatting/outer-chain lifetime, including external class/template paths. Strong guards alone do not close these gaps.
- Define one private capture context that owns guards, bounded baselines, queue and budget together. Admission handles must not be forgeable public parameters.
- Decide whether existing owner/list reader calls can be used only for initial gates without retaining duplicated snapshots or leaving unguarded path operations. Do not silently transfer their old exact32 evidence to a new guarded implementation.
- Any eventual execution permission must disclose temporary ref-count/root bookkeeping and delayed-collection effects, not advertise an entirely side-effect-free read. GC/lifetime stress tests would need a separately specified scope.

Existing readers remain unchanged and retain their documented lifetime limitations. No live install, asset capture/save, Blueprint compile, PIE, reparent or motion is authorized by this source review.
