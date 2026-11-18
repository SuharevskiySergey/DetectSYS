#pragma once

#include "Domains/Blueprint/Queries/McpBPOwnershipSCSInventory.h"

class UBlueprint;
class USimpleConstructionScript;

namespace McpBPOwnershipBindingReader
{
struct FSCSListsRead
{
    bool bAccepted = false;
    bool bComplete = false;
    FString SCSPath;
    TArray<FSCSListEntry> Roots;
    TArray<FSCSListEntry> Registry;
    TOptional<bool> PackageDirtyBefore;
    TOptional<bool> PackageDirtyAfter;
    FString Error;
};

// Draft: explicit already-loaded SCS must be a stored BP/class SCS pointer with
// exact BP/generated-class outer. No node payload/children/selection/registry fixup.
// Max128 entries PER list, max240000 retained text TCHAR; refusal is not truncation.
FSCSListsRead ReadSCSRawLists(const UBlueprint* Blueprint, const USimpleConstructionScript* SCS);
} // namespace McpBPOwnershipBindingReader
