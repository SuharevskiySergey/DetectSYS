#pragma once

#include "CoreMinimal.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSWalkBudget.h"

namespace McpBPOwnershipBindingReader
{
enum class ESCSWalkDiscovery : uint8 { Root, Registry, Child };
enum class ESCSWalkFrontierStop : uint8 { None, InvalidProvenance, WrongPhase, Budget };

struct FSCSWalkDiscoveryRecord
{
    // Borrowed opaque identity, private to an invocation. NEVER dereferenced by
    // this helper, serialized, reconstructed from a path or treated as admission.
    const void* Identity = nullptr;
    ESCSWalkDiscovery Source = ESCSWalkDiscovery::Root;
    int32 SourceNode = INDEX_NONE;
    int32 SourceIndex = INDEX_NONE;
    int32 Depth = INDEX_NONE;
};

// Source-only fixed-capacity FIFO bookkeeping. Tests prepared, not built/run;
// no production caller or UObject admission.
// Caller must keep a single shared budget and every non-null identity alive,
// resolved and admitted. Do not copy/export this object or its borrowed records.
// Caller retains ALL raw slots separately; this table stores first discovery only.
class FSCSWalkFrontier
{
public:
    explicit FSCSWalkFrontier(FSCSWalkBudget& InBudget) : Budget(InBudget) {}
    FSCSWalkFrontier(const FSCSWalkFrontier&) = delete;
    FSCSWalkFrontier& operator=(const FSCSWalkFrontier&) = delete;

    // Roots must precede registry slots; every list's raw indices must be
    // presented exactly once in ascending order, including null/duplicate slots.
    bool AddRoot(const void* Identity, int32 RawIndex, int32& OutNode)
    {
        OutNode = INDEX_NONE;
        if (!CanProceed()) return false;
        if (bWalking || bRegistryStarted) return Refuse(ESCSWalkFrontierStop::WrongPhase);
        if (RawIndex != NextRoot) return Refuse(ESCSWalkFrontierStop::InvalidProvenance);
        if (!Budget.ReserveRoots(1)) return Refuse(ESCSWalkFrontierStop::Budget);
        if (!Discover(Identity, ESCSWalkDiscovery::Root, INDEX_NONE, RawIndex, 0, OutNode)) return false;
        ++NextRoot;
        return true;
    }

    bool AddRegistry(const void* Identity, int32 RawIndex, int32& OutNode)
    {
        OutNode = INDEX_NONE;
        if (!CanProceed()) return false;
        if (bWalking) return Refuse(ESCSWalkFrontierStop::WrongPhase);
        if (RawIndex != NextRegistry) return Refuse(ESCSWalkFrontierStop::InvalidProvenance);
        bRegistryStarted = true;
        if (!Budget.ReserveRegistry(1)) return Refuse(ESCSWalkFrontierStop::Budget);
        if (!Discover(Identity, ESCSWalkDiscovery::Registry, INDEX_NONE, RawIndex, 0, OutNode)) return false;
        ++NextRegistry;
        return true;
    }

    // Seal all seeds before expanding ANY parent, including root-only inputs.
    bool SealSeeds()
    {
        if (!CanProceed()) return false;
        if (bWalking) return Refuse(ESCSWalkFrontierStop::WrongPhase);
        bWalking = true;
        return true;
    }

    // Identify the next parent so caller can validate it and read its array
    // count before BeginNextParent. Pointer lifetime/admission is still external.
    int32 PeekNextParent() const
    {
        return Stop == ESCSWalkFrontierStop::None && !Budget.IsStopped()
            && bWalking && NextChild == ActiveChildCount && NextParent < Count
            ? NextParent : INDEX_NONE;
    }

    // Reserve the WHOLE child array before reading its first slot. Exactly one
    // array per identity, in FIFO order. Complete all slots before next parent.
    // OutNode==INDEX_NONE with true means exhausted, not failed or complete SCS.
    bool BeginNextParent(int32 ChildCount, int32& OutNode)
    {
        OutNode = INDEX_NONE;
        if (!CanProceed()) return false;
        if (!bWalking || NextChild != ActiveChildCount) return Refuse(ESCSWalkFrontierStop::WrongPhase);
        if (NextParent == Count)
        {
            if (ChildCount != 0) return Refuse(ESCSWalkFrontierStop::InvalidProvenance);
            ActiveParent = INDEX_NONE;
            return true;
        }
        if (!Budget.ReserveChildren(ChildCount)) return Refuse(ESCSWalkFrontierStop::Budget);
        ActiveParent = NextParent++;
        ActiveChildCount = ChildCount;
        NextChild = 0;
        OutNode = ActiveParent;
        return true;
    }

    bool AddChild(const void* Identity, int32 RawIndex, int32& OutNode)
    {
        OutNode = INDEX_NONE;
        if (!CanProceed()) return false;
        if (!bWalking || ActiveParent == INDEX_NONE || NextChild >= ActiveChildCount)
            return Refuse(ESCSWalkFrontierStop::WrongPhase);
        if (RawIndex != NextChild) return Refuse(ESCSWalkFrontierStop::InvalidProvenance);
        if (!Discover(Identity, ESCSWalkDiscovery::Child, ActiveParent, RawIndex,
            Records[ActiveParent].Depth + 1, OutNode)) return false;
        ++NextChild;
        return true;
    }

    int32 GetCount() const { return Count; }
    ESCSWalkFrontierStop GetStop() const { return Stop; }
    const FSCSWalkDiscoveryRecord* GetRecord(int32 Index) const
    {
        return Index >= 0 && Index < Count ? &Records[Index] : nullptr;
    }

private:
    bool Refuse(ESCSWalkFrontierStop Reason)
    {
        if (Stop == ESCSWalkFrontierStop::None) Stop = Reason;
        return false;
    }

    bool CanProceed()
    {
        if (Stop != ESCSWalkFrontierStop::None) return false;
        if (Budget.IsStopped()) return Refuse(ESCSWalkFrontierStop::Budget);
        return true;
    }

    bool Discover(const void* Identity, ESCSWalkDiscovery Source, int32 SourceNode,
        int32 SourceIndex, int32 Depth, int32& OutNode)
    {
        if (!Identity) return true; // Null slot has provenance but no payload.
        for (int32 Index = 0; Index < Count; ++Index)
        {
            if (Records[Index].Identity == Identity)
            {
                OutNode = Index;
                return true; // Repeat/back edge: no new node or depth charge.
            }
        }
        // Local capacity remains a hard bound even if caller used the shared
        // budget elsewhere. All preceding successful reservations stay charged
        // on refusal; this is not transactional allocation or rollback.
        if (Count == FSCSWalkBudget::MaxNodes) return Refuse(ESCSWalkFrontierStop::Budget);
        if (!Budget.ReserveNode(Depth)) return Refuse(ESCSWalkFrontierStop::Budget);
        OutNode = Count++;
        Records[OutNode] = {Identity, Source, SourceNode, SourceIndex, Depth};
        return true;
    }

    FSCSWalkBudget& Budget;
    FSCSWalkDiscoveryRecord Records[FSCSWalkBudget::MaxNodes];
    ESCSWalkFrontierStop Stop = ESCSWalkFrontierStop::None;
    int32 Count = 0;
    int32 NextRoot = 0;
    int32 NextRegistry = 0;
    int32 NextParent = 0;
    int32 ActiveParent = INDEX_NONE;
    int32 NextChild = 0;
    int32 ActiveChildCount = 0;
    bool bRegistryStarted = false;
    bool bWalking = false;
};
} // namespace McpBPOwnershipBindingReader
