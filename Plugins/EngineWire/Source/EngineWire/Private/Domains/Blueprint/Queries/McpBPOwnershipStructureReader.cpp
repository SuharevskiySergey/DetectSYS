#include "Domains/Blueprint/Queries/McpBPOwnershipStructureReader.h"

#include "Components/ActorComponent.h"
#include "Components/SceneComponent.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "Engine/InheritableComponentHandler.h"
#include "K2Node_Composite.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"

namespace McpBPOwnershipBindingReader
{
namespace
{
// Keep the same exact package allowlist as the scalar reader, without loading assets.
bool AllowedOwner(const UBlueprint* BP)
{
    if (!IsInGameThread() || !GEditor || GEditor->IsPlaySessionInProgress()
        || !IsValid(BP) || BP->bBeingCompiled || BP->bIsRegeneratingOnLoad) return false;
    const FString Package = BP->GetOutermost()->GetName();
    static const TCHAR* const Names[] = {
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/BP_OwnershipTelescope"),
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/BP_OwnershipBodyLeg"),
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/BP_OwnershipRedistribution"),
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/BP_OwnershipHead"),
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/CR_OwnershipHead"),
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/BP_OwnershipBodyFixture"),
        TEXT("/Game/BeholderPrototype/Telescopic/BP_BeholderTelescopic_Test"),
        TEXT("/Game/BeholderPrototype/Body/BP_BeholderBodyLeg")
    };
    for (const TCHAR* Name : Names)
    {
        if (Package.Equals(Name, ESearchCase::CaseSensitive))
            return BP->GetPathName() == Package + TEXT(".") + FPackageName::GetLongPackageAssetName(Package);
    }
    return false;
}

template<typename T>
FPointerObservation Observe(const TObjectPtr<T>& Pointer)
{
    FPointerObservation Result;
    if (!Pointer.IsResolved())
    {
        Result.State = EPointerRead::Unresolved;
        return Result;
    }
    // No Get(), implicit conversion or object path access before IsResolved.
    const T* Object = Pointer.Get();
    if (Object && !IsValid(Object))
    {
        Result.State = EPointerRead::Invalid;
        return Result;
    }
    Result.State = Object ? EPointerRead::Resolved : EPointerRead::Null;
    if (Object) Result.Path = Object->GetPathName();
    return Result;
}

int64 NodeText(const FNodeRead& Read)
{
    int64 Count = int64(Read.NodePath.Len()) + Read.OwnerPath.Len() + Read.PackagePath.Len()
        + Read.Expression.Len() + Read.Error.Len();
    for (const FMemberScalars& Member : Read.Members)
        Count += int64(Member.Kind.Len()) + Member.Scope.Len() + Member.Name.ToString().Len()
            + Member.RawParent.Path.Len();
    for (const FReadGap& Gap : Read.Uncaptured) Count += Gap.Field.Len();
    return Count;
}

FPointerObservation ObserveKeyOwner(const FComponentKey& Key)
{
    const FObjectProperty* Property = FindFProperty<FObjectProperty>(
        FComponentKey::StaticStruct(), TEXT("OwnerClass"));
    if (!Property || Property->ArrayDim != 1 || Property->HasGetter()
        || Property->PropertyClass != UClass::StaticClass())
    {
        return FPointerObservation(); // NotCaptured, not null.
    }
    // Direct storage accessor, NOT GetObjectPropertyValue[_InContainer], which resolves.
    // UE5.6 PropertyObject.cpp:400-403 returns the stored wrapper without .Get().
    const TObjectPtr<UObject> Stored = Property->GetObjectPtrPropertyValue(
        Property->ContainerPtrToValuePtr<void>(static_cast<const void*>(&Key)));
    return Observe(Stored);
}
}

FOverridesRead ReadOwnOverrides(const UBlueprint* Blueprint)
{
    FOverridesRead Result;
    if (!AllowedOwner(Blueprint))
    {
        Result.Error = TEXT("Idle game-thread editor and exact allowlisted Blueprint required");
        return Result;
    }
    const bool Dirty = Blueprint->GetOutermost()->IsDirty();
    Result.OwnerPath = Blueprint->GetPathName();
    Result.Handler = Observe(Blueprint->InheritableComponentHandler);
    Result.Uncaptured.Add({TEXT("effective_parent_chain, cooked_data, revisions"), EGapReason::NotCaptured});
    if (Result.Handler.State == EPointerRead::Unresolved || Result.Handler.State == EPointerRead::Invalid)
    {
        Result.Uncaptured.Add({TEXT("handler"), EGapReason::Unsupported});
        return Result;
    }
    int64 Text = int64(Result.OwnerPath.Len()) + Result.Handler.Path.Len();
    if (Text > 240000)
    {
        Result.OwnerPath.Reset(); Result.Handler = FPointerObservation();
        Result.Error = TEXT("Override identity text exceeds limit");
        Result.Uncaptured.Add({TEXT("override.text_budget"), EGapReason::LimitExceeded});
        return Result;
    }
    if (Result.Handler.State == EPointerRead::Resolved)
    {
        UInheritableComponentHandler* Handler = Blueprint->InheritableComponentHandler.Get();
        if (Handler->GetOutermost() != Blueprint->GetOutermost())
        {
            Result.Uncaptured.Add({TEXT("handler.external_package"), EGapReason::Unsupported});
            return Result;
        }
        // Iterator is mutable in UE5.6; records are bound const and never changed.
        for (auto It = Handler->CreateRecordIterator(); It; ++It)
        {
            if (Result.Records.Num() == 64)
            {
                Result.Uncaptured.Add({TEXT("override.records"), EGapReason::LimitExceeded});
                return Result;
            }
            const FComponentOverrideRecord& Record = *It;
            FOverrideRead Read;
            Read.VariableName = Record.ComponentKey.GetSCSVariableName();
            Read.AssociatedGuid = Record.ComponentKey.GetAssociatedGuid();
            Read.KeyOwner = ObserveKeyOwner(Record.ComponentKey);
            Read.ComponentClass = Observe(Record.ComponentClass);
            Read.ComponentTemplate = Observe(Record.ComponentTemplate);
            if (Read.ComponentTemplate.State == EPointerRead::Resolved)
            {
                // Observe has already checked resolved state and live object validity.
                const UActorComponent* Template = Record.ComponentTemplate.Get();
                if (Template->GetOutermost() == Blueprint->GetOutermost() && Template->IsTemplate())
                {
                    if (const USceneComponent* Scene = Cast<USceneComponent>(Template))
                    {
                        // Literal flags only: no virtual visibility evaluation or setters.
                        Read.TemplateVisible = Scene->GetVisibleFlag();
                        Read.TemplateHiddenInGame = !!Scene->bHiddenInGame;
                    }
                }
                if (!Read.TemplateVisible.IsSet())
                    Result.Uncaptured.Add({FString::Printf(TEXT("override[%d].scene_flags"), Result.Records.Num()), EGapReason::NotCaptured});
            }
            Text += int64(Read.VariableName.ToString().Len()) + Read.KeyOwner.Path.Len()
                + Read.ComponentClass.Path.Len() + Read.ComponentTemplate.Path.Len();
            if (Text > 240000)
            {
                Result.Uncaptured.Add({TEXT("override.text_budget"), EGapReason::LimitExceeded});
                return Result;
            }
            if (Read.ComponentClass.State == EPointerRead::Unresolved || Read.ComponentTemplate.State == EPointerRead::Unresolved
                || Read.ComponentClass.State == EPointerRead::Invalid || Read.ComponentTemplate.State == EPointerRead::Invalid)
                Result.Uncaptured.Add({FString::Printf(TEXT("override[%d].pointer"), Result.Records.Num()), EGapReason::Unsupported});
            if (Read.KeyOwner.State != EPointerRead::Resolved)
                Result.Uncaptured.Add({FString::Printf(TEXT("override[%d].key_owner"), Result.Records.Num()), EGapReason::Unsupported});
            Result.Records.Add(MoveTemp(Read));
        }
    }
    Result.bAccepted = AllowedOwner(Blueprint) && Dirty == Blueprint->GetOutermost()->IsDirty();
    if (!Result.bAccepted) Result.Error = TEXT("Observed owner/editor/dirty state drift");
    return Result;
}

FOverrideChainRead ReadOverrideChain(const UBlueprint* Blueprint)
{
    FOverrideChainRead Result;
    if (!AllowedOwner(Blueprint))
    {
        Result.Stop = EChainStop::OwnerUnavailable;
        Result.Error = TEXT("Idle game-thread editor and exact allowlisted start Blueprint required");
        return Result;
    }
    Result.Uncaptured.Add({TEXT("effective_key_selection, SCS_fallback, revisions, atomicity"), EGapReason::NotCaptured});
    const FClassProperty* ParentProperty = FindFProperty<FClassProperty>(UBlueprint::StaticClass(), TEXT("ParentClass"));
    if (!ParentProperty || ParentProperty->ArrayDim != 1 || ParentProperty->HasGetter()
        || ParentProperty->PropertyClass != UClass::StaticClass())
    {
        Result.Stop = EChainStop::Unsupported;
        Result.Uncaptured.Add({TEXT("ParentClass.storage_schema"), EGapReason::Unsupported});
        return Result;
    }
    TSet<const UBlueprint*> Seen;
    TArray<const UBlueprint*> Owners;
    const UBlueprint* Current = Blueprint;
    int32 Records = 0;
    int64 Text = 0;
    for (int32 Depth = 0; Depth < 8; ++Depth)
    {
        if (!AllowedOwner(Current))
        {
            Result.Stop = EChainStop::OwnerUnavailable;
            break;
        }
        if (Seen.Contains(Current))
        {
            Result.Stop = EChainStop::Cycle;
            break;
        }
        Seen.Add(Current);
        FOverrideLayerRead Layer;
        Layer.Depth = Depth;
        Layer.bPackageDirtyBefore = Current->GetOutermost()->IsDirty();
        Layer.Own = ReadOwnOverrides(Current);
        TObjectPtr<UObject> StoredParent;
        if (Layer.Own.bAccepted)
        {
            StoredParent = ParentProperty->GetObjectPtrPropertyValue(
                ParentProperty->ContainerPtrToValuePtr<void>(static_cast<const void*>(Current)));
            Layer.ParentClass = Observe(StoredParent);
        }
        const UBlueprint* Next = nullptr;
        EChainStop PendingStop = EChainStop::NotStarted;
        if (!Layer.Own.bAccepted) PendingStop = EChainStop::OwnReadRefused;
        else if (Layer.ParentClass.State == EPointerRead::Unresolved) PendingStop = EChainStop::Unresolved;
        else if (Layer.ParentClass.State == EPointerRead::Null) PendingStop = EChainStop::NullParent;
        else if (Layer.ParentClass.State != EPointerRead::Resolved) PendingStop = EChainStop::Invalid;
        else
        {
            // Observe admitted only resolved, valid objects. No TSubclassOf::Get().
            const UClass* Parent = Cast<UClass>(StoredParent.Get());
            if (!Parent) PendingStop = EChainStop::Unsupported;
            else
            {
                Layer.ClassGeneratedBy = Observe(Parent->ClassGeneratedBy);
                if (Layer.ClassGeneratedBy.State == EPointerRead::Unresolved) PendingStop = EChainStop::Unresolved;
                else if (Layer.ClassGeneratedBy.State == EPointerRead::Null)
                    PendingStop = Parent->HasAnyClassFlags(CLASS_Native) ? EChainStop::NativeTerminal : EChainStop::Unsupported;
                else if (Layer.ClassGeneratedBy.State != EPointerRead::Resolved) PendingStop = EChainStop::Invalid;
                else
                {
                    Next = Cast<UBlueprint>(Parent->ClassGeneratedBy.Get());
                    if (!Next) PendingStop = EChainStop::Unsupported;
                    else if (Seen.Contains(Next)) PendingStop = EChainStop::Cycle;
                }
            }
        }

        int64 LayerText = int64(Layer.Own.OwnerPath.Len()) + Layer.Own.Handler.Path.Len()
            + Layer.Own.Error.Len() + Layer.ParentClass.Path.Len() + Layer.ClassGeneratedBy.Path.Len();
        for (const FReadGap& Gap : Layer.Own.Uncaptured) LayerText += Gap.Field.Len();
        for (const FOverrideRead& Record : Layer.Own.Records)
            LayerText += int64(Record.VariableName.ToString().Len()) + Record.KeyOwner.Path.Len()
                + Record.ComponentClass.Path.Len() + Record.ComponentTemplate.Path.Len();
        if (Records + Layer.Own.Records.Num() > 128 || Text + LayerText > 240000)
        {
            Result.Stop = EChainStop::Limit;
            Result.Uncaptured.Add({TEXT("chain.record_or_text_budget"), EGapReason::LimitExceeded});
            break; // Do not retain the oversized layer or silently truncate records.
        }
        Records += Layer.Own.Records.Num();
        Text += LayerText;
        Result.Layers.Add(MoveTemp(Layer));
        Owners.Add(Current);
        if (PendingStop != EChainStop::NotStarted)
        {
            Result.Stop = PendingStop;
            break;
        }
        Current = Next;
    }
    if (Result.Stop == EChainStop::NotStarted)
    {
        Result.Stop = EChainStop::Limit;
        Result.Uncaptured.Add({TEXT("chain.depth"), EGapReason::LimitExceeded});
    }
    // Recheck every retained layer, not just the last ancestor.
    for (int32 Index = 0; Index < Owners.Num(); ++Index)
    {
        const UBlueprint* Owner = Owners[Index];
        if (!AllowedOwner(Owner)) { Result.Stop = EChainStop::StateDrift; continue; }
        const bool DirtyAfter = Owner->GetOutermost()->IsDirty();
        Result.Layers[Index].PackageDirtyAfter = DirtyAfter;
        if (DirtyAfter != Result.Layers[Index].bPackageDirtyBefore) Result.Stop = EChainStop::StateDrift;
    }
    Result.bAccepted = Result.Stop == EChainStop::NativeTerminal;
    if (!Result.bAccepted) Result.Uncaptured.Add({TEXT("chain.termination"), EGapReason::NotCaptured});
    // bComplete remains false: no effective-key selection/SCS fallback/revisions.
    return Result;
}

FGraphTreeRead ReadGraphTree(const UEdGraph* Root)
{
    FGraphTreeRead Result;
    if (!IsInGameThread() || !IsValid(Root))
    {
        Result.Error = TEXT("Live graph on game thread required");
        return Result;
    }
    const UBlueprint* Owner = Root->GetTypedOuter<UBlueprint>();
    if (!AllowedOwner(Owner))
    {
        Result.Error = TEXT("Idle editor and exact allowlisted graph owner required");
        return Result;
    }
    const bool Dirty = Owner->GetOutermost()->IsDirty();
    struct FPending { const UEdGraph* Graph; int32 Depth; };
    TArray<FPending> Queue;
    TSet<const UEdGraph*> Seen;
    Queue.Add({Root, 0});
    Seen.Add(Root);
    int64 Text = 0;
    Result.Uncaptured.Add({TEXT("asset_roots, inherited_graphs, pins, rig_VM, revisions"), EGapReason::NotCaptured});

    auto Edge = [&](const FString& From, const TCHAR* Relation, int32 Index,
        const TObjectPtr<UEdGraph>& Target, int32 Depth) -> bool
    {
        if (Result.Edges.Num() >= 256) return false;
        FGraphEdgeRead Read;
        Read.SourcePath = From; Read.Relation = Relation; Read.Index = Index;
        Read.Target = Observe(Target);
        Text += int64(From.Len()) + Read.Relation.Len() + Read.Target.Path.Len();
        if (Text > 240000) return false;
        Result.Edges.Add(MoveTemp(Read));
        if (!Target.IsResolved())
        {
            Result.Uncaptured.Add({TEXT("graph.edge.unresolved"), EGapReason::Unsupported});
            return true;
        }
        const UEdGraph* Child = Target.Get();
        if (!Child) return true;
        if (!IsValid(Child))
        {
            Result.Uncaptured.Add({TEXT("graph.edge.invalid"), EGapReason::Unsupported});
            return true;
        }
        if (Child->GetTypedOuter<UBlueprint>() != Owner)
        {
            Result.Uncaptured.Add({TEXT("graph.edge.external_owner"), EGapReason::Unsupported});
            return true;
        }
        if (Seen.Contains(Child)) return true;
        if (Depth > 8 || Queue.Num() >= 16) return false;
        Seen.Add(Child); Queue.Add({Child, Depth});
        return true;
    };

    for (int32 Q = 0; Q < Queue.Num(); ++Q)
    {
        // Copy before enqueueing children, which may reallocate Queue.
        const FPending Current = Queue[Q];
        const UEdGraph* Graph = Current.Graph;
        const FString GraphPath = Graph->GetPathName();
        Text += GraphPath.Len();
        if (Text > 240000) goto Limit;
        Result.GraphPaths.Add(GraphPath);
        for (int32 I = 0; I < Graph->Nodes.Num(); ++I)
        {
            if (Result.Uncaptured.Num() >= 128) goto Limit;
            if (Result.Nodes.Num() >= 128) goto Limit;
            const auto& Pointer = Graph->Nodes[I];
            if (!Pointer.IsResolved())
            {
                Result.Uncaptured.Add({FString::Printf(TEXT("graph[%d].node[%d].unresolved"), Q, I), EGapReason::Unsupported});
                // The global gap cap bounds unresolved/null entry loops too.
                continue;
            }
            const UEdGraphNode* Node = Pointer.Get();
            if (!Node)
            {
                Result.Uncaptured.Add({FString::Printf(TEXT("graph[%d].node[%d].null"), Q, I), EGapReason::NotCaptured});
                continue;
            }
            if (!IsValid(Node) || Node->GetTypedOuter<UBlueprint>() != Owner
                || Node->GetOuter() != Graph)
            {
                Result.Error = TEXT("Invalid, external-owner or wrong-graph node; traversal stopped");
                return Result;
            }
            FNodeRead Read = ReadNodeScalars(Node);
            Text += NodeText(Read);
            if (Text > 240000) goto Limit;
            const bool Accepted = Read.bAccepted;
            Result.Nodes.Add(MoveTemp(Read));
            if (!Accepted) { Result.Error = TEXT("Scalar node refused; traversal stopped"); return Result; }
            if (const UK2Node_Composite* Composite = Cast<UK2Node_Composite>(Node))
                if (!Edge(Node->GetPathName(), TEXT("BoundGraph"), I, Composite->BoundGraph, Current.Depth + 1)) goto Limit;
        }
        for (int32 I = 0; I < Graph->SubGraphs.Num(); ++I)
        {
            if (Result.Uncaptured.Num() >= 128) goto Limit;
            if (!Edge(GraphPath, TEXT("SubGraphs"), I, Graph->SubGraphs[I], Current.Depth + 1)) goto Limit;
        }
    }
    Result.bAccepted = AllowedOwner(Owner) && Dirty == Owner->GetOutermost()->IsDirty();
    if (!Result.bAccepted) Result.Error = TEXT("Observed owner/editor/dirty state drift");
    return Result;

Limit:
    Result.Uncaptured.Add({TEXT("graph.traversal_budget"), EGapReason::LimitExceeded});
    return Result;
}
}
