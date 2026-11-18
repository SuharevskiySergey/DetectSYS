#pragma once

#include "Domains/Blueprint/Queries/McpBPOwnershipSCSWalkBudget.h"
#include "UObject/StrongObjectPtr.h"

namespace McpBPOwnershipBindingReader
{
enum class ESCSWalkGuardStop : uint8
{
    None, ContextUnavailable, InvalidObject, Budget
};

// Invocation-local lifetime mechanism, NOT owner/path/SCS admission. Source-only,
// tests prepared but not built/run, no production caller. Changes UObject
// ref-count/root bookkeeping; NOT a pure read.
// Caller must construct/use/destroy synchronously on the game thread, before
// shutdown, without yielding, pumping events or invoking user code/GC.
class FSCSWalkGuards
{
public:
    explicit FSCSWalkGuards(FSCSWalkBudget& InBudget) : Budget(InBudget) {}
    FSCSWalkGuards(const FSCSWalkGuards&) = delete;
    FSCSWalkGuards& operator=(const FSCSWalkGuards&) = delete;

    // The raw pointer must ALREADY be live and externally protected through
    // this call (or obtained from an admitted, resolved wrapper under that
    // contract). Cannot authenticate dangling pointers. No handle resolution.
    // Null is a successful no-op only in an admissible context.
    bool HoldResolvedBorrowed(const UObject* Object);

    // Recheck context and all held objects before final raw comparisons.
    // Does not compare payload/outer fields or prove an atomic snapshot.
    bool Recheck();

    int32 GetCount() const { return Count; }
    ESCSWalkGuardStop GetStop() const { return Stop; }

private:
    bool CheckContext();
    bool Refuse(ESCSWalkGuardStop Reason);
    static bool IsUsable(const UObject* Object);

    FSCSWalkBudget& Budget;
    // Includes owner, node, class/template AND outer-chain objects in ONE cap.
    // Additional outer guards may reduce admissible node capacity; never spill.
    TStrongObjectPtr<const UObject> Objects[FSCSWalkBudget::MaxGuards];
    int32 Count = 0;
    ESCSWalkGuardStop Stop = ESCSWalkGuardStop::None;
};
} // namespace McpBPOwnershipBindingReader
