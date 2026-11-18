#pragma once

#include "Domains/Blueprint/Queries/McpBPOwnershipBindingReader.h"

namespace McpBPOwnershipBindingReader
{
// Draft DTO contract only. No reader, endpoint, serialization or selection API.
// These proposed per-inventory bounds are NOT runtime-verified guarantees.
struct FSCSInventoryBudget
{
    static constexpr int32 MaxRootEntries = 128;
    static constexpr int32 MaxRegistryEntries = 128;
    static constexpr int32 MaxNodes = 128;
    static constexpr int32 MaxChildEdges = 256;
    static constexpr int32 MaxDepth = 8;
    static constexpr int64 MaxRetainedTextChars = 240000;
};

enum class ESCSInventoryStop : uint8
{
    NotStarted, CapturedRaw, NullSCS, OwnerUnavailable, UnsupportedSchema,
    Unresolved, Invalid, WrongOuter, Limit, StateDrift
};

enum class ESCSOuterForm : uint8
{
    NotCaptured, GeneratedClass, LegacyBlueprint, Unsupported
};

// Root/registry entries remain ordered and separate, including duplicate/null
// targets. No synthetic union or getter-populated registry is substituted.
struct FSCSListEntry
{
    int32 Index = INDEX_NONE;
    FPointerObservation Target;
};

struct FSCSChildEdge
{
    int32 SourceNode = INDEX_NONE;
    int32 ChildIndex = INDEX_NONE;
    FPointerObservation Target;
};

struct FSCSNodeInventory
{
    FString NodePath;
    FPointerObservation Outer;
    int32 DiscoveryDepth = INDEX_NONE;
    FGuid VariableGuid;
    FName VariableName;
    FPointerObservation ComponentClass;
    FPointerObservation ComponentTemplate;
    TOptional<bool> TemplateVisible;
    TOptional<bool> TemplateHiddenInGame;
    FName AttachToName;
    FName ParentComponentOrVariableName;
    FName ParentComponentOwnerClassName;
    TOptional<bool> IsParentComponentNative;
    // Membership comes from raw list entries/edges, never inferred from names.
};

struct FSCSInventory
{
    bool bAccepted = false;
    bool bComplete = false;
    bool bEngineIdentityVerified = false;
    ESCSInventoryStop Stop = ESCSInventoryStop::NotStarted;
    FString BlueprintPath;
    FPointerObservation BlueprintGeneratedClass;
    FPointerObservation BlueprintSCS;
    FPointerObservation SCSOuter;
    ESCSOuterForm OuterForm = ESCSOuterForm::NotCaptured;
    // Generated-class storage is separate evidence, not a BP-field alias.
    FPointerObservation GeneratedClassSCS;
    FPointerObservation GeneratedClassHandler;
    FPointerObservation GeneratedClassSuper;
    TOptional<bool> PackageDirtyBefore;
    TOptional<bool> PackageDirtyAfter;
    TArray<FSCSListEntry> Roots;
    TArray<FSCSListEntry> Registry;
    TArray<FSCSNodeInventory> Nodes;
    TArray<FSCSChildEdge> ChildEdges;
    TArray<FReadGap> Uncaptured;
    FString Error;
    // CapturedRaw would mean only bounded raw inventory completed, not effective
    // inheritance, hierarchy agreement, live key identity or restoration coverage.
};
} // namespace McpBPOwnershipBindingReader
