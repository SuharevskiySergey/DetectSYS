# Outer storage — no-resolution blocker

Public-wrapper follow-up: `docs/BeholderOwnershipOuterAccessorContract.md` records TObjectPtr→FObjectPtr::GetOuter resolved forwarding back to ordinary GetOuter, and packed-outer metadata/weak-object behavior. Neither is an admitted bypass. That document specifies the missing engine-owned stored-wrapper capability without claiming it exists or authorizing engine edits/build/install. Current tested gate unchanged; no new code/test/editor execution. More identical refusal tests do not unblock capture.

Latest authorized staging build + isolated exact2 **PASSED2/2**, exact names/zero per-test warnings-errors/exit0. Receipt `Saved/BeholderOwnershipSCSWalkOuterTests_d5571e2aa75244acb9e33fae4c4f37b8.json`; details/hashes in verification plan. Tested plugin TU reports **LATE_RESOLVE=1 REMOTE=0 EDITORONLY_DATA=1**. Configuration gate correctly stays closed. Supersedes unbuilt refusal-branch/two-case status below; supported getter branch compiled OUT, not validated. No non-null test read/strong refs or outer-chain lifetime evidence. Seven live binaries unchanged/host asset files0; prior17/32 not rerun/not51/51. Editor live walk remains blocked; no macro overrides/engine edits authorized. Further execution needs permission.

Source review only, no builds/tests/editor calls. This finding concerns outer access, not the tested strong-reference accounting mechanism.

## UE5.6 call chain

Installed engine sources relative to `Engine/Source/`:

- `Runtime/CoreUObject/Public/UObject/UObjectBase.h:195–203`: GetOuter uses `NoAccessTrackingGetNoResolve(OuterPrivate.GetAccessTrackedObjectPtr())` only under `UE_WITH_REMOTE_OBJECT_HANDLE`. The other branch returns `OuterPrivate` through its implicit pointer conversion.
- Same header around366: OuterPrivate is `ObjectPtr_Private::TNonAccessTrackedObjectPtr<UObject>`, not an exposed reflected FObjectProperty/TObjectPtr field.
- `Runtime/CoreUObject/Public/UObject/ObjectPtr.h:873–883`: `NoAccessTrackingGet` calls `ResolveObjectHandleNoRead`; the distinct `NoAccessTrackingGetNoResolve` calls `NoResolveObjectHandleNoRead`.
- Same header908–935: TNonAccessTrackedObjectPtr::Get uses NoAccessTrackingGet; implicit operator T* calls Get. Its GetNoResolve/access-tracked-wrapper accessors are available on the wrapper, but OuterPrivate itself is private to UObjectBase. Do not fabricate reflected lookup, layout offset, reinterpret cast or friend access to obtain it.
- `Runtime/CoreUObject/Private/UObject/UObjectBaseUtility.cpp:55–77`: GetPathName recursively calls GetOuter and checks outer classes for delimiters. Avoiding only GetPathName does not eliminate resolving outer access if a replacement walker calls GetOuter directly.

Conclusion: **GetOuter is not a configuration-independent no-resolution accessor.** No-read/access-tracking suppression does not establish that no object handle was resolved. This source call chain is not evidence that a particular existing test actually triggered resolution/loading; the tested synthetic outers were live resolved objects. The current build's handle configuration and unresolved-outer behavior have not been independently verified.

## Consequences for current code/evidence

Existing owner/list/node/children and structure readers use outer/path getters. Their successful receipts cover the documented resolved synthetic scenarios, not a universal no-resolution or lifetime guarantee. No previous success should be relabeled as an unresolved-handle test or coherent capture. Existing guards do not resolve handles themselves in HoldResolvedBorrowed, but they cannot certify what a caller did to obtain its raw pointer.

Do not silently change those tested APIs or weaken exact-outer admission to path/package/name equality. Equal paths are not live owner identity. An outer that was not safely observed must remain unavailable, not null or inferred from roots/registry membership. Without exact outer admission, a future live walk must refuse payload capture rather than call the existing readers as a fallback.

## Implementation gate

### Raw-pointer write-site audit (limited, not an admission proof)

