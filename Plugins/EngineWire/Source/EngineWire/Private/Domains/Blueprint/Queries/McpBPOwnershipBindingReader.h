#pragma once

#include "CoreMinimal.h"

class UEdGraphNode;

// Source-only preparation. No handler, endpoint, loading, graph traversal or asset writes.
namespace McpBPOwnershipBindingReader
{
enum class EPointerRead : uint8 { NotCaptured, Null, Unresolved, Invalid, Resolved };

struct FPointerObservation
{
    EPointerRead State = EPointerRead::NotCaptured;
    FString Path;
};

enum class EGapReason : uint8
{
    Unsupported,
    NotCaptured,
    LimitExceeded
};

struct FReadGap
{
    FString Field;
    EGapReason Reason = EGapReason::NotCaptured;
};

struct FMemberScalars
{
    FString Kind;
    FName Name;
    FString Scope;
    FGuid MemberGuid;
    bool bSelfContext = false;
    TOptional<bool> WasDeprecated;
    FPointerObservation RawParent;
    // Stored parent only; never inferred from self-context or resolved member ownership.
};

struct FNodeRead
{
    bool bAccepted = false;
    bool bComplete = false;
    FString NodePath;
    FString OwnerPath;
    FString PackagePath;
    TOptional<bool> PackageDirtyBefore;
    TOptional<bool> PackageDirtyAfter;
    FGuid NodeGuid;
    TArray<FMemberScalars> Members;
    bool bHasExpression = false;
    FString Expression;
    TArray<FReadGap> Uncaptured;
    FString Error;
};

// Caller must supply an already-loaded, live node on the game thread in an idle editor.
// Refuses PIE/SIE/queued play and an absent, compiling or regenerating Blueprint owner.
// Dirty flags are observations, not a revision stamp or mutation-free certificate.
// This is a partial node read, NOT a complete asset/binding snapshot or admission gate.
FNodeRead ReadNodeScalars(const UEdGraphNode* Node);

struct FBatchRead
{
    bool bAccepted = false;
    bool bComplete = false;
    int32 RequestedNodes = 0;
    int32 ProcessedNodes = 0;
    int64 RetainedTextChars = 0;
    TArray<FNodeRead> Nodes;
    FString Error;
};

// Maximum 16 input entries, including duplicates. No traversal or implicit loading.
// Stops on first rejected node; remaining entries are not read.
// Retained DTO text: at most 73728 TCHAR per node / 262144 per batch.
// These are text-content limits, not allocator or serialized JSON byte limits.
FBatchRead ReadNodeBatch(TConstArrayView<const UEdGraphNode*> Nodes);
}
