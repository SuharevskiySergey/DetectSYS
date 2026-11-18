#include "Domains/Blueprint/Queries/McpBPOwnershipBindingReader.h"

#include "EdGraph/EdGraphNode.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "Engine/MemberReference.h"
#include "K2Node_CallFunction.h"
#include "K2Node_MathExpression.h"
#include "K2Node_Variable.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"

namespace McpBPOwnershipBindingReader
{
namespace
{
bool IsAllowedPackage(const FString& Path)
{
    // Exact package identities, not a prefix permitting arbitrary dependencies.
    static const TCHAR* const Allowed[] = {
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/BP_OwnershipTelescope"),
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/BP_OwnershipBodyLeg"),
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/BP_OwnershipRedistribution"),
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/BP_OwnershipHead"),
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/CR_OwnershipHead"),
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/BP_OwnershipBodyFixture"),
        TEXT("/Game/BeholderPrototype/Telescopic/BP_BeholderTelescopic_Test"),
        TEXT("/Game/BeholderPrototype/Body/BP_BeholderBodyLeg")
    };
    for (const TCHAR* Candidate : Allowed)
    {
        if (Path.Equals(Candidate, ESearchCase::CaseSensitive))
        {
            return true;
        }
    }
    return false;
}

FMemberScalars ReadMember(const FMemberReference& Reference, const TCHAR* Kind)
{
    FMemberScalars Result;
    Result.Kind = Kind;
    Result.Name = Reference.GetMemberName();
    Result.Scope = Reference.GetMemberScopeName();
    Result.MemberGuid = Reference.GetMemberGuid();
    Result.bSelfContext = Reference.IsSelfContext();
    const FObjectProperty* Parent = FindFProperty<FObjectProperty>(
        FMemberReference::StaticStruct(), TEXT("MemberParent"));
    if (Parent && Parent->ArrayDim == 1 && !Parent->HasGetter()
        && Parent->PropertyClass == UObject::StaticClass())
    {
        // Read the stored wrapper, not the resolving UObject* getter.
        const TObjectPtr<UObject> Stored = Parent->GetObjectPtrPropertyValue(
            Parent->ContainerPtrToValuePtr<void>(static_cast<const void*>(&Reference)));
        if (!Stored.IsResolved())
        {
            Result.RawParent.State = EPointerRead::Unresolved;
        }
        else
        {
            const UObject* Object = Stored.Get();
            if (!Object) Result.RawParent.State = EPointerRead::Null;
            else if (!IsValid(Object)) Result.RawParent.State = EPointerRead::Invalid;
            else
            {
                Result.RawParent.State = EPointerRead::Resolved;
                Result.RawParent.Path = Object->GetPathName();
            }
        }
    }
    // Typed direct storage read, not GetValue_InContainer/metadata getter.
    // An absent or changed field stays unset, never silently becomes false.
    const FBoolProperty* Deprecated = FindFProperty<FBoolProperty>(
        FMemberReference::StaticStruct(), TEXT("bWasDeprecated"));
    if (Deprecated && Deprecated->ArrayDim == 1 && !Deprecated->HasGetter())
    {
        Result.WasDeprecated = Deprecated->GetPropertyValue(
            Deprecated->ContainerPtrToValuePtr<void>(static_cast<const void*>(&Reference)));
    }
    return Result;
}

bool IsEditorReadAllowed()
{
    // Includes a queued play request, not only an already-created PlayWorld.
    return GEditor && !GEditor->IsPlaySessionInProgress();
}

int64 CountTextChars(const FNodeRead& Read)
{
    int64 Count = static_cast<int64>(Read.NodePath.Len()) + Read.OwnerPath.Len()
        + Read.PackagePath.Len() + Read.Expression.Len() + Read.Error.Len();
    for (const FMemberScalars& Member : Read.Members)
    {
        Count += static_cast<int64>(Member.Kind.Len()) + Member.Scope.Len()
            + Member.Name.ToString().Len() + Member.RawParent.Path.Len();
    }
    for (const FReadGap& Gap : Read.Uncaptured)
    {
        Count += Gap.Field.Len();
    }
    return Count;
}

FNodeRead TextLimitFailure(const TCHAR* Message)
{
    // Drop the oversized payload; do not expose a silently truncated binding.
    FNodeRead Result;
    Result.Error = Message;
    Result.Uncaptured.Add({TEXT("dto.text_budget"), EGapReason::LimitExceeded});
    return Result;
}
}

FNodeRead ReadNodeScalars(const UEdGraphNode* Node)
{
    FNodeRead Result;
    if (!IsInGameThread())
    {
        Result.Error = TEXT("Game-thread read required");
        return Result;
    }
    if (!IsEditorReadAllowed())
    {
        Result.Error = TEXT("Idle editor required; PIE/SIE and queued play requests are refused");
        return Result;
    }
    if (!IsValid(Node))
    {
        Result.Error = TEXT("A live, already-loaded node is required");
        return Result;
    }

    const UBlueprint* Owner = Node->GetTypedOuter<UBlueprint>();
    if (!IsValid(Owner) || Owner->bBeingCompiled || Owner->bIsRegeneratingOnLoad)
    {
        Result.Error = TEXT("Stable owning Blueprint required; compiling/regenerating owners are refused");
        return Result;
    }
    const UPackage* Package = Node->GetOutermost();
    if (!Package || !IsAllowedPackage(Package->GetName()))
    {
        Result.Error = TEXT("Node package is outside the exact allowlist");
        return Result;
    }

    const FString PackagePath = Package->GetName();
    const FString ExpectedOwnerPath = PackagePath + TEXT(".")
        + FPackageName::GetLongPackageAssetName(PackagePath);
    if (Owner->GetPathName() != ExpectedOwnerPath)
    {
        Result.Error = TEXT("Owning Blueprint is not the exact allowlisted asset object");
        return Result;
    }

    Result.bAccepted = true;
    Result.OwnerPath = ExpectedOwnerPath;
    Result.PackagePath = PackagePath;
    Result.PackageDirtyBefore = Package->IsDirty();
    Result.NodePath = Node->GetPathName();
    Result.NodeGuid = Node->NodeGuid;
    if (const UK2Node_Variable* Variable = Cast<UK2Node_Variable>(Node))
    {
        Result.Members.Add(ReadMember(Variable->VariableReference, TEXT("variable")));
    }
    if (const UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node))
    {
        Result.Members.Add(ReadMember(Call->FunctionReference, TEXT("function")));
    }
    if (!Result.Members.IsEmpty())
    {
        for (const FMemberScalars& Member : Result.Members)
        {
            if (Member.RawParent.State != EPointerRead::Resolved && Member.RawParent.State != EPointerRead::Null)
            {
                Result.Uncaptured.Add({Member.Kind + TEXT(".raw_parent"), EGapReason::Unsupported});
            }
            if (!Member.WasDeprecated.IsSet())
            {
                Result.Uncaptured.Add({Member.Kind + TEXT(".was_deprecated"), EGapReason::Unsupported});
            }
        }
    }
    if (const UK2Node_MathExpression* Math = Cast<UK2Node_MathExpression>(Node))
    {
        Result.bHasExpression = true;
        // Do not truncate silently or expose an unbounded expression in the DTO.
        if (Math->Expression.Len() <= 65536)
        {
            Result.Expression = Math->Expression;
        }
        else
        {
            Result.bHasExpression = false;
            Result.Uncaptured.Add({TEXT("expression"), EGapReason::LimitExceeded});
        }
        Result.Uncaptured.Add({TEXT("math.bound_graph"), EGapReason::Unsupported});
    }
    // Empty Members must never be mistaken for proof that an arbitrary node has no bindings.
    Result.Uncaptured.Add({TEXT("other_node_references"), EGapReason::NotCaptured});
    Result.Uncaptured.Add({TEXT("graph_traversal"), EGapReason::NotCaptured});
    Result.Uncaptured.Add({TEXT("pins"), EGapReason::NotCaptured});
    Result.Uncaptured.Add({TEXT("overrides"), EGapReason::NotCaptured});
    Result.Uncaptured.Add({TEXT("rig"), EGapReason::NotCaptured});
    Result.Uncaptured.Add({TEXT("revisions"), EGapReason::NotCaptured});
    Result.PackageDirtyAfter = Package->IsDirty();
    if (Result.PackageDirtyBefore.GetValue() != Result.PackageDirtyAfter.GetValue()
        || Owner->bBeingCompiled || Owner->bIsRegeneratingOnLoad || !IsEditorReadAllowed())
    {
        // Keep the partial observations, but refuse to admit this read as stable.
        Result.bAccepted = false;
        Result.Error = TEXT("Observed editor/owner/dirty state changed during scalar read");
    }
    // Intentionally remains false even for an accepted scalar read.
    if (CountTextChars(Result) > 73728)
    {
        return TextLimitFailure(TEXT("Node DTO exceeds 73728 retained text TCHARs"));
    }
    return Result;
}

