#pragma once

#include "CoreMinimal.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipBindingReader.h"

class UBlueprint;
class UEdGraph;

namespace McpBPOwnershipBindingReader
{
struct FOverrideRead
{
    FName VariableName;
    FGuid AssociatedGuid;
    FPointerObservation KeyOwner;
    FPointerObservation ComponentClass;
    FPointerObservation ComponentTemplate;
    TOptional<bool> TemplateVisible;
    TOptional<bool> TemplateHiddenInGame;
    // Only filled for a resolved scene template in the inspected Blueprint package.
    // Key.OwnerClass is read through typed direct storage; resolving accessor is not called.
};

struct FOverridesRead
{
    bool bAccepted = false;
    bool bComplete = false;
    FString OwnerPath;
    FPointerObservation Handler;
    TArray<FOverrideRead> Records;
    TArray<FReadGap> Uncaptured;
    FString Error;
};

struct FGraphEdgeRead
{
    FString SourcePath;
    FString Relation;
    int32 Index = 0;
    FPointerObservation Target;
};

struct FGraphTreeRead
{
    bool bAccepted = false;
    bool bComplete = false;
    TArray<FString> GraphPaths;
    TArray<FGraphEdgeRead> Edges;
    TArray<FNodeRead> Nodes;
    TArray<FReadGap> Uncaptured;
    FString Error;
};

// Already-loaded caller-owned objects only; no endpoint, loading or parent traversal.
// Own records only (max64). Does not calculate effective inherited overrides.
FOverridesRead ReadOwnOverrides(const UBlueprint* Blueprint);
// K2/UEdGraph subtree only: max16 graphs,128 nodes,256 edges,depth8.
// Not rig-VM coverage, not an atomic or complete asset snapshot.
FGraphTreeRead ReadGraphTree(const UEdGraph* Root);

enum class EChainStop : uint8
{
    NotStarted, NativeTerminal, NullParent, Unresolved, Invalid,
    OwnerUnavailable, Cycle, Limit, Unsupported, OwnReadRefused, StateDrift
};

struct FOverrideLayerRead
{
    int32 Depth = 0;
    FOverridesRead Own;
    FPointerObservation ParentClass;
    FPointerObservation ClassGeneratedBy;
    bool bPackageDirtyBefore = false;
    TOptional<bool> PackageDirtyAfter;
};

struct FOverrideChainRead
{
    bool bAccepted = false;
    bool bComplete = false;
    EChainStop Stop = EChainStop::NotStarted;
    TArray<FOverrideLayerRead> Layers;
    TArray<FReadGap> Uncaptured;
    FString Error;
};

// Already-loaded exact-allowlisted ancestors only; no CDO, loading or key matching.
// Max8 layers /128 retained records /240000 retained text TCHARs (not JSON bytes).
// NativeTerminal is traversal status, not complete effective-template capture.
FOverrideChainRead ReadOverrideChain(const UBlueprint* Blueprint);
}
