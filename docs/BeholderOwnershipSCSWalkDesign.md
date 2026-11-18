# Bounded whole-SCS walk — source-only design

Latest separate outer-only exact2 **PASSED2/2**: tested plugin macros late1/remote0/editor-data1, configuration refusal remains closed. Receipt/details in verification plan. Supported getter branch compiled OUT; no outer capture/lifetime/chain validation. Prior17/32 not rerun/not51/51. Seven live binaries unchanged/host asset files0; further execution needs permission. This does not unblock the editor walk.

Latest scoped verification: guards+frontier+budget exact17 **PASSED17/17**, exact names/zero per-test warnings-errors/exit0. Receipt/details in verification plan. Guard sources/four cases now compiled/exercised with existing rooted transient-package temporary refs and release; prior13 passed again. NOT unrooted survival/pending-GC/outer paths/live SCS admission/coherent capture. Supersedes unbuilt guard statuses below for tested version only; no production walk/caller. Prior32 not rerun/not49/49; seven live binaries unchanged/host asset files0. Further execution needs permission.

Latest separate staging build + isolated frontier/budget exact13 **PASSED13/13**, exact names/zero per-test warnings-errors/exit0. Receipt `Saved/BeholderOwnershipSCSWalkFrontierTests_13d9e425261a414bba9f2666ad6d4967.json`; details/hashes in verification plan. Frontier/header/six cases and prior seven budget cases compiled/exercised; supersedes unbuilt/unrun helper statuses below for tested version only. Opaque local-address FIFO, not live SCS admission/traversal/lifetime/path/coherent capture. Old32 not rerun/not45/45; seven live binaries unchanged/host asset files0. Further execution needs permission.

Latest scoped verification: separate staging build + isolated budget-only exact7 **PASSED7/7**, exact names/all Success/zero per-test warnings-errors/exit0. Receipt `Saved/BeholderOwnershipSCSWalkBudgetTests_7bcf820fc8c24a3698251af9bd6c92a1.json`; details/hashes in verification plan. Budget primitive/seven cases compiled and exercised; supersedes unbuilt counter status below only for tested version. No integrated walk/caller/GC guard/path lifetime verification. Prior32 not rerun: not39/39. Seven live binaries unchanged/host asset files0; further execution requires permission.

Status: design, not implemented or verified. Latest exact32 validates the existing single-parent children reader, not this walk. No build, tests or editor calls were performed for this design.

## Why the existing readers cannot simply be composed

`ReadSCSNodePayload` requires live pointer membership in raw roots or registry. `ReadSCSChildPointers` calls it before and after reading children. A child-only target can therefore be observed but cannot become the next parent. Removing that membership check would weaken the already-tested API; matching a DTO path to a live object would not establish pointer identity.

Both readers also call `ReadSCSRawLists` repeatedly and allocate independent DTOs. Adding their retained text sizes after return would not enforce one pre-admission budget. Count and dirty rechecks do not detect same-count edge replacement or metadata changes while the package remains dirty.

Keep these APIs unchanged. A future whole-SCS reader needs its own private, invocation-local admission context; no public `allowUnlisted` switch or caller-supplied path/provenance token.

## Invocation-local admission

Source-only FIFO primitive added in `McpBPOwnershipSCSWalkFrontier.h`, **not compiled/tested/integrated**. Fixed128 records store opaque borrowed identities, first-discovery source/index/parent and depth; no UObject dereference or resolution. Roots then registry must be presented in ascending slot order, seeds sealed before FIFO expansion; whole-parent child count charged before slots, repeats/nulls preserve slot charges without adding identities. Caller retains ordered edge DTOs separately, performs lifetime/admission checks and validates full seed arrays BEFORE feeding slots (the primitive only charges individual seed slots). PeekNextParent allows reading the next admitted parent's child count before BeginNextParent. Shared-budget reservations are not rolled back on later failure. No raw pointer/provenance token may leave the invocation, and no frontier result certifies effective membership, true cycles or snapshot completeness. Existing seven budget tests do not cover this new header.