Source-wide `OuterPrivate` search found bootstrap null initialization (`UObjectBase.cpp:125–130`), allocation constructor raw `UObject* InOuter` initialization (144–159), DeferredRegister's raw UPackage assignment (194–205), and LowLevelRename's raw UObject* assignment (270–303). `UObjectBase.h:76–81` additionally has a NoInit constructor retaining existing storage; LowLevelRename mentions whole-object transactional revert. Thus the ordinary writes examined are pointer-based, but the search does not establish a complete invariant for reconstructed/restored storage, GC/reference replacement, arbitrary engine integrations or the live object's history. Do not relax the gate merely because no textual unresolved assignment was found.

Two source-only Automation cases now prepared in `McpBPOwnershipSCSWalkOuterTests.cpp`: Defaults/ConfigurationRefusal. They report the test TU's actual compiled late-resolve/remote/editor-data macros and compare gate behavior for null input, with zero guard acquisition even after an arithmetic budget stop. **Not compiled/run**,51 source cases, not51/51. No non-null pointer read/pinning/loading, no guard opt-in needed for these two cases alone. Future results would attest tested plugin-branch behavior, not every engine DLL's macros, the unreachable supported branch on an unsupported build, or genuine outer lifetime/no-resolution behavior. Prior17/17 predates this source.

### Follow-up source findings and fail-closed draft

`CoreUObject/Private/UObject/ObjectHandlePrivate.h:9–23` defines the friend FObjectHandleUtils and its outer accessors. This is an engine-private header, NOT a supported plugin include boundary. Its `GetNonAccessTrackedOuterNoResolve` also uses the ordinary implicit conversion in the non-remote branch; the function name alone is not a configuration-independent guarantee. Do not include/copy/redeclare that friend into the plugin.

`CoreUObject/Public/UObject/ObjectHandle.h:420–465` makes the conversion behavior explicit: late-resolve branch can call ObjectRef.Resolve and replace the handle; remote branch can resolve/touch resident objects; ONLY the no-late/no-remote branch simply reads the pointer. `ObjectHandleDefines.h:10–21` defaults late resolve/tracking/type safety to `!UE_WITH_REMOTE_OBJECT_HANDLE && WITH_EDITORONLY_DATA`. Consequently the normal non-remote editor-data default is NOT a supported no-resolution configuration. Actual built macro values have not been measured; defaults are not a receipt of this editor binary's configuration.

Added source-only `McpBPOwnershipSCSWalkOuter.h/.cpp`: configuration query and invocation-local single-outer result. `#if LATE_RESOLVE || REMOTE` returns UnsupportedConfiguration before input dereference/ref acquisition. Only the both-disabled branch compiles GetOuter, acquires input/outer guards and rechecks; unknown/refusal is distinct from an accepted null outer. No engine-private header, offsets, flag overrides, new caller or changes to tested readers. **Not compiled/run**, no tests;17/17 does not cover it. Current editor may therefore refuse every live outer observation by design. Do not disable engine features or override module macros to make it pass: mismatched engine/plugin layout/semantics are not support.

This draft narrows the storage contract but does not solve the required editor capture: a supported editor stored-wrapper API is still absent. Even in a future supported configuration it requires an already-live borrowed input and synchronous guard contract; it neither proves bootstrap lifetime nor compares pre/post outer/name drift. No outer-chain walker or path formatter implemented, no engine modification/build/install authorized.

A native outer-chain reader is blocked until one of these is separately reviewed and scoped:

1. An engine-supported API that can inspect stored outer resolution state and obtain only an already-resolved pointer without tracking/resolving, including lifetime/bootstrap semantics. None has been established in this review.
2. A precisely verified engine/build configuration in which the relevant conversion cannot resolve/load, with a fail-closed compile/runtime gate and explicit supported-configuration contract. Do not assume that from editor version or a successful compile alone.
3. A separately authorized engine-side accessor/integration exposing the required stored wrapper observation. Engine source edits/builds/install are NOT requested or authorized here.

Changing the contract to permit resolution/loading would be a user-visible scope change, not an implementation detail; it is not the chosen recovery. A pathless DTO can avoid formatting but does NOT solve exact-outer admission by itself.

Once storage access is admitted, bounded traversal still needs cycle/depth checks, one shared guard cap including outer objects, name/outer baselines and bounded formatting. Strong references protect against collection only within their documented assumptions; they do not make the chain immutable or establish an atomic snapshot. There is no new outer-walker code, test fixture or endpoint.
