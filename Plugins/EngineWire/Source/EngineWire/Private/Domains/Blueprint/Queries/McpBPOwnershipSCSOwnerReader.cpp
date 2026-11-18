#include "Domains/Blueprint/Queries/McpBPOwnershipSCSOwnerReader.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSSchema.h"

#include "Editor.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"

namespace McpBPOwnershipBindingReader
{
namespace
{
bool AllowedSCSOwner(const UBlueprint* BP)
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
        if (Package.Equals(Name, ESearchCase::CaseSensitive))
            return BP->GetPathName() == Package + TEXT(".") + FPackageName::GetLongPackageAssetName(Package);
    return false;
}

bool ObserveSCSOwnerPointer(const TObjectPtr<UObject>& Stored, FPointerObservation& Out)
{
    if (!Stored.IsResolved()) { Out.State = EPointerRead::Unresolved; return false; }
    const UObject* Object = Stored.Get();
    if (Object && !IsValid(Object)) { Out.State = EPointerRead::Invalid; return false; }
    Out.State = Object ? EPointerRead::Resolved : EPointerRead::Null;
    if (Object) Out.Path = Object->GetPathName();
    return true;
}
}

FSCSOwnerRead ReadSCSOwnerPointers(const UBlueprint* Blueprint)
{
    FSCSOwnerRead Result;
    if (!AllowedSCSOwner(Blueprint))
    {
        Result.Error = TEXT("Idle game-thread editor and exact allowlisted SCS Blueprint required");
        return Result;
    }
    const FSCSOwnerSchema Schema = InspectSCSOwnerSchema();
    if (!Schema.IsSupported()) { Result.Error = Schema.Error; return Result; }
    Result.PackageDirtyBefore = Blueprint->GetOutermost()->IsDirty();
    Result.BlueprintPath = Blueprint->GetPathName();
    const auto Raw = [](const FObjectProperty* Property, const void* Container)
    {
        return Property->GetObjectPtrPropertyValue(Property->ContainerPtrToValuePtr<void>(Container));
    };
    const TObjectPtr<UObject> Generated = Raw(Schema.BlueprintGeneratedClass, Blueprint);
    const TObjectPtr<UObject> BPSCS = Raw(Schema.BlueprintSCS, Blueprint);
    const TObjectPtr<UObject> BPHandler = Raw(Schema.BlueprintHandler, Blueprint);
    const bool GeneratedOK = ObserveSCSOwnerPointer(Generated, Result.GeneratedClass);
    const bool SCSOK = ObserveSCSOwnerPointer(BPSCS, Result.BlueprintSCS);
    const bool HandlerOK = ObserveSCSOwnerPointer(BPHandler, Result.BlueprintHandler);
    bool Safe = GeneratedOK && SCSOK && HandlerOK;
    if (Safe && Result.GeneratedClass.State == EPointerRead::Resolved)
    {
        const UBlueprintGeneratedClass* Class = Cast<UBlueprintGeneratedClass>(Generated.Get());
        // Never read external class storage merely because its pointer is resolved.
        if (!Class || Class->GetOutermost() != Blueprint->GetOutermost())
        {
            Safe = false;
            Result.Error = TEXT("Generated class is not a same-package BlueprintGeneratedClass");
        }
        else
        {
            const TObjectPtr<UObject> ClassSCS = Raw(Schema.GeneratedClassSCS, Class);
            const TObjectPtr<UObject> ClassHandler = Raw(Schema.GeneratedClassHandler, Class);
            const TObjectPtr<UObject> GeneratedBy = Class->ClassGeneratedBy;
            const bool ClassSCSOK = ObserveSCSOwnerPointer(ClassSCS, Result.ClassSCS);
            const bool ClassHandlerOK = ObserveSCSOwnerPointer(ClassHandler, Result.ClassHandler);
            const bool GeneratedByOK = ObserveSCSOwnerPointer(GeneratedBy, Result.ClassGeneratedBy);
            if (ClassSCSOK) Result.SameSCS = BPSCS.Get() == ClassSCS.Get();
            if (ClassHandlerOK) Result.SameHandler = BPHandler.Get() == ClassHandler.Get();
            if (GeneratedByOK) Result.ClassGeneratedByIsBlueprint = GeneratedBy.Get() == Blueprint;
            Safe = ClassSCSOK && ClassHandlerOK && GeneratedByOK;
        }
    }
    Result.PackageDirtyAfter = Blueprint->GetOutermost()->IsDirty();
    if (!AllowedSCSOwner(Blueprint) || Result.PackageDirtyAfter.GetValue() != Result.PackageDirtyBefore.GetValue())
    {
        Safe = false;
        Result.Error = TEXT("Observed SCS owner/editor/dirty state drift");
    }
    if (!Safe && Result.Error.IsEmpty()) Result.Error = TEXT("Unresolved or invalid SCS owner pointer");
    const int64 Text = int64(Result.BlueprintPath.Len()) + Result.GeneratedClass.Path.Len()
        + Result.BlueprintSCS.Path.Len() + Result.BlueprintHandler.Path.Len() + Result.ClassSCS.Path.Len()
        + Result.ClassHandler.Path.Len() + Result.ClassGeneratedBy.Path.Len() + Result.Error.Len();
    if (Text > 32768)
    {
        // Refuse without retaining oversized payload; not a peak allocation bound.
        FSCSOwnerRead Refused;
        Refused.Error = TEXT("SCS owner retained text exceeds32768 TCHAR budget");
        return Refused;
    }
    Result.bAccepted = Safe;
    // Accepted means raw observation only. Even mismatching identities are evidence,
    // not inferred ownership, a repair recommendation or complete SCS capture.
    return Result;
}
} // namespace McpBPOwnershipBindingReader
