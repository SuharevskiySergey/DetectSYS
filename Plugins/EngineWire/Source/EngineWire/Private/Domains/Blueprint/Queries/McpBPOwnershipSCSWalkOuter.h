#pragma once

#include "CoreTypes.h"

class UObject;

namespace McpBPOwnershipBindingReader
{
class FSCSWalkGuards;

enum class ESCSWalkOuterStop : uint8
{
    NotStarted, Observed, UnsupportedConfiguration, NullInput, GuardRefusal
};

struct FSCSWalkOuterRead
{
    bool bAccepted = false;
    ESCSWalkOuterStop Stop = ESCSWalkOuterStop::NotStarted;
    // Invocation-local only. nullptr is observed-null ONLY when accepted.
    // Caller must retain Guards until all uses finish; never serialize pointer.
    const UObject* Outer = nullptr;
};

// Source-only fail-closed gate. Does not alter engine build configuration.
bool IsSCSWalkOuterStorageSupported();

// Only compiled no-late/no-remote branch can read GetOuter. Unsupported builds
// refuse BEFORE dereferencing Object/acquiring refs, without a getter fallback.
// Requires already-live borrowed input and guards' synchronous lifetime contract.
// Not a chain walker, path formatter, owner admission or drift baseline.
FSCSWalkOuterRead ReadSCSWalkOuter(const UObject* Object, FSCSWalkGuards& Guards);
} // namespace McpBPOwnershipBindingReader
