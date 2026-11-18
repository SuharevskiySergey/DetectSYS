#include "Domains/Blueprint/Queries/McpBPOwnershipSCSNodeReader.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSListReader.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSSchema.h"

#include "Engine/Blueprint.h"
#include "Engine/SCS_Node.h"
#include "Engine/SimpleConstructionScript.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"

namespace McpBPOwnershipBindingReader
{
namespace
{
bool ContainsRawSCSNode(const FArrayProperty* Property, const USimpleConstructionScript* SCS, const USCS_Node* Node)
{
    FScriptArrayHelper Array(Property, Property->ContainerPtrToValuePtr<void>(static_cast<const void*>(SCS)));
    // Both list budgets were admitted before this identity scan; recheck before
    // any access because the descriptor alone does not certify instance state.
    if (Array.Num() > 128) return false;
    const FObjectProperty* Inner = CastFieldChecked<FObjectProperty>(Property->Inner);
    for (int32 Index = 0; Index < Array.Num(); ++Index)
    {
        const TObjectPtr<UObject> Stored = Inner->GetObjectPtrPropertyValue(Array.GetRawPtr(Index));
        if (!Stored.IsResolved()) return false;
        if (Stored.Get() == Node) return true;
    }
    return false;
}

bool ObserveSCSNodePointer(const FObjectProperty* Property, const USCS_Node* Node, FPointerObservation& Out)
{
    const TObjectPtr<UObject> Stored = Property->GetObjectPtrPropertyValue(
        Property->ContainerPtrToValuePtr<void>(static_cast<const void*>(Node)));
    if (!Stored.IsResolved()) { Out.State = EPointerRead::Unresolved; return false; }
    const UObject* Object = Stored.Get();
    if (Object && !IsValid(Object)) { Out.State = EPointerRead::Invalid; return false; }
    Out.State = Object ? EPointerRead::Resolved : EPointerRead::Null;
    if (Object) Out.Path = Object->GetPathName();
    return true; // Pointer/path only; external template payload is never read.
}
}

FSCSNodeRead ReadSCSNodePayload(const UBlueprint* Blueprint, const USimpleConstructionScript* SCS, const USCS_Node* Node)
{
    FSCSNodeRead Result;
    const FSCSListsRead Lists = ReadSCSRawLists(Blueprint, SCS);
    if (!Lists.bAccepted) { Result.Error = Lists.Error; return Result; }
    if (!IsValid(Node) || Node->GetOuter() != SCS)
    {
        Result.Error = TEXT("Live SCS node with exact supplied SCS outer required");
        return Result;
    }
    const FSCSListSchema ListSchema = InspectSCSListSchema();
    const FSCSNodeSchema Schema = InspectSCSNodeSchema();
    if (!ListSchema.IsSupported() || !Schema.IsSupported())
    {
        Result.Error = TEXT("Unsupported SCS node/list payload schema");
        return Result;
    }
    const auto IsMember = [&]()
    {
        return ContainsRawSCSNode(ListSchema.Roots, SCS, Node) || ContainsRawSCSNode(ListSchema.Registry, SCS, Node);
    };
    if (!IsMember()) { Result.Error = TEXT("SCS node absent from admitted raw roots/registry"); return Result; }
    Result.PackageDirtyBefore = Blueprint->GetOutermost()->IsDirty();
    Result.Node.NodePath = Node->GetPathName();
    Result.Node.Outer.State = EPointerRead::Resolved;
    Result.Node.Outer.Path = SCS->GetPathName();
    Result.Node.VariableGuid = *Schema.VariableGuid->ContainerPtrToValuePtr<FGuid>(static_cast<const void*>(Node));
    const auto Name = [Node](const FNameProperty* Property)
    {
        return Property->GetPropertyValue(Property->ContainerPtrToValuePtr<void>(static_cast<const void*>(Node)));
    };
    Result.Node.VariableName = Name(Schema.VariableName);
    Result.Node.AttachToName = Name(Schema.AttachToName);
    Result.Node.ParentComponentOrVariableName = Name(Schema.ParentName);
    Result.Node.ParentComponentOwnerClassName = Name(Schema.ParentOwnerClassName);
    Result.Node.IsParentComponentNative = Schema.IsParentNative->GetPropertyValue(
        Schema.IsParentNative->ContainerPtrToValuePtr<void>(static_cast<const void*>(Node)));
    const bool ClassOK = ObserveSCSNodePointer(Schema.ComponentClass, Node, Result.Node.ComponentClass);
    const bool TemplateOK = ObserveSCSNodePointer(Schema.ComponentTemplate, Node, Result.Node.ComponentTemplate);
    Result.Uncaptured.Add({TEXT("children, scene_flags, effective_template, revisions, lifetime"), EGapReason::NotCaptured});
    Result.PackageDirtyAfter = Blueprint->GetOutermost()->IsDirty();
    const FSCSListsRead After = ReadSCSRawLists(Blueprint, SCS);
    if (!After.bAccepted || !IsValid(Node) || Node->GetOuter() != SCS || !IsMember()
        || Result.PackageDirtyAfter.GetValue() != Result.PackageDirtyBefore.GetValue())
        Result.Error = TEXT("SCS node owner/list/dirty state drift");
    else if (!ClassOK || !TemplateOK) Result.Error = TEXT("Unresolved or invalid SCS node payload pointer");

    int64 Text = int64(Result.Node.NodePath.Len()) + Result.Node.Outer.Path.Len()
        + Result.Node.ComponentClass.Path.Len() + Result.Node.ComponentTemplate.Path.Len()
        + Result.Node.VariableName.ToString().Len() + Result.Node.AttachToName.ToString().Len()
        + Result.Node.ParentComponentOrVariableName.ToString().Len() + Result.Node.ParentComponentOwnerClassName.ToString().Len()
        + Result.Error.Len();
    for (const FReadGap& Gap : Result.Uncaptured) Text += Gap.Field.Len();
    if (Text > 32768)
    {
        FSCSNodeRead Refused;
        Refused.Error = TEXT("SCS node retained text exceeds32768 TCHAR budget");
        return Refused;
    }
    Result.bAccepted = Result.Error.IsEmpty();
    return Result; // Missing GUID/name/null template remain raw observations, never repaired.
}
} // namespace McpBPOwnershipBindingReader
