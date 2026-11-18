#pragma once

#include "Domains/Blueprint/Queries/McpBPOwnershipStructureReader.h"

namespace McpBPOwnershipBindingReader
{
struct FOverrideSourceIndex
{
    int32 Layer = INDEX_NONE;
    int32 Record = INDEX_NONE;
};

struct FOverridePathKeyGroup
{
    FString OwnerPath;
    FGuid Guid;
    TArray<FOverrideSourceIndex> Sources;
    // Snapshot-only nearest candidate; never an engine-certified effective template.
    FOverrideSourceIndex Candidate;
    bool bSameLayerConflict = false;
};

struct FOverridePathReview
{
    bool bReviewed = false;
    bool bEngineIdentityVerified = false;
    bool bComplete = false;
    TArray<FOverridePathKeyGroup> Groups;
    TArray<FOverrideSourceIndex> Uncomparable;
    TArray<FReadGap> Uncaptured;
    FString Error;
};

// Pure DTO review: no UObject access/loading/key resolve or name-based remapping.
// owner PATH+GUID equality is deliberately weaker than live FComponentKey equality.
FOverridePathReview ReviewOverridePathCandidates(const FOverrideChainRead& Chain);
}
