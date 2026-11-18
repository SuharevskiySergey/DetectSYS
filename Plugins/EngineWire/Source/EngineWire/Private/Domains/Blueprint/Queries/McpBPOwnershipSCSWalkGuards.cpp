#include "Domains/Blueprint/Queries/McpBPOwnershipSCSWalkGuards.h"

#include "CoreGlobals.h"
#include "Editor.h"
#include "UObject/GarbageCollection.h"
#include "UObject/Object.h"
#include "UObject/UObjectGlobals.h"

namespace McpBPOwnershipBindingReader
{
bool FSCSWalkGuards::Refuse(ESCSWalkGuardStop Reason)
{
    if (Stop == ESCSWalkGuardStop::None) Stop = Reason;
    return false;
}

bool FSCSWalkGuards::CheckContext()
{
    if (Stop != ESCSWalkGuardStop::None) return false;
    // Short circuit before touching editor/GC state from a worker thread.
    if (!IsInGameThread() || IsEngineExitRequested() || GExitPurge
        || !GEditor || GEditor->IsPlaySessionInProgress()
        || IsGarbageCollecting() || IsIncrementalUnhashPending()
        || IsIncrementalPurgePending() || IsIncrementalReachabilityAnalysisPending())
        return Refuse(ESCSWalkGuardStop::ContextUnavailable);
    if (Budget.IsStopped()) return Refuse(ESCSWalkGuardStop::Budget);
    return true;
}

bool FSCSWalkGuards::IsUsable(const UObject* Object)
{
    // These checks still require a valid borrowed address. StrongPtr::IsValid
    // only tests non-null, so it is intentionally not used for object validity.
    return IsValid(Object) && !Object->IsUnreachable()
        && !Object->HasAnyFlags(RF_BeginDestroyed | RF_FinishDestroyed);
}

bool FSCSWalkGuards::HoldResolvedBorrowed(const UObject* Object)
{
    if (!CheckContext()) return false;
    if (!Object) return true;
    if (!IsUsable(Object)) return Refuse(ESCSWalkGuardStop::InvalidObject);
    for (int32 Index = 0; Index < Count; ++Index)
        if (Objects[Index].Get() == Object) return true;
    if (Count == FSCSWalkBudget::MaxGuards) return Refuse(ESCSWalkGuardStop::Budget);
    if (!Budget.ReserveGuard()) return Refuse(ESCSWalkGuardStop::Budget);
    Objects[Count++].Reset(Object);
    // No path/getter/load/outer traversal. A post-check can observe failure but
    // is NOT exclusion against explicit destruction or concurrent mutation.
    if (!IsUsable(Object)) return Refuse(ESCSWalkGuardStop::InvalidObject);
    return true;
}

bool FSCSWalkGuards::Recheck()
{
    if (!CheckContext()) return false;
    for (int32 Index = 0; Index < Count; ++Index)
        if (!IsUsable(Objects[Index].Get())) return Refuse(ESCSWalkGuardStop::InvalidObject);
    return true;
}
} // namespace McpBPOwnershipBindingReader