FBatchRead ReadNodeBatch(TConstArrayView<const UEdGraphNode*> Nodes)
{
    FBatchRead Result;
    Result.RequestedNodes = Nodes.Num();
    if (!IsInGameThread())
    {
        Result.Error = TEXT("Game-thread read required");
        Result.RetainedTextChars = Result.Error.Len();
        return Result;
    }
    if (!IsEditorReadAllowed())
    {
        Result.Error = TEXT("Idle editor required; PIE/SIE and queued play requests are refused");
        Result.RetainedTextChars = Result.Error.Len();
        return Result;
    }
    // Bound before dereferencing inputs or allocating output node records.
    // At most 16 * 65536 expression TCHARs, excluding paths/scalar metadata.
    if (Nodes.IsEmpty() || Nodes.Num() > 16)
    {
        Result.Error = TEXT("Expected 1..16 already-loaded node entries");
        Result.RetainedTextChars = Result.Error.Len();
        return Result;
    }
    Result.Nodes.Reserve(Nodes.Num());
    for (const UEdGraphNode* Node : Nodes)
    {
        FNodeRead Read = ReadNodeScalars(Node);
        ++Result.ProcessedNodes;
        // Reserve room for the final constant-size rejection and batch error text.
        if (Result.RetainedTextChars + CountTextChars(Read) > 262144 - 1024)
        {
            Read = TextLimitFailure(TEXT("Batch DTO exceeds retained text budget"));
        }
        Result.RetainedTextChars += CountTextChars(Read);
        const bool bNodeAccepted = Read.bAccepted;
        Result.Nodes.Add(MoveTemp(Read));
        if (!bNodeAccepted)
        {
            Result.Error = TEXT("Stopped at rejected node; see final node record");
            Result.RetainedTextChars += Result.Error.Len();
            return Result;
        }
    }
    // Accepted means every requested scalar read was admitted, not complete capture.
    Result.bAccepted = true;
    return Result;
}
}