1. Require game thread and the existing Blueprint/SCS owner gates. Copy admitted schemas once; metadata availability is not instance admission.
2. Read roots and registry separately, in raw order, retaining nulls and duplicates. Seed one FIFO in roots order followed by registry order. Never call GetAllNodes or populate AllNodes.
3. Intern resolved valid nodes by **live pointer identity**, never path, GUID or display name. Each node must have the exact admitted SCS as outer. Preserve every root/registry slot independently of this internal identity table.
4. A new child-only node is admitted only from a resolved raw ChildNodes wrapper of an already admitted parent in this invocation. Record parent identity-table index and raw child index before queuing it. Revalidate the source edge against the same pointer before reading the child's payload. Admission cannot be exported/reused by another invocation.
5. Read each admitted payload and child array once in FIFO order. All edges remain ordered observations, including null, duplicate, self and back edges. Existing targets are not queued again. Discovery depth is first-seen BFS depth; it is not maximum graph path length or evidence that the SCS is a tree.
6. Do not label every repeated target a cycle: a diamond/shared child is also repeated. Initial implementation should record repeat identity only. A separate bounded graph analysis would be needed for cycle classification; termination itself follows from visited identities and limits.

Private context holds identity-to-index entries, queue, first-discovery provenance, and raw storage baselines. No pointers, wrappers or reusable admission handles leave it in the output DTO. A child-only node with exact outer is not thereby certified as engine-effective membership.

## One inventory budget

Source-only primitive now exists in `McpBPOwnershipSCSWalkBudget.h`: allocation-free counters with sticky refusal, subtract-before-add overflow checks, global child slots, new-node depth checks, guards and normal-text allowance excluding512 diagnostic TCHAR. **Not built/tested/integrated**, no caller. This is bookkeeping only; a caller must reserve before retaining actual data and independently perform identity/lifetime/admission checks. It neither traverses SCS nor enforces field accounting automatically. Diagnostic formatting and outer-chain guard accounting remain unimplemented;392 is still a proposed role bound, not a certified whole-walk limit.

Proposed fixed limits: roots128, registry128, unique nodes128, **total** retained child slots256, discovery depth8 (seeds depth0), retained text240000 TCHAR. Existing single-parent256 does not imply256 per parent in this API.

- Admit each source array count before copying/iterating its entries. Charge all child slots, including nulls/duplicates/repeats, against the remaining global edge count before reading that array. An oversized array causes refusal, not accepted truncation.
- Check node capacity before adding a new identity or queue entry. Reject a newly discovered target beyond depth8; an already visited back edge does not consume a new depth allowance.
- A shared budget object charges all output path copies, node names (including retained FNames measured as text), errors and gap fields. Reserve a fixed bounded diagnostic allowance before reading. Charge before retaining a field; overflow uses a constant diagnostic and cannot retain an oversized field.
- Repeated path strings in different DTO fields are charged repeatedly. Queue and baseline storage also need fixed node/edge/count bounds. Do not retain nested owner/list/node-reader results in each node.
- Path generation and FName-to-string conversion may allocate temporary strings before their lengths are known. This is a retained-content budget, **not** a peak-memory, allocator-byte or serialized-byte guarantee. A stronger claim requires a separately audited bounded formatting/storage strategy.
- No multi-layer capture is authorized by these per-SCS bounds. An inherited coordinator needs its own shared layer/node/edge/text limits before composing inventories.

## Lifetime and consistency gates remain blocking

Missing integration boundary is now specified in `docs/BeholderOwnershipOuterAccessorContract.md`: public TObjectPtr/FObjectPtr forwarding does not bypass the stored-outer blocker, and packed metadata is not current live storage evidence. Engine-owned exported stateful-resolution observation would need separate scope/versioned admission/lifetime review; no such API is claimed installed. No further refusal-only tests/helpers added for this finding, no engine changes/execution.

Source-only single-outer configuration gate now exists in `McpBPOwnershipSCSWalkOuter.h/.cpp`, NOT compiled/tested/no caller. Only no-late/no-remote configurations can compile the guarded getter; default editor-data late resolve is refused, not disabled. No engine-private accessor or module flag override. This does not unblock editor capture or certify lifetime/drift;17/17 predates it. See OuterStorageReview follow-up.

Outer-storage gate is additionally blocked: `docs/BeholderOwnershipOuterStorageReview.md` traces GetOuter's ordinary implicit conversion to ResolveObjectHandleNoRead. Avoiding GetPathName is insufficient. No configuration-independent stored-outer no-resolution accessor is established; exact-outer live admission must not be weakened to paths or bypassed through existing readers. No outer-walker implementation added; no engine edits/resolution scope authorized.

Source-only guard mechanism added as `McpBPOwnershipSCSWalkGuards.h/.cpp`: fixed392 strong guards including outer objects, dedup/context/validity checks and recheck, no caller/tests. NOT compiled/executed,13/13 does not cover it. More outer objects reduce available capacity, never expand the cap. Bootstrap borrowed-pointer safety, caller non-reentrancy, guarded outer traversal/path formatting and baseline comparisons remain unimplemented; existing readers are not silently wrapped or re-certified.

