#include "Domains/Blueprint/Queries/McpBPOwnershipSCSListReader.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSOwnerReader.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSSchema.h"

#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/SCS_Node.h"
#include "Engine/SimpleConstructionScript.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"

namespace McpBPOwnershipBindingReader
{
FSCSListsRead ReadSCSRawLists(const UBlueprint* Blueprint, const USimpleConstructionScript* SCS)
{
    FSCSListsRead Result;
    // Owner reader refuses before UObject access on wrong thread/null/unlisted BP.
    const FSCSOwnerRead Owner = ReadSCSOwnerPointers(Blueprint);
    if (!Owner.bAccepted) { Result.Error = Owner.Error; return Result; }
    if (!IsValid(SCS)) { Result.Error = TEXT("Explicit live non-null SCS required"); return Result; }
    const FSCSOwnerSchema OwnerSchema = InspectSCSOwnerSchema();
    const FSCSListSchema Lists = InspectSCSListSchema();
    if (!OwnerSchema.IsSupported() || !Lists.IsSupported())
    {
        Result.Error = TEXT("Unsupported SCS owner/list storage schema");
        return Result;
    }
    const auto Raw = [](const FObjectProperty* Property, const void* Container)
    {
        return Property->GetObjectPtrPropertyValue(Property->ContainerPtrToValuePtr<void>(Container));
    };
    const TObjectPtr<UObject> BPStored = Raw(OwnerSchema.BlueprintSCS, Blueprint);
    const TObjectPtr<UObject> Generated = Raw(OwnerSchema.BlueprintGeneratedClass, Blueprint);
    if (!BPStored.IsResolved() || !Generated.IsResolved())
    {
        Result.Error = TEXT("Unresolved SCS admission pointer");
        return Result;
    }
    const UBlueprintGeneratedClass* Class = nullptr;
    if (Generated.Get())
    {
        if (!IsValid(Generated.Get())) { Result.Error = TEXT("Invalid SCS generated class"); return Result; }
        Class = Cast<UBlueprintGeneratedClass>(Generated.Get());
        if (!Class || Class->GetOutermost() != Blueprint->GetOutermost())
        {
            Result.Error = TEXT("External or unsupported SCS generated class");
            return Result;
        }
    }
    TObjectPtr<UObject> ClassStored;
    if (Class) ClassStored = Raw(OwnerSchema.GeneratedClassSCS, Class);
    if (!ClassStored.IsResolved()) { Result.Error = TEXT("Unresolved class SCS pointer"); return Result; }
    if ((BPStored.Get() != SCS && ClassStored.Get() != SCS)
        || SCS->GetOutermost() != Blueprint->GetOutermost()
        || (SCS->GetOuter() != Blueprint && SCS->GetOuter() != Class))
    {
        Result.Error = TEXT("SCS is not an admitted stored pointer with exact BP/class outer");
        return Result;
    }

    Result.PackageDirtyBefore = Blueprint->GetOutermost()->IsDirty();
    Result.SCSPath = SCS->GetPathName();
    // UE5.6 GetRawPtr is non-const even for address-only access. Helpers stay
    // local/mutable; returned element storage is consumed only by a const getter.
    FScriptArrayHelper RootArray(Lists.Roots, Lists.Roots->ContainerPtrToValuePtr<void>(static_cast<const void*>(SCS)));
    FScriptArrayHelper RegistryArray(Lists.Registry, Lists.Registry->ContainerPtrToValuePtr<void>(static_cast<const void*>(SCS)));
    if (RootArray.Num() > FSCSInventoryBudget::MaxRootEntries || RegistryArray.Num() > FSCSInventoryBudget::MaxRegistryEntries)
    {
        Result.Error = TEXT("SCS raw list entry limit exceeded before copying");
        return Result;
    }
    int64 Text = Result.SCSPath.Len();
    constexpr int64 PayloadTextBudget = FSCSInventoryBudget::MaxRetainedTextChars - 512; // Reserve bounded error text.
    if (Text > PayloadTextBudget)
    {
        Result.SCSPath.Reset();
        Result.Error = TEXT("SCS identity text limit exceeded");
        return Result;
    }
    const auto CopyList = [&](const FArrayProperty* Property, FScriptArrayHelper& Array, TArray<FSCSListEntry>& Out) -> bool
    {
        const FObjectProperty* Inner = CastFieldChecked<FObjectProperty>(Property->Inner); // Schema admitted this exact inner.
        for (int32 Index = 0; Index < Array.Num(); ++Index)
        {
            FSCSListEntry Entry;
            Entry.Index = Index;
            const TObjectPtr<UObject> Stored = Inner->GetObjectPtrPropertyValue(Array.GetRawPtr(Index));
            bool Safe = Stored.IsResolved();
            if (!Safe) Entry.Target.State = EPointerRead::Unresolved;
            else
            {
                const UObject* Object = Stored.Get();
                if (Object && !IsValid(Object)) { Entry.Target.State = EPointerRead::Invalid; Safe = false; }
                else
                {
                    Entry.Target.State = Object ? EPointerRead::Resolved : EPointerRead::Null;
                    if (Object)
                    {
                        Entry.Target.Path = Object->GetPathName();
                        Safe = Object->IsA<USCS_Node>() && Object->GetOuter() == SCS;
                    }
                }
            }
            Text += Entry.Target.Path.Len();
            if (Text > PayloadTextBudget)
            {
                Result.Roots.Reset(); Result.Registry.Reset(); Result.SCSPath.Reset();
                Result.Error = TEXT("SCS raw list retained text limit exceeded");
                return false;
            }
            Out.Add(MoveTemp(Entry)); // Preserve duplicate/null indices, never populate AllNodes.
            if (!Safe)
            {
                Result.Error = TEXT("Unresolved, invalid or wrong-outer SCS list entry");
                return false;
            }
        }
        return true;
    };
    if (!CopyList(Lists.Roots, RootArray, Result.Roots) || !CopyList(Lists.Registry, RegistryArray, Result.Registry)) return Result;
    Result.PackageDirtyAfter = Blueprint->GetOutermost()->IsDirty();
    const FSCSOwnerRead After = ReadSCSOwnerPointers(Blueprint);
    if (!After.bAccepted || Result.PackageDirtyAfter.GetValue() != Result.PackageDirtyBefore.GetValue())
    {
        Result.Error = TEXT("SCS raw list owner/editor/dirty drift");
        return Result;
    }
    const TObjectPtr<UObject> BPAfter = Raw(OwnerSchema.BlueprintSCS, Blueprint);
    const TObjectPtr<UObject> GeneratedAfter = Raw(OwnerSchema.BlueprintGeneratedClass, Blueprint);
    TObjectPtr<UObject> ClassAfter;
    if (Class)
    {
        if (!IsValid(Class)) { Result.Error = TEXT("SCS generated class invalidated"); return Result; }
        ClassAfter = Raw(OwnerSchema.GeneratedClassSCS, Class);
    }
    if (!BPAfter.IsResolved() || !GeneratedAfter.IsResolved() || !ClassAfter.IsResolved()
        || BPAfter.Get() != BPStored.Get() || GeneratedAfter.Get() != Generated.Get()
        || ClassAfter.Get() != ClassStored.Get())
    {
        Result.Error = TEXT("SCS admission pointer drift");
        return Result;
    }
    Result.bAccepted = true;
    return Result; // bComplete stays false; no coherence/effective-template certificate.
}
} // namespace McpBPOwnershipBindingReader
