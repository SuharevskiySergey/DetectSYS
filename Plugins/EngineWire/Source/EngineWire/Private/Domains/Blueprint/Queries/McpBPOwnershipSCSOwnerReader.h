#pragma once

#include "Domains/Blueprint/Queries/McpBPOwnershipBindingReader.h"

class UBlueprint;

namespace McpBPOwnershipBindingReader
{
struct FSCSOwnerRead
{
    bool bAccepted = false;
    bool bComplete = false;
    FString BlueprintPath;
    FPointerObservation GeneratedClass;
    FPointerObservation BlueprintSCS;
    FPointerObservation BlueprintHandler;
    FPointerObservation ClassSCS;
    FPointerObservation ClassHandler;
    FPointerObservation ClassGeneratedBy;
    // Set only after both inputs are resolved or null. Path equality is not used.
    TOptional<bool> SameSCS;
    TOptional<bool> SameHandler;
    TOptional<bool> ClassGeneratedByIsBlueprint;
    TOptional<bool> PackageDirtyBefore;
    TOptional<bool> PackageDirtyAfter;
    FString Error;
};

// Source-only draft. Already-loaded exact-allowlisted BP on idle editor game thread.
// Raw owner fields only, max32768 retained text TCHARs; no superclass/node reads,
// loading, CDO, handler creation, repair or engine-effective template evaluation.
FSCSOwnerRead ReadSCSOwnerPointers(const UBlueprint* Blueprint);
} // namespace McpBPOwnershipBindingReader
