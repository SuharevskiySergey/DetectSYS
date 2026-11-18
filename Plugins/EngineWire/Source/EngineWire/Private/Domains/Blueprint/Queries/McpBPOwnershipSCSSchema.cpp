#include "Domains/Blueprint/Queries/McpBPOwnershipSCSSchema.h"

#include "Engine/SCS_Node.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintCore.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/InheritableComponentHandler.h"
#include "Engine/SimpleConstructionScript.h"
#include "Components/ActorComponent.h"
#include "UObject/NoExportTypes.h"
#include "UObject/UnrealType.h"

namespace McpBPOwnershipBindingReader
{
namespace
{
const FObjectProperty* FindRawOwnerPointer(const UClass* DeclaringClass, const FName Name, const UClass* ValueClass)
{
    const FObjectProperty* Property = FindFProperty<FObjectProperty>(DeclaringClass, Name);
    return Property && Property->GetOwnerClass() == DeclaringClass
        && Property->ArrayDim == 1 && !Property->HasGetter() && !Property->HasSetter()
        && Property->PropertyClass == ValueClass && Property->HasAnyPropertyFlags(CPF_TObjectPtr)
        ? Property : nullptr;
}

template<typename T>
const T* FindRawNodeField(const FName Name)
{
    const T* Property = FindFProperty<T>(USCS_Node::StaticClass(), Name);
    return Property && Property->GetOwnerClass() == USCS_Node::StaticClass()
        && Property->ArrayDim == 1 && !Property->HasGetter() && !Property->HasSetter() ? Property : nullptr;
}

const FArrayProperty* FindRawNodeList(const UClass* OwnerClass, const FName Name)
{
    const FArrayProperty* Array = FindFProperty<FArrayProperty>(OwnerClass, Name);
    if (!Array || Array->GetOwnerClass() != OwnerClass || Array->ArrayDim != 1
        || Array->HasGetter() || Array->HasSetter()) return nullptr;
    const FObjectProperty* Inner = CastField<FObjectProperty>(Array->Inner);
    if (!Inner || Inner->ArrayDim != 1 || Inner->HasGetter() || Inner->HasSetter()
        || Inner->PropertyClass != USCS_Node::StaticClass()
        || !Inner->HasAnyPropertyFlags(CPF_TObjectPtr)) return nullptr;
    return Array;
}
}

FSCSListSchema InspectSCSListSchema()
{
    FSCSListSchema Result;
    if (!IsInGameThread())
    {
        Result.Error = TEXT("SCS list schema inspection requires game thread");
        return Result;
    }
    const FArrayProperty* Roots = FindRawNodeList(USimpleConstructionScript::StaticClass(), TEXT("RootNodes"));
    const FArrayProperty* Registry = FindRawNodeList(USimpleConstructionScript::StaticClass(), TEXT("AllNodes"));
    const FArrayProperty* Children = FindRawNodeList(USCS_Node::StaticClass(), TEXT("ChildNodes"));
    if (!Roots || !Registry || !Children)
    {
        // No partially admitted layout and no fallback to GetAllNodes/GetChildNodes.
        Result.Error = FString::Printf(TEXT("Unsupported raw SCS node-list schema: roots=%d registry=%d children=%d"),
            Roots != nullptr, Registry != nullptr, Children != nullptr);
        return Result;
    }
    Result.Roots = Roots;
    Result.Registry = Registry;
    Result.Children = Children;
    return Result;
}

FSCSOwnerSchema InspectSCSOwnerSchema()
{
    FSCSOwnerSchema Result;
    if (!IsInGameThread())
    {
        Result.Error = TEXT("SCS owner schema inspection requires game thread");
        return Result;
    }
    FSCSOwnerSchema Candidate;
    // TSubclassOf must be read as stored FClassProperty wrapper, never .Get().
    const FClassProperty* Generated = FindFProperty<FClassProperty>(UBlueprintCore::StaticClass(), TEXT("GeneratedClass"));
    // UE5.6 UHT marks TSubclassOf with CPF_UObjectWrapper, not CPF_TObjectPtr.
    // Keep this explicit form separate from the four TObjectPtr fields below.
    if (Generated && Generated->GetOwnerClass() == UBlueprintCore::StaticClass()
        && Generated->ArrayDim == 1 && !Generated->HasGetter() && !Generated->HasSetter()
        && Generated->PropertyClass == UClass::StaticClass() && Generated->MetaClass == UObject::StaticClass()
        && Generated->HasAnyPropertyFlags(CPF_UObjectWrapper) && !Generated->HasAnyPropertyFlags(CPF_TObjectPtr))
        Candidate.BlueprintGeneratedClass = Generated;
    Candidate.BlueprintSCS = FindRawOwnerPointer(UBlueprint::StaticClass(), TEXT("SimpleConstructionScript"), USimpleConstructionScript::StaticClass());
    Candidate.BlueprintHandler = FindRawOwnerPointer(UBlueprint::StaticClass(), TEXT("InheritableComponentHandler"), UInheritableComponentHandler::StaticClass());
    Candidate.GeneratedClassSCS = FindRawOwnerPointer(UBlueprintGeneratedClass::StaticClass(), TEXT("SimpleConstructionScript"), USimpleConstructionScript::StaticClass());
    Candidate.GeneratedClassHandler = FindRawOwnerPointer(UBlueprintGeneratedClass::StaticClass(), TEXT("InheritableComponentHandler"), UInheritableComponentHandler::StaticClass());
    if (!Candidate.IsSupported())
    {
        Result.Error = FString::Printf(
            TEXT("Unsupported raw SCS owner pointer schema: BP.GeneratedClass=%d BP.SCS=%d BP.Handler=%d Class.SCS=%d Class.Handler=%d; no inferred ownership fallback"),
            Candidate.BlueprintGeneratedClass != nullptr, Candidate.BlueprintSCS != nullptr,
            Candidate.BlueprintHandler != nullptr, Candidate.GeneratedClassSCS != nullptr,
            Candidate.GeneratedClassHandler != nullptr);
        return Result;
    }
    return Candidate;
}

FSCSNodeSchema InspectSCSNodeSchema()
{
    FSCSNodeSchema Result;
    if (!IsInGameThread())
    {
        Result.Error = TEXT("SCS node schema inspection requires game thread");
        return Result;
    }
    FSCSNodeSchema Candidate;
    Candidate.ComponentClass = FindRawNodeField<FObjectProperty>(TEXT("ComponentClass"));
    Candidate.ComponentTemplate = FindRawNodeField<FObjectProperty>(TEXT("ComponentTemplate"));
    Candidate.VariableGuid = FindRawNodeField<FStructProperty>(TEXT("VariableGuid"));
    Candidate.VariableName = FindRawNodeField<FNameProperty>(TEXT("InternalVariableName"));
    Candidate.AttachToName = FindRawNodeField<FNameProperty>(TEXT("AttachToName"));
    Candidate.ParentName = FindRawNodeField<FNameProperty>(TEXT("ParentComponentOrVariableName"));
    Candidate.ParentOwnerClassName = FindRawNodeField<FNameProperty>(TEXT("ParentComponentOwnerClassName"));
    Candidate.IsParentNative = FindRawNodeField<FBoolProperty>(TEXT("bIsParentComponentNative"));
    const bool ClassLayout = Candidate.ComponentClass
        && Candidate.ComponentClass->PropertyClass == UClass::StaticClass()
        && Candidate.ComponentClass->HasAnyPropertyFlags(CPF_TObjectPtr);
    const bool TemplateLayout = Candidate.ComponentTemplate
        && Candidate.ComponentTemplate->PropertyClass == UActorComponent::StaticClass()
        && Candidate.ComponentTemplate->HasAnyPropertyFlags(CPF_TObjectPtr);
    const bool GuidLayout = Candidate.VariableGuid && Candidate.VariableGuid->Struct == TBaseStructure<FGuid>::Get();
    if (!Candidate.IsSupported() || !ClassLayout || !TemplateLayout || !GuidLayout)
    {
        // Return no usable subset if even one payload field has unexpected storage.
        Result.Error = TEXT("Unsupported raw SCS node payload schema; no getter fallback");
        return Result;
    }
    return Candidate;
}
} // namespace McpBPOwnershipBindingReader
