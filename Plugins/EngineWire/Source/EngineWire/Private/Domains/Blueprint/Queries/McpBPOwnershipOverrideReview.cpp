#include "Domains/Blueprint/Queries/McpBPOwnershipOverrideReview.h"

namespace McpBPOwnershipBindingReader
{
FOverridePathReview ReviewOverridePathCandidates(const FOverrideChainRead& Chain)
{
    FOverridePathReview Result;
    Result.Uncaptured.Add({TEXT("live_key_identity, SCS_fallback, effective_templates, recovery"), EGapReason::NotCaptured});
    if (!Chain.bAccepted || Chain.Stop != EChainStop::NativeTerminal
        || Chain.Layers.IsEmpty() || Chain.Layers.Num() > 8)
    {
        Result.Error = TEXT("Admitted native-terminal chain with 1..8 layers required");
        return Result;
    }
    int32 Records = 0;
    int64 OwnerChars = 0;
    // Validate bounds before allocating groups or producing partial candidates.
    for (int32 L = 0; L < Chain.Layers.Num(); ++L)
    {
        const FOverrideLayerRead& Layer = Chain.Layers[L];
        if (Layer.Depth != L || !Layer.Own.bAccepted)
        {
            Result.Error = TEXT("Layer order or own-read admission is inconsistent");
            return Result;
        }
        if (Layer.Own.Records.Num() > 128 - Records)
        {
            Result.Error = TEXT("Review exceeds 128 records");
            return Result;
        }
        Records += Layer.Own.Records.Num();
        for (const FOverrideRead& Record : Layer.Own.Records)
        {
            OwnerChars += Record.KeyOwner.Path.Len();
            if (OwnerChars > 240000)
            {
                Result.Error = TEXT("Review exceeds owner-path text budget");
                return Result;
            }
        }
    }
    for (int32 L = 0; L < Chain.Layers.Num(); ++L)
    {
        const TArray<FOverrideRead>& LayerRecords = Chain.Layers[L].Own.Records;
        for (int32 R = 0; R < LayerRecords.Num(); ++R)
        {
            const FOverrideRead& Record = LayerRecords[R];
            if (Record.KeyOwner.State != EPointerRead::Resolved || Record.KeyOwner.Path.IsEmpty()
                || !Record.AssociatedGuid.IsValid())
            {
                Result.Uncomparable.Add({L, R});
                continue;
            }
            int32 GroupIndex = INDEX_NONE;
            for (int32 G = 0; G < Result.Groups.Num(); ++G)
            {
                if (Result.Groups[G].OwnerPath == Record.KeyOwner.Path
                    && Result.Groups[G].Guid == Record.AssociatedGuid)
                {
                    GroupIndex = G;
                    break;
                }
            }
            if (GroupIndex == INDEX_NONE)
            {
                FOverridePathKeyGroup Group;
                Group.OwnerPath = Record.KeyOwner.Path;
                Group.Guid = Record.AssociatedGuid;
                Group.Candidate = {L, R};
                GroupIndex = Result.Groups.Add(MoveTemp(Group));
            }
            FOverridePathKeyGroup& Group = Result.Groups[GroupIndex];
            for (const FOverrideSourceIndex& Source : Group.Sources)
            {
                if (Source.Layer == L)
                {
                    // No last-write-wins, even for ambiguous deeper ancestor records.
                    Group.bSameLayerConflict = true;
                    Group.Candidate = FOverrideSourceIndex();
                    break;
                }
            }
            Group.Sources.Add({L, R});
        }
    }
    if (!Result.Uncomparable.IsEmpty())
    {
        // An unknown key could alias any group; retain provenance, but no recommendation.
        for (FOverridePathKeyGroup& Group : Result.Groups) Group.Candidate = FOverrideSourceIndex();
        Result.Uncaptured.Add({TEXT("uncomparable_keys_block_candidates"), EGapReason::Unsupported});
    }
    Result.bReviewed = true;
    // Never sets bComplete or bEngineIdentityVerified, even for conflict-free input.
    return Result;
}
}
