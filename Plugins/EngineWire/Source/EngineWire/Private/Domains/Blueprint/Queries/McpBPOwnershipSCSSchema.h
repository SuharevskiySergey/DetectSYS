#pragma once

#include "CoreMinimal.h"

class FArrayProperty;
class FObjectProperty;
class FStructProperty;
class FNameProperty;
class FBoolProperty;

namespace McpBPOwnershipBindingReader
{
// Internal draft gate for the three raw node lists, NOT the full capture schema.
// Property descriptors only; never contains instance pointers or copied arrays.
struct FSCSListSchema
{
    const FArrayProperty* Roots = nullptr;
    const FArrayProperty* Registry = nullptr;
    const FArrayProperty* Children = nullptr;
    FString Error;

    bool IsSupported() const { return Roots && Registry && Children && Error.IsEmpty(); }
};

// Game-thread only. Looks up native class metadata; no SCS getter/instance read.
// May initialize native StaticClass metadata. Not an offline/pure DTO operation.
FSCSListSchema InspectSCSListSchema();

struct FSCSNodeSchema
{
    const FObjectProperty* ComponentClass = nullptr;
    const FObjectProperty* ComponentTemplate = nullptr;
    const FStructProperty* VariableGuid = nullptr;
    const FNameProperty* VariableName = nullptr;
    const FNameProperty* AttachToName = nullptr;
    const FNameProperty* ParentName = nullptr;
    const FNameProperty* ParentOwnerClassName = nullptr;
    const FBoolProperty* IsParentNative = nullptr;
    FString Error;

    bool IsSupported() const
    {
        return ComponentClass && ComponentTemplate && VariableGuid && VariableName
            && AttachToName && ParentName && ParentOwnerClassName && IsParentNative && Error.IsEmpty();
    }
};

// Separate all-or-none payload gate; list admission alone never admits a node.
FSCSNodeSchema InspectSCSNodeSchema();

struct FSCSOwnerSchema
{
    // GeneratedClass is declared by UBlueprintCore, not UBlueprint.
    const FObjectProperty* BlueprintGeneratedClass = nullptr;
    const FObjectProperty* BlueprintSCS = nullptr;
    const FObjectProperty* BlueprintHandler = nullptr;
    const FObjectProperty* GeneratedClassSCS = nullptr;
    const FObjectProperty* GeneratedClassHandler = nullptr;
    FString Error;

    bool IsSupported() const
    {
        return BlueprintGeneratedClass && BlueprintSCS && BlueprintHandler
            && GeneratedClassSCS && GeneratedClassHandler && Error.IsEmpty();
    }
};

// Storage-layout admission only: does not compare live ownership, inspect
// ClassGeneratedBy's typed C++ member or read superclass.
FSCSOwnerSchema InspectSCSOwnerSchema();
} // namespace McpBPOwnershipBindingReader