UE5.6 source review is recorded in `docs/BeholderOwnershipSCSLifetimeReview.md`. Proposed mechanism: invocation-local strong guards with an explicit392-object ceiling and refusal during active/pending GC phases. Strong guards mutate ref-count/root bookkeeping and may delay collection; they are not zero-side-effect reads. Bootstrap/callee reentrancy and outer-chain/path lifetime still block a live implementation. Existing readers are unchanged; no runtime lifetime verification performed.

Do not implement the live walk until the UE5.6 lifetime policy is source-reviewed: game-thread execution alone is not an explicit root/lifetime guarantee. Decide how admitted objects remain protected without resolving handles or creating persistent roots; account for any temporary strong references and release them on every exit.

Capture raw root/registry/child slot identities and node fields for a final comparison pass, not just counts. The comparison must include wrapper resolution state, exact pointers, owner/generated-by/SCS relations, GUID/names/attachments/native-parent bool and template/class wrappers. Refuse on any difference, invalidation or unresolved state; never repair. Final comparison must itself use admitted schemas and count limits, not resolving getters.

This can detect observed drift, not prove atomicity or absence of ABA changes. No producer revisions or editor mutation exclusion have been established. `bComplete` and `bEngineIdentityVerified` stay false even if a future raw walk finishes. Avoid wording that presents pre/post equality as a coherent engine snapshot.

## Failure output

On any admission, count, text, lifetime or drift failure: `bAccepted=false`, an explicit stop reason, bounded diagnostic and optionally bounded prefix evidence. Offending edge provenance may be retained only if capacity/text were already admitted. Never retain a target payload after its admission failed. Limit refusal need not preserve an offending path that exceeds budget.

Whole-walk output must add explicit first-discovery provenance and target node indices; current `FSCSChildEdge` has only source index/child index/path observation. Do not reinterpret equal path strings as equal target indices. DTO changes should be additive and explicitly default to unknown, with no effective-selection recommendation.

## Future verification scope (not permission to run)

Outer gate: two source-prepared cases Defaults/ConfigurationRefusal report compiled macros and assert null/config refusal without guard acquisition, NOT compiled/run.51 source cases is not51/51. Pointer-only write-site source audit is insufficient to relax late/remote refusal; no live non-null outer capture or path formatting is validated. See OuterStorageReview.

Four additional guard cases prepared source-only (Defaults/NullIdleContext/WrongThread/BorrowedPackage), NOT compiled/run. Existing rooted transient-package pinning needs explicit isolated-host `-McpOwnershipGuardBookkeeping`; temporary ref-count mutations disclosed in verification plan. No actual collection/outer paths/live SCS capture exercised;49 source cases is not49/49. No new execution performed.

Six source-only frontier cases now prepared: Defaults/SeedProvenance/BreadthFirst/DepthAndBackEdges/SharedLimits/PhasesAndRefusal in `McpBPOwnershipSCSWalkFrontierTests.cpp`. Use only local addresses, no UObject. Assert FIFO/dedup/provenance/limits and refusal behavior, not lifetime/native SCS identity or true engine cycle classification. **Not compiled/run**,45 source cases is not45/45; latest7/7 only covers the previously tested budget version. Details in verification plan.

Seven counter-only Automation cases are now prepared in `McpBPOwnershipSCSWalkBudgetTests.cpp` (see verification plan). **Not compiled/run**; they do not exercise a walk, live identity deduplication, path formatting, diagnostics allocation or GC guards. Source case count39 is not39/39. Existing32 receipt remains historical coverage of the prior tested version.

- Child-only chain with empty registry; roots/registry divergence and registry-only islands.
- Null/duplicate/self/two-node back edges and a diamond; exact ordering, first-discovery provenance and one payload per identity, no registry rewrite.
- Node128/129, aggregate edges256/257 across multiple parents, depth8/9; visited back edges at depth8 must not spuriously hit depth9.
- All retained text contributions, diagnostic reserve, oversized path refusal and partial output accounting.
- Wrong outer, unresolved/invalid targets, source-edge replacement with unchanged count, payload change with unchanged dirty bit, owner drift and lifetime refusal.
- Fixture setup/restoration and no dirty/asset writes independently checked. Synthetic arrays still do not certify genuine compiled inheritance or effective template selection.

Only after the lifetime/storage-baseline review should implementation and transient fixtures be prepared. Any build, native execution, live capture or install needs fresh explicit scope. No Blueprint compile/save, reparent, PIE or motion is part of this design.
