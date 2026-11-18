#pragma once

#include "Domains/Blueprint/Queries/McpBPOwnershipSCSInventory.h"

class UBlueprint;
class USimpleConstructionScript;
class USCS_Node;

namespace McpBPOwnershipBindingReader
{
struct FSCSChildrenRead
{
    bool bAccepted = false;
    bool bComplete = false;
    FString SourceNodePath;
    TArray<FSCSListEntry> Children;
    TOptional<bool> PackageDirtyBefore;
    TOptional<bool> PackageDirtyAfter;
    FString Error;
};

// Draft single-parent raw edges. Parent must pass ReadSCSNodePayload membership;
// child-only targets may be observed but are NOT recursively admitted/read.
// Max256 entries /32768 retained text TCHAR, not peak memory/JSON byte guarantee.
FSCSChildrenRead ReadSCSChildPointers(const UBlueprint* Blueprint, const USimpleConstructionScript* SCS, const USCS_Node* Node);
} // namespace McpBPOwnershipBindingReader
