#include "Domains/Blueprint/Queries/McpBPOwnershipSCSWalkOuter.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSWalkGuards.h"

#include "UObject/Object.h"
#include "UObject/ObjectHandleDefines.h"

namespace McpBPOwnershipBindingReader
{
bool IsSCSWalkOuterStorageSupported()
{
#if UE_WITH_OBJECT_HANDLE_LATE_RESOLVE || UE_WITH_REMOTE_OBJECT_HANDLE
    return false;
#else
    return true;
#endif
}

FSCSWalkOuterRead ReadSCSWalkOuter(const UObject* Object, FSCSWalkGuards& Guards)
{
    FSCSWalkOuterRead Result;
#if UE_WITH_OBJECT_HANDLE_LATE_RESOLVE || UE_WITH_REMOTE_OBJECT_HANDLE
    // In particular, no-late + remote is NOT admitted: remote resolution can
    // touch resident state, and a no-resolve nullptr can conceal unknown outer.
    Result.Stop = ESCSWalkOuterStop::UnsupportedConfiguration;
#else
    if (!Object)
    {
        Result.Stop = ESCSWalkOuterStop::NullInput;
        return Result;
    }
    if (!Guards.HoldResolvedBorrowed(Object))
    {
        Result.Stop = ESCSWalkOuterStop::GuardRefusal;
        return Result;
    }
    const UObject* Outer = Object->GetOuter();
    if (!Guards.HoldResolvedBorrowed(Outer) || !Guards.Recheck())
    {
        Result.Stop = ESCSWalkOuterStop::GuardRefusal;
        return Result;
    }
    Result.Outer = Outer;
    Result.bAccepted = true;
    Result.Stop = ESCSWalkOuterStop::Observed;
#endif
    return Result;
}
} // namespace McpBPOwnershipBindingReader
