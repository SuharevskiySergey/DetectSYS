#pragma once

#include "Domains/Blueprint/Queries/McpBPOwnershipSCSInventory.h"

class UBlueprint;
class USimpleConstructionScript;
class USCS_Node;

namespace McpBPOwnershipBindingReader
{
struct FSCSNodeRead
{
    bool bAccepted = false;
    bool bComplete = false;
    FSCSNodeInventory Node;
    TOptional<bool> PackageDirtyBefore;
    TOptional<bool> PackageDirtyAfter;
    TArray<FReadGap> Uncaptured;
    FString Error;
};

// Draft: one already-loaded node present by native identity in admitted raw roots
// or registry, with exact SCS outer. No child-only discovery, binding resolution,
// template payload/visibility evaluation, loading/CDO/compiler or mutation.
// Max32768 retained text TCHAR; not peak allocation or serialized byte bound.
FSCSNodeRead ReadSCSNodePayload(const UBlueprint* Blueprint, const USimpleConstructionScript* SCS, const USCS_Node* Node);
} // namespace McpBPOwnershipBindingReader
