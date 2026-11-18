#include "Domains/Blueprint/Queries/McpBPOwnershipSCSChildrenReader.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSNodeReader.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSSchema.h"

#include "Engine/Blueprint.h"
#include "Engine/SCS_Node.h"
#include "Engine/SimpleConstructionScript.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"

namespace McpBPOwnershipBindingReader
{
FSCSChildrenRead ReadSCSChildPointers(const UBlueprint* Blueprint, const USimpleConstructionScript* SCS, const USCS_Node* Node)
{
    FSCSChildrenRead Result;
    const FSCSNodeRead Parent = ReadSCSNodePayload(Blueprint, SCS, Node);
    if (!Parent.bAccepted) { Result.Error = Parent.Error; return Result; }
    const FSCSListSchema Schema = InspectSCSListSchema();
    if (!Schema.IsSupported()) { Result.Error = Schema.Error; return Result; }
    Result.PackageDirtyBefore = Blueprint->GetOutermost()->IsDirty();
    Result.SourceNodePath = Node->GetPathName();
    FScriptArrayHelper Array(Schema.Children, Schema.Children->ContainerPtrToValuePtr<void>(static_cast<const void*>(Node)));
    if (Array.Num() > FSCSInventoryBudget::MaxChildEdges)
    {
        Result.Error = TEXT("SCS child entry limit exceeded before copying");
        // Source path can itself be oversized, even when no entries were copied.
        if (Result.SourceNodePath.Len() > 32768 - 512) Result.SourceNodePath.Reset();
        return Result;
    }
    const int32 CountBefore = Array.Num();
    int64 Text = Result.SourceNodePath.Len();
    const auto RefuseText = [&]()
    {
        Result.SourceNodePath.Reset();
        Result.Children.Reset();
        Result.Error = TEXT("SCS children retained text exceeds32768 TCHAR budget");
    };
    if (Text > 32768 - 512) { RefuseText(); return Result; }
    const FObjectProperty* Inner = CastFieldChecked<FObjectProperty>(Schema.Children->Inner);
    for (int32 Index = 0; Index < CountBefore; ++Index)
    {
        FSCSListEntry Edge;
        Edge.Index = Index;
        const TObjectPtr<UObject> Stored = Inner->GetObjectPtrPropertyValue(Array.GetRawPtr(Index));
        bool Safe = Stored.IsResolved();
        if (!Safe) Edge.Target.State = EPointerRead::Unresolved;
        else
        {
            const UObject* Target = Stored.Get();
            if (Target && !IsValid(Target)) { Edge.Target.State = EPointerRead::Invalid; Safe = false; }
            else
            {
                Edge.Target.State = Target ? EPointerRead::Resolved : EPointerRead::Null;
                if (Target)
                {
                    Edge.Target.Path = Target->GetPathName();
                    Safe = Target->IsA<USCS_Node>() && Target->GetOuter() == SCS;
                }
            }
        }
        Text += Edge.Target.Path.Len();
        if (Text > 32768 - 512) { RefuseText(); return Result; }
        Result.Children.Add(MoveTemp(Edge));
        if (!Safe)
        {
            Result.Error = TEXT("Unresolved, invalid or wrong-outer SCS child target");
            return Result; // Prefix+offending observation retained as refused evidence.
        }
    }
    const FSCSNodeRead After = ReadSCSNodePayload(Blueprint, SCS, Node);
    if (!After.bAccepted)
    {
        Result.Error = TEXT("SCS children parent admission changed");
        return Result;
    }
    Result.PackageDirtyAfter = Blueprint->GetOutermost()->IsDirty();
    if (Result.PackageDirtyAfter.GetValue() != Result.PackageDirtyBefore.GetValue()
        || Array.Num() != CountBefore)
    {
        Result.Error = TEXT("SCS children parent/list/dirty state drift");
        return Result;
    }
    Result.bAccepted = true;
    return Result; // Self/cycle edges are observations, not traversal or repair.
}
} // namespace McpBPOwnershipBindingReader
