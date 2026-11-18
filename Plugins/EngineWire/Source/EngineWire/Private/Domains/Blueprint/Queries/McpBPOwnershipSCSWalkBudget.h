#pragma once

#include "CoreTypes.h"

namespace McpBPOwnershipBindingReader
{
// Source-only accounting primitive for a future walk, NOT object admission.
// No caller yet. Counts supplied by a caller must describe actual retained data.
// Does not bound formatting temporaries, allocator overhead or serialized bytes.
enum class ESCSWalkBudgetStop : uint8
{
    None, InvalidCount, Roots, Registry, Nodes, ChildSlots, Depth, Guards, Text
};

class FSCSWalkBudget
{
public:
    static constexpr int32 MaxRootSlots = 128;
    static constexpr int32 MaxRegistrySlots = 128;
    static constexpr int32 MaxNodes = 128;
    static constexpr int32 MaxChildSlots = 256;
    static constexpr int32 MaxDiscoveryDepth = 8;
    static constexpr int32 MaxGuards = 392;
    static constexpr int64 MaxTextChars = 240000;
    // Normal output cannot consume this allowance. Refusal output must use a
    // fixed diagnostic whose length fits it; this class does not format errors.
    static constexpr int64 DiagnosticReserveChars = 512;

    bool ReserveRoots(int32 Count)
    {
        return Reserve(Count, MaxRootSlots, RootSlots, ESCSWalkBudgetStop::Roots);
    }

    bool ReserveRegistry(int32 Count)
    {
        return Reserve(Count, MaxRegistrySlots, RegistrySlots, ESCSWalkBudgetStop::Registry);
    }

    // Charge an entire parent's array before copying any slot. Null, repeated
    // and back-edge targets consume slots just like newly discovered targets.
    bool ReserveChildren(int32 Count)
    {
        return Reserve(Count, MaxChildSlots, ChildSlots, ESCSWalkBudgetStop::ChildSlots);
    }

    // Call only for a NEW identity; an already visited back edge has no new
    // discovery depth. Pointer identity/deduplication is a caller obligation.
    bool ReserveNode(int32 DiscoveryDepth)
    {
        if (IsStopped()) return false;
        if (DiscoveryDepth < 0) return Refuse(ESCSWalkBudgetStop::InvalidCount);
        if (DiscoveryDepth > MaxDiscoveryDepth) return Refuse(ESCSWalkBudgetStop::Depth);
        return Reserve(1, MaxNodes, Nodes, ESCSWalkBudgetStop::Nodes);
    }

    bool ReserveGuard()
    {
        return Reserve(1, MaxGuards, Guards, ESCSWalkBudgetStop::Guards);
    }

    bool ReserveText(int64 Count)
    {
        if (IsStopped()) return false;
        if (Count < 0) return Refuse(ESCSWalkBudgetStop::InvalidCount);
        // Subtract before comparing: even INT64_MAX input cannot overflow.
        if (Count > MaxTextChars - DiagnosticReserveChars - TextChars)
            return Refuse(ESCSWalkBudgetStop::Text);
        TextChars += Count;
        return true;
    }

    bool IsStopped() const { return Stop != ESCSWalkBudgetStop::None; }
    ESCSWalkBudgetStop GetStop() const { return Stop; }
    int32 GetRootSlots() const { return RootSlots; }
    int32 GetRegistrySlots() const { return RegistrySlots; }
    int32 GetNodes() const { return Nodes; }
    int32 GetChildSlots() const { return ChildSlots; }
    int32 GetGuards() const { return Guards; }
    int64 GetTextChars() const { return TextChars; }

private:
    bool Refuse(ESCSWalkBudgetStop Reason)
    {
        if (!IsStopped()) Stop = Reason;
        return false;
    }

    bool Reserve(int32 Count, int32 Limit, int32& Used, ESCSWalkBudgetStop Reason)
    {
        if (IsStopped()) return false;
        if (Count < 0) return Refuse(ESCSWalkBudgetStop::InvalidCount);
        if (Count > Limit - Used) return Refuse(Reason);
        Used += Count;
        return true;
    }

    ESCSWalkBudgetStop Stop = ESCSWalkBudgetStop::None;
    int32 RootSlots = 0;
    int32 RegistrySlots = 0;
    int32 Nodes = 0;
    int32 ChildSlots = 0;
    int32 Guards = 0;
    int64 TextChars = 0;
};
} // namespace McpBPOwnershipBindingReader
