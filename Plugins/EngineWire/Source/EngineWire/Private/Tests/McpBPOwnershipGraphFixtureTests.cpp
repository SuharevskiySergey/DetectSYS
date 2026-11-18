#include "Domains/Blueprint/Queries/McpBPOwnershipStructureReader.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipOverrideReview.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSOwnerReader.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSSchema.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSListReader.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSNodeReader.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSChildrenReader.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "EdGraph/EdGraph.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/InheritableComponentHandler.h"
#include "Engine/SimpleConstructionScript.h"
#include "Components/SceneComponent.h"
#include "HAL/PlatformMisc.h"
#include "K2Node_Composite.h"
#include "K2Node_VariableGet.h"
#include "Misc/App.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "UObject/Package.h"
#include "UObject/NoExportTypes.h"
#include "UObject/StrongObjectPtr.h"
#include "UObject/UnrealType.h"

namespace
{
using namespace McpBPOwnershipBindingReader;

bool PermitTransientFixtures(FAutomationTestBase& Test)
{
    FString TempRoot = FPlatformMisc::GetEnvironmentVariable(TEXT("LOCALAPPDATA"));
    if (TempRoot.IsEmpty())
    {
        Test.AddError(TEXT("LOCALAPPDATA required for isolated fixture guard"));
        return false;
    }
    TempRoot = FPaths::Combine(TempRoot, TEXT("Temp/opencode"));
    const FString ProjectDir = FPaths::GetPath(FPaths::ConvertRelativePathToFull(FPaths::GetProjectFilePath()));
    if (!IsInGameThread() || !GEditor || GEditor->IsPlaySessionInProgress()
        || FString(FApp::GetProjectName()) != TEXT("BeholderStructureTestHost")
        || !FPaths::IsUnderDirectory(ProjectDir, TempRoot)
        || !FParse::Param(FCommandLine::Get(), TEXT("McpOwnershipTransientFixtures")))
    {
        Test.AddError(TEXT("Transient fixtures require idle isolated Temp/opencode BeholderStructureTestHost and explicit -McpOwnershipTransientFixtures opt-in"));
        return false;
    }
    return true;
}

UBlueprint* MakeFixture(FAutomationTestBase& Test, const TCHAR* Path, TStrongObjectPtr<UPackage>& KeepPackage)
{
    // Never load, overwrite, rename or recycle an existing package, even in the test host.
    if (FindPackage(nullptr, Path) || FPackageName::DoesPackageExist(Path))
    {
        Test.AddError(TEXT("Fixture package already exists in memory or on disk; refusing creation"));
        return nullptr;
    }
    UPackage* Package = CreatePackage(Path);
    KeepPackage.Reset(Package);
    Package->SetFlags(RF_Transient);
    return NewObject<UBlueprint>(Package, *FPackageName::GetLongPackageAssetName(Path), RF_Transient);
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipGraphCycleFixture,
    "EngineWire.OwnershipGraphFixtures.NestedCycle",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipGraphCycleFixture::RunTest(const FString& Parameters)
{
    if (!PermitTransientFixtures(*this)) return false;
    TStrongObjectPtr<UPackage> Package;
    TStrongObjectPtr<UBlueprint> BP(MakeFixture(*this,
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/BP_OwnershipTelescope"), Package));
    if (!BP.IsValid()) return false;
    UEdGraph* Root = NewObject<UEdGraph>(BP.Get(), TEXT("FixtureRoot"), RF_Transient);
    UEdGraph* Child = NewObject<UEdGraph>(BP.Get(), TEXT("FixtureChild"), RF_Transient);
    BP->FunctionGraphs.Add(Root);
    BP->FunctionGraphs.Add(Child);
    UK2Node_Composite* Composite = NewObject<UK2Node_Composite>(Root, TEXT("FixtureComposite"), RF_Transient);
    UK2Node_VariableGet* Variable = NewObject<UK2Node_VariableGet>(Child, TEXT("FixtureVariable"), RF_Transient);
    const FGuid MemberGuid(1, 2, 3, 4);
    const FGuid NodeGuid(5, 6, 7, 8);
    Variable->VariableReference.SetSelfMember(TEXT("FixtureValue"), MemberGuid);
    Variable->NodeGuid = NodeGuid;
    Root->Nodes.Add(Composite);
    Child->Nodes.Add(Variable);
    Composite->BoundGraph = Child;
    Root->SubGraphs.Add(Child);
    Child->SubGraphs.Add(Root);
    const bool DirtyBefore = Package->IsDirty();
    const FGraphTreeRead Read = ReadGraphTree(Root);
    TestTrue(TEXT("Non-null graph read admitted"), Read.bAccepted);
    TestFalse(TEXT("Subtree is not complete asset capture"), Read.bComplete);
    TestEqual(TEXT("Cycle/duplicate target visited once"), Read.GraphPaths.Num(), 2);
    TestEqual(TEXT("Both authored nodes captured"), Read.Nodes.Num(), 2);
    TestEqual(TEXT("Both root edges and cycle provenance retained"), Read.Edges.Num(), 3);
    if (Read.GraphPaths.Num() == 2)
    {
        TestEqual(TEXT("First graph is supplied root"), Read.GraphPaths[0], Root->GetPathName());
        TestEqual(TEXT("Second graph is shared child"), Read.GraphPaths[1], Child->GetPathName());
    }
    if (Read.Edges.Num() == 3)
    {
        TestEqual(TEXT("First edge is composite binding"), Read.Edges[0].Relation, FString(TEXT("BoundGraph")));
        TestEqual(TEXT("Composite provenance is node path"), Read.Edges[0].SourcePath, Composite->GetPathName());
        TestEqual(TEXT("Composite points at child"), Read.Edges[0].Target.Path, Child->GetPathName());
        TestEqual(TEXT("Second edge retains duplicate SubGraphs provenance"), Read.Edges[1].Relation, FString(TEXT("SubGraphs")));
        TestEqual(TEXT("Duplicate edge has root source"), Read.Edges[1].SourcePath, Root->GetPathName());
        TestEqual(TEXT("Duplicate edge still targets child"), Read.Edges[1].Target.Path, Child->GetPathName());
        TestEqual(TEXT("Cycle edge has child source"), Read.Edges[2].SourcePath, Child->GetPathName());
        TestEqual(TEXT("Cycle edge points back to root"), Read.Edges[2].Target.Path, Root->GetPathName());
        for (const FGraphEdgeRead& Edge : Read.Edges)
            TestEqual(TEXT("Fixture edges are resolved"), static_cast<int32>(Edge.Target.State), static_cast<int32>(EPointerRead::Resolved));
    }
    for (const FReadGap& Gap : Read.Uncaptured)
        TestTrue(TEXT("Known partial coverage is not a traversal limit"), Gap.Reason != EGapReason::LimitExceeded);
    if (Read.Nodes.Num() == 2 && Read.Nodes[1].Members.Num() == 1)
    {
        TestEqual(TEXT("Raw self name without resolving declaration"), Read.Nodes[1].Members[0].Name, FName(TEXT("FixtureValue")));
        TestTrue(TEXT("Raw member GUID preserved"), Read.Nodes[1].Members[0].MemberGuid == MemberGuid);
        TestTrue(TEXT("Node GUID distinct and preserved"), Read.Nodes[1].NodeGuid == NodeGuid);
        TestTrue(TEXT("Raw self-context preserved"), Read.Nodes[1].Members[0].bSelfContext);
        TestEqual(TEXT("Self member stores null parent, not inferred Blueprint owner"),
            static_cast<int32>(Read.Nodes[1].Members[0].RawParent.State), static_cast<int32>(EPointerRead::Null));
        TestTrue(TEXT("Null parent has no fabricated path"), Read.Nodes[1].Members[0].RawParent.Path.IsEmpty());
    }
    else AddError(TEXT("Expected one raw variable reference on the child node"));
    TestEqual(TEXT("Reader did not change dirty bit"), Package->IsDirty(), DirtyBefore);
    TestTrue(TEXT("Reader preserved composite binding"), Composite->BoundGraph.Get() == Child);
    TestEqual(TEXT("Reader preserved raw member name"), Variable->VariableReference.GetMemberName(), FName(TEXT("FixtureValue")));
    TestTrue(TEXT("Reader preserved raw member GUID"), Variable->VariableReference.GetMemberGuid() == MemberGuid);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipGraphWrongOuterFixture,
    "EngineWire.OwnershipGraphFixtures.WrongGraphOuter",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipGraphWrongOuterFixture::RunTest(const FString& Parameters)
{
    if (!PermitTransientFixtures(*this)) return false;
    TStrongObjectPtr<UPackage> Package;
    TStrongObjectPtr<UBlueprint> BP(MakeFixture(*this,
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/BP_OwnershipBodyLeg"), Package));
    if (!BP.IsValid()) return false;
    UEdGraph* Root = NewObject<UEdGraph>(BP.Get(), TEXT("FixtureRoot"), RF_Transient);
    UEdGraph* Other = NewObject<UEdGraph>(BP.Get(), TEXT("FixtureOther"), RF_Transient);
    BP->FunctionGraphs.Add(Root);
    BP->FunctionGraphs.Add(Other);
    Root->Nodes.Add(NewObject<UK2Node_VariableGet>(Other, TEXT("MisplacedNode"), RF_Transient));
    const bool DirtyBefore = Package->IsDirty();
    const FGraphTreeRead Read = ReadGraphTree(Root);
    TestFalse(TEXT("Same BP but wrong graph node is refused"), Read.bAccepted);
    TestFalse(TEXT("Refused traversal cannot be complete"), Read.bComplete);
    TestTrue(TEXT("Rejected node payload not captured"), Read.Nodes.IsEmpty());
    TestEqual(TEXT("Wrong-graph gate reason"), Read.Error,
        FString(TEXT("Invalid, external-owner or wrong-graph node; traversal stopped")));
    TestEqual(TEXT("Refusal did not change dirty bit"), Package->IsDirty(), DirtyBefore);
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipOverrideRecordFixture,
    "EngineWire.OwnershipOverrideFixtures.RawRecord",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipOverrideRecordFixture::RunTest(const FString& Parameters)
{
    if (!PermitTransientFixtures(*this)) return false;
    TStrongObjectPtr<UPackage> Package;
    TStrongObjectPtr<UBlueprint> BP(MakeFixture(*this,
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/BP_OwnershipRedistribution"), Package));
    if (!BP.IsValid()) return false;

    // Validate native reflected layout before modifying ONLY this transient fixture.
    const FArrayProperty* Records = FindFProperty<FArrayProperty>(UInheritableComponentHandler::StaticClass(), TEXT("Records"));
    const FStructProperty* Inner = Records ? CastField<FStructProperty>(Records->Inner) : nullptr;
    const FObjectProperty* Owner = FindFProperty<FObjectProperty>(FComponentKey::StaticStruct(), TEXT("OwnerClass"));
    const FNameProperty* Name = FindFProperty<FNameProperty>(FComponentKey::StaticStruct(), TEXT("SCSVariableName"));
    const FStructProperty* Guid = FindFProperty<FStructProperty>(FComponentKey::StaticStruct(), TEXT("AssociatedGuid"));
    if (!Records || Records->ArrayDim != 1 || !Inner || Inner->Struct != FComponentOverrideRecord::StaticStruct()
        || !Owner || Owner->ArrayDim != 1 || Owner->HasSetter() || Owner->PropertyClass != UClass::StaticClass()
        || !Name || Name->ArrayDim != 1 || !Guid || Guid->ArrayDim != 1 || Guid->Struct != TBaseStructure<FGuid>::Get())
    {
        AddError(TEXT("Unsupported fixture record/key reflected layout; no fallback or engine schema changes"));
        return false;
    }
    UInheritableComponentHandler* Handler = NewObject<UInheritableComponentHandler>(BP.Get(), TEXT("FixtureHandler"), RF_Transient);
    BP->InheritableComponentHandler = Handler;
    USceneComponent* Template = NewObject<USceneComponent>(Handler, TEXT("FixtureSocketHousing"), RF_Transient | RF_ArchetypeObject);
    Template->SetVisibleFlag(false);
    Template->bHiddenInGame = true;
    auto* Storage = Records->ContainerPtrToValuePtr<TArray<FComponentOverrideRecord>>(Handler);
    FComponentOverrideRecord& Record = Storage->AddDefaulted_GetRef();
    Record.ComponentClass = USceneComponent::StaticClass();
    Record.ComponentTemplate = Template;
    // Synthetic key, not an installed SCS dependency; never resolve it to a node.
    Owner->SetObjectPropertyValue_InContainer(&Record.ComponentKey, UBlueprint::StaticClass());
    Name->SetPropertyValue(Name->ContainerPtrToValuePtr<void>(&Record.ComponentKey), FName(TEXT("FixtureSocketHousing")));
    const FGuid ExpectedGuid(9, 10, 11, 12);
    *Guid->ContainerPtrToValuePtr<FGuid>(&Record.ComponentKey) = ExpectedGuid;
    const bool DirtyBefore = Package->IsDirty();

    for (int32 Pass = 0; Pass < 2; ++Pass)
    {
        const bool Visible = Pass == 1;
        Template->SetVisibleFlag(Visible);
        Template->bHiddenInGame = !Visible;
        const FOverridesRead Read = ReadOwnOverrides(BP.Get());
        TestTrue(TEXT("Non-null own-record read admitted"), Read.bAccepted);
        TestFalse(TEXT("Own records are not full inherited capture"), Read.bComplete);
        TestEqual(TEXT("One synthetic record"), Read.Records.Num(), 1);
        TestEqual(TEXT("Exact handler path"), Read.Handler.Path, Handler->GetPathName());
        if (Read.Records.Num() == 1)
        {
            const FOverrideRead& Captured = Read.Records[0];
            TestEqual(TEXT("Raw key name"), Captured.VariableName, FName(TEXT("FixtureSocketHousing")));
            TestTrue(TEXT("Raw key GUID"), Captured.AssociatedGuid == ExpectedGuid);
            TestEqual(TEXT("Stored owner path, not effective owner inference"), Captured.KeyOwner.Path, UBlueprint::StaticClass()->GetPathName());
            TestEqual(TEXT("Owner pointer resolved"), static_cast<int32>(Captured.KeyOwner.State), static_cast<int32>(EPointerRead::Resolved));
            TestEqual(TEXT("Exact template path"), Captured.ComponentTemplate.Path, Template->GetPathName());
            TestEqual(TEXT("Exact component class path"), Captured.ComponentClass.Path, USceneComponent::StaticClass()->GetPathName());
            TestTrue(TEXT("Visible captured, not missing"), Captured.TemplateVisible.IsSet());
            TestTrue(TEXT("Hidden captured, not missing"), Captured.TemplateHiddenInGame.IsSet());
            if (Captured.TemplateVisible.IsSet()) TestEqual(TEXT("Literal visible flag"), Captured.TemplateVisible.GetValue(), Visible);
            if (Captured.TemplateHiddenInGame.IsSet()) TestEqual(TEXT("Literal hidden flag"), Captured.TemplateHiddenInGame.GetValue(), !Visible);
        }
        TestTrue(TEXT("Reader preserves key GUID"), Record.ComponentKey.GetAssociatedGuid() == ExpectedGuid);
        TestEqual(TEXT("Reader preserves dirty bit"), Package->IsDirty(), DirtyBefore);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipOverrideNoHandlerFixture,
    "EngineWire.OwnershipOverrideFixtures.NoHandler",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipOverrideNoHandlerFixture::RunTest(const FString& Parameters)
{
    if (!PermitTransientFixtures(*this)) return false;
    TStrongObjectPtr<UPackage> Package;
    TStrongObjectPtr<UBlueprint> BP(MakeFixture(*this,
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/BP_OwnershipHead"), Package));
    if (!BP.IsValid()) return false;
    const FOverridesRead Read = ReadOwnOverrides(BP.Get());
    TestTrue(TEXT("No own handler is a valid partial read"), Read.bAccepted);
    TestFalse(TEXT("No own handler is not complete inherited inventory"), Read.bComplete);
    TestEqual(TEXT("Null handler distinguished from uncaptured"), static_cast<int32>(Read.Handler.State), static_cast<int32>(EPointerRead::Null));
    TestTrue(TEXT("No fabricated records"), Read.Records.IsEmpty());
    TestTrue(TEXT("Read did not create a handler"), BP->InheritableComponentHandler.IsResolved() && BP->InheritableComponentHandler.Get() == nullptr);
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipRawParentFixture,
    "EngineWire.OwnershipGraphFixtures.RawParentForms",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipRawParentFixture::RunTest(const FString& Parameters)
{
    if (!PermitTransientFixtures(*this)) return false;
    TStrongObjectPtr<UPackage> Package;
    TStrongObjectPtr<UBlueprint> BP(MakeFixture(*this,
        TEXT("/Game/BeholderPrototype/OwnershipIsolation/BP_OwnershipBodyFixture"), Package));
    if (!BP.IsValid()) return false;
    UEdGraph* Graph = NewObject<UEdGraph>(BP.Get(), TEXT("ParentFormsGraph"), RF_Transient);
    BP->FunctionGraphs.Add(Graph);
    UK2Node_VariableGet* Node = NewObject<UK2Node_VariableGet>(Graph, TEXT("ParentFormsNode"), RF_Transient);
    Graph->Nodes.Add(Node);
    const FGuid MemberGuid(13, 14, 15, 16);
    const FName MemberName(TEXT("SyntheticParentProbe"));

    for (int32 Form = 0; Form < 3; ++Form)
    {
        if (Form == 0) Node->VariableReference.SetSelfMember(MemberName, MemberGuid);
        else if (Form == 1) Node->VariableReference.SetExternalMember(MemberName, UBlueprint::StaticClass(), MemberGuid);
        else Node->VariableReference.SetGlobalField(MemberName, Package.Get());
        const bool DirtyBefore = Package->IsDirty();
        const FNodeRead Read = ReadNodeScalars(Node);
        TestTrue(TEXT("Parent form scalar read admitted"), Read.bAccepted);
        TestFalse(TEXT("Parent form does not make snapshot complete"), Read.bComplete);
        TestEqual(TEXT("One raw reference"), Read.Members.Num(), 1);
        if (Read.Members.Num() != 1) continue;
        const FMemberScalars& Member = Read.Members[0];
        TestEqual(TEXT("Name preserved"), Member.Name, MemberName);
        TestTrue(TEXT("GUID preserved across forms"), Member.MemberGuid == MemberGuid);
        TestEqual(TEXT("Self-context is stored, not inferred"), Member.bSelfContext, Form == 0);
        TestEqual(TEXT("Correct stored parent state"), static_cast<int32>(Member.RawParent.State),
            static_cast<int32>(Form == 0 ? EPointerRead::Null : EPointerRead::Resolved));
        const FString ExpectedPath = Form == 0 ? FString() :
            (Form == 1 ? UBlueprint::StaticClass()->GetPathName() : Package->GetPathName());
        TestEqual(TEXT("Exact raw class/package/null parent"), Member.RawParent.Path, ExpectedPath);
        TestTrue(TEXT("Deprecated scalar is captured"), Member.WasDeprecated.IsSet());
        if (Member.WasDeprecated.IsSet()) TestFalse(TEXT("Fixture reference is not deprecated"), Member.WasDeprecated.GetValue());
        for (const FReadGap& Gap : Read.Uncaptured)
            TestTrue(TEXT("Raw parent was captured, not silently omitted"), Gap.Field != TEXT("variable.raw_parent"));
        TestEqual(TEXT("Reader preserved source self-context"), Node->VariableReference.IsSelfContext(), Form == 0);
        TestTrue(TEXT("Reader preserved source GUID"), Node->VariableReference.GetMemberGuid() == MemberGuid);
        TestEqual(TEXT("Reader preserved dirty bit"), Package->IsDirty(), DirtyBefore);
    }
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipOverrideChainFixture,
    "EngineWire.OwnershipOverrideFixtures.ParentChain",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipOverrideChainFixture::RunTest(const FString& Parameters)
{
    if (!PermitTransientFixtures(*this)) return false;
    const FClassProperty* ParentProperty = FindFProperty<FClassProperty>(UBlueprint::StaticClass(), TEXT("ParentClass"));
    if (!ParentProperty || ParentProperty->ArrayDim != 1 || ParentProperty->HasGetter()
        || ParentProperty->PropertyClass != UClass::StaticClass())
    {
        AddError(TEXT("Unsupported fixture ParentClass storage layout"));
        return false;
    }
    // Validate layout before constructing or editing transient fixture objects.
    const FArrayProperty* Records = FindFProperty<FArrayProperty>(UInheritableComponentHandler::StaticClass(), TEXT("Records"));
    const FStructProperty* Inner = Records ? CastField<FStructProperty>(Records->Inner) : nullptr;
    const FObjectProperty* Owner = FindFProperty<FObjectProperty>(FComponentKey::StaticStruct(), TEXT("OwnerClass"));
    const FNameProperty* Name = FindFProperty<FNameProperty>(FComponentKey::StaticStruct(), TEXT("SCSVariableName"));
    const FStructProperty* Guid = FindFProperty<FStructProperty>(FComponentKey::StaticStruct(), TEXT("AssociatedGuid"));
    if (!Records || Records->ArrayDim != 1 || !Inner || Inner->Struct != FComponentOverrideRecord::StaticStruct()
        || !Owner || Owner->ArrayDim != 1 || Owner->HasSetter() || Owner->PropertyClass != UClass::StaticClass()
        || !Name || Name->ArrayDim != 1 || !Guid || Guid->ArrayDim != 1 || Guid->Struct != TBaseStructure<FGuid>::Get())
    {
        AddError(TEXT("Unsupported chain fixture record/key layout; refusing setup"));
        return false;
    }
    TStrongObjectPtr<UPackage> ChildPackage;
    TStrongObjectPtr<UPackage> ParentPackage;
    TStrongObjectPtr<UBlueprint> Child(MakeFixture(*this,
        TEXT("/Game/BeholderPrototype/Body/BP_BeholderBodyLeg"), ChildPackage));
    TStrongObjectPtr<UBlueprint> Parent(MakeFixture(*this,
        TEXT("/Game/BeholderPrototype/Telescopic/BP_BeholderTelescopic_Test"), ParentPackage));
    if (!Child.IsValid() || !Parent.IsValid()) return false;
    UBlueprintGeneratedClass* ParentClass = NewObject<UBlueprintGeneratedClass>(ParentPackage.Get(),
        TEXT("BP_BeholderTelescopic_Test_C"), RF_Transient);
    UBlueprintGeneratedClass* ChildClass = NewObject<UBlueprintGeneratedClass>(ChildPackage.Get(),
        TEXT("BP_BeholderBodyLeg_C"), RF_Transient);
    ChildClass->ClassGeneratedBy = Child.Get();
    Child->GeneratedClass = ChildClass;
    ParentClass->ClassGeneratedBy = Parent.Get();
    Parent->GeneratedClass = ParentClass;
    Child->ParentClass = ParentClass;
    Parent->ParentClass = UObject::StaticClass();

    const FGuid KeyGuid(21, 22, 23, 24);
    UBlueprint* Layers[] = {Child.Get(), Parent.Get()};
    UInheritableComponentHandler* Handlers[2] = {};
    USceneComponent* Templates[2] = {};
    for (int32 Layer = 0; Layer < 2; ++Layer)
    {
        Handlers[Layer] = NewObject<UInheritableComponentHandler>(Layers[Layer], TEXT("ChainHandler"), RF_Transient);
        Layers[Layer]->InheritableComponentHandler = Handlers[Layer];
        Templates[Layer] = NewObject<USceneComponent>(Handlers[Layer], TEXT("ChainTemplate"), RF_Transient | RF_ArchetypeObject);
        Templates[Layer]->SetVisibleFlag(Layer == 1);
        Templates[Layer]->bHiddenInGame = Layer == 0;
        auto* Storage = Records->ContainerPtrToValuePtr<TArray<FComponentOverrideRecord>>(Handlers[Layer]);
        FComponentOverrideRecord& Record = Storage->AddDefaulted_GetRef();
        Record.ComponentClass = USceneComponent::StaticClass();
        Record.ComponentTemplate = Templates[Layer];
        // Deliberately synthetic owner/key: no SCS declaration or effective-template query.
        Owner->SetObjectPropertyValue_InContainer(&Record.ComponentKey, UBlueprint::StaticClass());
        Name->SetPropertyValue(Name->ContainerPtrToValuePtr<void>(&Record.ComponentKey),
            FName(Layer == 0 ? TEXT("ChildAlias") : TEXT("ParentAlias")));
        *Guid->ContainerPtrToValuePtr<FGuid>(&Record.ComponentKey) = KeyGuid;
    }
    const bool ChildDirty = ChildPackage->IsDirty();
    const bool ParentDirty = ParentPackage->IsDirty();
    // TSubclassOf::Get performs IsChildOf and returns null for these intentionally
    // unlinked metadata classes. Compare stored wrappers, without altering hierarchy.
    const auto StoredParent = [ParentProperty](const UBlueprint* BP)
    {
        return ParentProperty->GetObjectPtrPropertyValue(
            ParentProperty->ContainerPtrToValuePtr<void>(static_cast<const void*>(BP)));
    };
    const TObjectPtr<UObject> ChildParentBefore = StoredParent(Child.Get());
    const TObjectPtr<UObject> ParentParentBefore = StoredParent(Parent.Get());
    if (!ChildParentBefore.IsResolved() || ChildParentBefore.Get() != ParentClass
        || !ParentParentBefore.IsResolved() || ParentParentBefore.Get() != UObject::StaticClass())
    {
        AddError(TEXT("Fixture raw parent links were not installed as intended before capture"));
        return false;
    }
    const FOverrideChainRead Chain = ReadOverrideChain(Child.Get());
    // Same metadata-only fixture: BP handler is populated, class-side handler is
    // deliberately absent. Reader must retain that difference, never create one.
    const FSCSOwnerRead OwnerRead = ReadSCSOwnerPointers(Child.Get());
    TestTrue(TEXT("Synthetic owner pointers admitted"), OwnerRead.bAccepted);
    TestFalse(TEXT("Synthetic owner pointers not full SCS capture"), OwnerRead.bComplete);
    TestEqual(TEXT("Exact owner BP path"), OwnerRead.BlueprintPath, Child->GetPathName());
    TestEqual(TEXT("Raw generated class captured without TSubclassOf Get"), OwnerRead.GeneratedClass.Path, ChildClass->GetPathName());
    TestEqual(TEXT("BP handler path preserved"), OwnerRead.BlueprintHandler.Path, Handlers[0]->GetPathName());
    TestEqual(TEXT("Absent class handler observed null"), static_cast<int32>(OwnerRead.ClassHandler.State), static_cast<int32>(EPointerRead::Null));
    TestEqual(TEXT("Exact generated-by provenance"), OwnerRead.ClassGeneratedBy.Path, Child->GetPathName());
    TestTrue(TEXT("SCS comparison captured even for two nulls"), OwnerRead.SameSCS.IsSet());
    if (OwnerRead.SameSCS.IsSet()) TestTrue(TEXT("Both raw SCS pointers null"), OwnerRead.SameSCS.GetValue());
    TestTrue(TEXT("Handler mismatch captured"), OwnerRead.SameHandler.IsSet());
    if (OwnerRead.SameHandler.IsSet()) TestFalse(TEXT("BP handler not inferred as class handler"), OwnerRead.SameHandler.GetValue());
    TestTrue(TEXT("Generated-by identity captured"), OwnerRead.ClassGeneratedByIsBlueprint.IsSet());
    if (OwnerRead.ClassGeneratedByIsBlueprint.IsSet()) TestTrue(TEXT("Class points to supplied BP"), OwnerRead.ClassGeneratedByIsBlueprint.GetValue());
    TestTrue(TEXT("Owner reader dirty-before present"), OwnerRead.PackageDirtyBefore.IsSet());
    TestTrue(TEXT("Owner reader dirty-after present"), OwnerRead.PackageDirtyAfter.IsSet());
    if (OwnerRead.PackageDirtyBefore.IsSet()) TestEqual(TEXT("Owner reader dirty-before value"), OwnerRead.PackageDirtyBefore.GetValue(), ChildDirty);
    if (OwnerRead.PackageDirtyAfter.IsSet()) TestEqual(TEXT("Owner reader dirty-after value"), OwnerRead.PackageDirtyAfter.GetValue(), ChildDirty);
    // Non-null pointer observations only. Construct synthetic SCS objects without
    // editing/traversing their registry, compiling a BP or querying actual templates.
    const FSCSOwnerSchema OwnerSchema = InspectSCSOwnerSchema();
    if (!OwnerSchema.IsSupported())
    {
        AddError(OwnerSchema.Error);
        return false;
    }
    USimpleConstructionScript* ClassSCS = NewObject<USimpleConstructionScript>(ChildClass, TEXT("OwnerClassSCS"), RF_Transient);
    USimpleConstructionScript* LegacySCS = NewObject<USimpleConstructionScript>(Child.Get(), TEXT("OwnerLegacySCS"), RF_Transient);
    const auto PutPointer = [](const FObjectProperty* Property, void* Container, UObject* Value)
    {
        Property->SetObjectPropertyValue_InContainer(Container, Value);
    };
    PutPointer(OwnerSchema.GeneratedClassSCS, ChildClass, ClassSCS);
    PutPointer(OwnerSchema.BlueprintSCS, Child.Get(), ClassSCS);
    PutPointer(OwnerSchema.GeneratedClassHandler, ChildClass, Handlers[0]);
    const bool OwnerFixtureDirty = ChildPackage->IsDirty();
    for (int32 Pass = 0; Pass < 2; ++Pass)
    {
        UObject* ExpectedBPSCS = Pass == 0 ? static_cast<UObject*>(ClassSCS) : static_cast<UObject*>(LegacySCS);
        UObject* ExpectedClassHandler = Pass == 0 ? static_cast<UObject*>(Handlers[0]) : static_cast<UObject*>(Handlers[1]);
        PutPointer(OwnerSchema.BlueprintSCS, Child.Get(), ExpectedBPSCS);
        // Pass1 deliberately records an external-package handler pointer; reader
        // observes identity/path only, never reads its payload or certifies ownership.
        PutPointer(OwnerSchema.GeneratedClassHandler, ChildClass, ExpectedClassHandler);
        const FSCSOwnerRead NonNull = ReadSCSOwnerPointers(Child.Get());
        TestTrue(TEXT("Non-null raw SCS pointers admitted"), NonNull.bAccepted);
        TestFalse(TEXT("Non-null raw SCS is not inventory completeness"), NonNull.bComplete);
        TestEqual(TEXT("Exact non-null BP SCS path"), NonNull.BlueprintSCS.Path, ExpectedBPSCS->GetPathName());
        TestEqual(TEXT("Exact non-null class SCS path"), NonNull.ClassSCS.Path, ClassSCS->GetPathName());
        TestEqual(TEXT("Non-null BP SCS resolved"), static_cast<int32>(NonNull.BlueprintSCS.State), static_cast<int32>(EPointerRead::Resolved));
        TestEqual(TEXT("Non-null class SCS resolved"), static_cast<int32>(NonNull.ClassSCS.State), static_cast<int32>(EPointerRead::Resolved));
        TestTrue(TEXT("Non-null SCS comparison present"), NonNull.SameSCS.IsSet());
        if (NonNull.SameSCS.IsSet()) TestEqual(TEXT("SCS identity not inferred from package"), NonNull.SameSCS.GetValue(), Pass == 0);
        TestEqual(TEXT("Exact class handler path"), NonNull.ClassHandler.Path, ExpectedClassHandler->GetPathName());
        TestTrue(TEXT("Non-null handler comparison present"), NonNull.SameHandler.IsSet());
        if (NonNull.SameHandler.IsSet()) TestEqual(TEXT("Handler identity comparison"), NonNull.SameHandler.GetValue(), Pass == 0);
        TestTrue(TEXT("Owner read does not rewrite BP SCS"), OwnerSchema.BlueprintSCS->GetObjectPtrPropertyValue(
            OwnerSchema.BlueprintSCS->ContainerPtrToValuePtr<void>(Child.Get())).Get() == ExpectedBPSCS);
        TestTrue(TEXT("Owner read does not rewrite class handler"), OwnerSchema.GeneratedClassHandler->GetObjectPtrPropertyValue(
            OwnerSchema.GeneratedClassHandler->ContainerPtrToValuePtr<void>(ChildClass)).Get() == ExpectedClassHandler);
        TestEqual(TEXT("Owner observation preserves fixture dirty"), ChildPackage->IsDirty(), OwnerFixtureDirty);
    }
    const FSCSListSchema ListSchema = InspectSCSListSchema();
    if (!ListSchema.IsSupported()) { AddError(ListSchema.Error); return false; }
    // ONLY transient test setup uses mutable raw arrays. Production reader does
    // not call AddNode/GetAllNodes or repair the deliberately divergent registry.
    auto* Roots = ListSchema.Roots->ContainerPtrToValuePtr<TArray<TObjectPtr<USCS_Node>>>(ClassSCS);
    auto* Registry = ListSchema.Registry->ContainerPtrToValuePtr<TArray<TObjectPtr<USCS_Node>>>(ClassSCS);
    const TArray<TObjectPtr<USCS_Node>> OriginalRoots = *Roots;
    const TArray<TObjectPtr<USCS_Node>> OriginalRegistry = *Registry;
    USCS_Node* RootOnly = NewObject<USCS_Node>(ClassSCS, TEXT("RawRootOnly"), RF_Transient);
    USCS_Node* RegistryOnly = NewObject<USCS_Node>(ClassSCS, TEXT("RawRegistryOnly"), RF_Transient);
    USCS_Node* Foreign = NewObject<USCS_Node>(LegacySCS, TEXT("RawWrongOuter"), RF_Transient);
    *Roots = {RootOnly, nullptr, RootOnly};
    *Registry = {RegistryOnly, RootOnly};
    const bool ListDirty = ChildPackage->IsDirty();
    const FSCSListsRead RawLists = ReadSCSRawLists(Child.Get(), ClassSCS);
    TestTrue(TEXT("Divergent raw lists admitted as evidence"), RawLists.bAccepted);
    TestFalse(TEXT("Raw lists not full inventory"), RawLists.bComplete);
    TestEqual(TEXT("Explicit SCS path"), RawLists.SCSPath, ClassSCS->GetPathName());
    TestEqual(TEXT("Duplicate/null roots retained"), RawLists.Roots.Num(), 3);
    TestEqual(TEXT("Separate registry count"), RawLists.Registry.Num(), 2);
    if (RawLists.Roots.Num() == 3 && RawLists.Registry.Num() == 2)
    {
        for (int32 Index = 0; Index < 3; ++Index) TestEqual(TEXT("Root source index"), RawLists.Roots[Index].Index, Index);
        TestEqual(TEXT("First root exact path"), RawLists.Roots[0].Target.Path, RootOnly->GetPathName());
        TestEqual(TEXT("Duplicate root exact path"), RawLists.Roots[2].Target.Path, RootOnly->GetPathName());
        TestEqual(TEXT("Null entry explicit"), static_cast<int32>(RawLists.Roots[1].Target.State), static_cast<int32>(EPointerRead::Null));
        TestEqual(TEXT("Registry-only entry exact path"), RawLists.Registry[0].Target.Path, RegistryOnly->GetPathName());
        TestEqual(TEXT("Registry source index"), RawLists.Registry[1].Index, 1);
    }
    TestEqual(TEXT("Reader did not rebuild roots"), Roots->Num(), 3);
    TestEqual(TEXT("Reader did not populate divergent registry"), Registry->Num(), 2);
    const FSCSNodeSchema NodeSchema = InspectSCSNodeSchema();
    if (!NodeSchema.IsSupported()) { AddError(NodeSchema.Error); return false; }
    const FGuid RawNodeGuid(31, 32, 33, 34);
    *NodeSchema.VariableGuid->ContainerPtrToValuePtr<FGuid>(RootOnly) = RawNodeGuid;
    NodeSchema.VariableName->SetPropertyValue(NodeSchema.VariableName->ContainerPtrToValuePtr<void>(RootOnly), FName(TEXT("RawSocketHousing")));
    NodeSchema.AttachToName->SetPropertyValue(NodeSchema.AttachToName->ContainerPtrToValuePtr<void>(RootOnly), FName(TEXT("RawEyeTip")));
    NodeSchema.ParentName->SetPropertyValue(NodeSchema.ParentName->ContainerPtrToValuePtr<void>(RootOnly), FName(TEXT("RawParentComponent")));
    NodeSchema.ParentOwnerClassName->SetPropertyValue(NodeSchema.ParentOwnerClassName->ContainerPtrToValuePtr<void>(RootOnly), FName(TEXT("RawParentOwner")));
    PutPointer(NodeSchema.ComponentClass, RootOnly, USceneComponent::StaticClass());
    PutPointer(NodeSchema.ComponentTemplate, RootOnly, Templates[0]);
    for (int32 Pass = 0; Pass < 2; ++Pass)
    {
        NodeSchema.IsParentNative->SetPropertyValue(NodeSchema.IsParentNative->ContainerPtrToValuePtr<void>(RootOnly), Pass == 1);
        const FSCSNodeRead Payload = ReadSCSNodePayload(Child.Get(), ClassSCS, RootOnly);
        TestTrue(TEXT("Raw root-member payload admitted"), Payload.bAccepted);
        TestFalse(TEXT("Raw payload incomplete"), Payload.bComplete);
        TestEqual(TEXT("Exact node identity"), Payload.Node.NodePath, RootOnly->GetPathName());
        TestEqual(TEXT("Exact SCS outer provenance"), Payload.Node.Outer.Path, ClassSCS->GetPathName());
        TestTrue(TEXT("Raw GUID not declaration-resolved"), Payload.Node.VariableGuid == RawNodeGuid);
        TestEqual(TEXT("Raw variable name"), Payload.Node.VariableName, FName(TEXT("RawSocketHousing")));
        TestEqual(TEXT("Raw attach socket"), Payload.Node.AttachToName, FName(TEXT("RawEyeTip")));
        TestEqual(TEXT("Raw parent label"), Payload.Node.ParentComponentOrVariableName, FName(TEXT("RawParentComponent")));
        TestEqual(TEXT("Raw parent-owner label"), Payload.Node.ParentComponentOwnerClassName, FName(TEXT("RawParentOwner")));
        TestTrue(TEXT("Native-parent flag observed"), Payload.Node.IsParentComponentNative.IsSet());
        if (Payload.Node.IsParentComponentNative.IsSet()) TestEqual(TEXT("Literal native-parent bool"), Payload.Node.IsParentComponentNative.GetValue(), Pass == 1);
        TestEqual(TEXT("Exact class pointer path"), Payload.Node.ComponentClass.Path, USceneComponent::StaticClass()->GetPathName());
        TestEqual(TEXT("Exact template pointer path without payload read"), Payload.Node.ComponentTemplate.Path, Templates[0]->GetPathName());
        TestFalse(TEXT("Scene flags deliberately uncaptured"), Payload.Node.TemplateVisible.IsSet());
        TestFalse(TEXT("Hidden flag deliberately uncaptured"), Payload.Node.TemplateHiddenInGame.IsSet());
        TestEqual(TEXT("No invented traversal depth"), Payload.Node.DiscoveryDepth, INDEX_NONE);
        TestTrue(TEXT("Raw GUID preserved by reader"), *NodeSchema.VariableGuid->ContainerPtrToValuePtr<FGuid>(RootOnly) == RawNodeGuid);
        TestEqual(TEXT("Raw lists preserved by payload reader"), Roots->Num(), 3);
        TestEqual(TEXT("Node read preserves dirty"), ChildPackage->IsDirty(), ListDirty);
    }
    const FSCSNodeRead RegistryPayload = ReadSCSNodePayload(Child.Get(), ClassSCS, RegistryOnly);
    TestTrue(TEXT("Registry-only membership admitted"), RegistryPayload.bAccepted);
    USCS_Node* Unlisted = NewObject<USCS_Node>(ClassSCS, TEXT("RawUnlisted"), RF_Transient);
    const FSCSNodeRead MissingNode = ReadSCSNodePayload(Child.Get(), ClassSCS, Unlisted);
    TestFalse(TEXT("Same outer without list membership refused"), MissingNode.bAccepted);
    TestEqual(TEXT("Missing membership refusal reason"), MissingNode.Error, FString(TEXT("SCS node absent from admitted raw roots/registry")));
    const FSCSNodeRead ForeignNode = ReadSCSNodePayload(Child.Get(), ClassSCS, Foreign);
    TestFalse(TEXT("Wrong node outer refused before payload"), ForeignNode.bAccepted);
    TestTrue(TEXT("Wrong outer has no captured node payload"), ForeignNode.Node.NodePath.IsEmpty());
    TestEqual(TEXT("Wrong node outer reason"), ForeignNode.Error, FString(TEXT("Live SCS node with exact supplied SCS outer required")));
    auto* ChildEdges = ListSchema.Children->ContainerPtrToValuePtr<TArray<TObjectPtr<USCS_Node>>>(RootOnly);
    const TArray<TObjectPtr<USCS_Node>> OriginalChildEdges = *ChildEdges;
    // Unlisted is deliberately child-only; observing an edge must not promote it
    // into roots/registry or authorize reading its payload as an admitted parent.
    *ChildEdges = {Unlisted, nullptr, Unlisted, RootOnly};
    const bool ChildrenDirty = ChildPackage->IsDirty();
    const FSCSChildrenRead Edges = ReadSCSChildPointers(Child.Get(), ClassSCS, RootOnly);
    TestTrue(TEXT("Ordered child edges admitted without traversal"), Edges.bAccepted);
    TestFalse(TEXT("Child edges not complete inventory"), Edges.bComplete);
    TestEqual(TEXT("Exact child edge source path"), Edges.SourceNodePath, RootOnly->GetPathName());
    TestEqual(TEXT("Child-only/null/duplicate/self entries retained"), Edges.Children.Num(), 4);
    if (Edges.Children.Num() == 4)
    {
        for (int32 Index = 0; Index < 4; ++Index) TestEqual(TEXT("Child source index"), Edges.Children[Index].Index, Index);
        TestEqual(TEXT("Child-only target exact path"), Edges.Children[0].Target.Path, Unlisted->GetPathName());
        TestEqual(TEXT("Duplicate child exact path"), Edges.Children[2].Target.Path, Unlisted->GetPathName());
        TestEqual(TEXT("Self-link exact path"), Edges.Children[3].Target.Path, RootOnly->GetPathName());
        TestEqual(TEXT("Null child explicit"), static_cast<int32>(Edges.Children[1].Target.State), static_cast<int32>(EPointerRead::Null));
    }
    const FSCSChildrenRead ChildOnlyParent = ReadSCSChildPointers(Child.Get(), ClassSCS, Unlisted);
    TestFalse(TEXT("Edge observation does not admit child-only parent"), ChildOnlyParent.bAccepted);
    TestTrue(TEXT("Child-only parent captures no outgoing edges"), ChildOnlyParent.Children.IsEmpty());
    TestEqual(TEXT("Child-only membership refusal"), ChildOnlyParent.Error, FString(TEXT("SCS node absent from admitted raw roots/registry")));
    ChildEdges->Add(Foreign);
    const FSCSChildrenRead ForeignEdge = ReadSCSChildPointers(Child.Get(), ClassSCS, RootOnly);
    TestFalse(TEXT("Wrong-outer child target refused"), ForeignEdge.bAccepted);
    TestEqual(TEXT("Wrong child outer error"), ForeignEdge.Error, FString(TEXT("Unresolved, invalid or wrong-outer SCS child target")));
    TestEqual(TEXT("Refused prefix includes offending edge"), ForeignEdge.Children.Num(), 5);
    if (ForeignEdge.Children.Num() == 5) TestEqual(TEXT("Offending child provenance"), ForeignEdge.Children[4].Target.Path, Foreign->GetPathName());
    ChildEdges->Init(Unlisted, 256);
    const FSCSChildrenRead ChildrenAtLimit = ReadSCSChildPointers(Child.Get(), ClassSCS, RootOnly);
    TestTrue(TEXT("256 child entries admitted"), ChildrenAtLimit.bAccepted);
    TestEqual(TEXT("256 child entries not deduplicated"), ChildrenAtLimit.Children.Num(), 256);
    ChildEdges->Add(Unlisted);
    const FSCSChildrenRead ChildrenOverLimit = ReadSCSChildPointers(Child.Get(), ClassSCS, RootOnly);
    TestFalse(TEXT("257 child entries refused before copying"), ChildrenOverLimit.bAccepted);
    TestTrue(TEXT("No over-limit child edges retained"), ChildrenOverLimit.Children.IsEmpty());
    TestEqual(TEXT("Child count budget reason"), ChildrenOverLimit.Error, FString(TEXT("SCS child entry limit exceeded before copying")));
    TestEqual(TEXT("Reader preserved oversized child input"), ChildEdges->Num(), 257);
    TestEqual(TEXT("Children reader preserves dirty state"), ChildPackage->IsDirty(), ChildrenDirty);
    TestEqual(TEXT("Children reader does not populate registry"), Registry->Num(), 2);
    *ChildEdges = OriginalChildEdges;
    Registry->Add(Foreign);
    const FSCSListsRead WrongOuter = ReadSCSRawLists(Child.Get(), ClassSCS);
    TestFalse(TEXT("Wrong-outer entry refused"), WrongOuter.bAccepted);
    TestEqual(TEXT("Wrong-outer refusal reason"), WrongOuter.Error, FString(TEXT("Unresolved, invalid or wrong-outer SCS list entry")));
    Registry->Reset();
    Roots->Init(RootOnly, 128);
    const FSCSListsRead AtLimit = ReadSCSRawLists(Child.Get(), ClassSCS);
    TestTrue(TEXT("128 root entries admitted"), AtLimit.bAccepted);
    TestEqual(TEXT("128 root entries retained without deduplication"), AtLimit.Roots.Num(), 128);
    Roots->Add(RootOnly);
    const FSCSListsRead OverLimit = ReadSCSRawLists(Child.Get(), ClassSCS);
    TestFalse(TEXT("129 root entries refused"), OverLimit.bAccepted);
    TestTrue(TEXT("Over-limit lists not copied"), OverLimit.Roots.IsEmpty() && OverLimit.Registry.IsEmpty());
    TestEqual(TEXT("List count limit reason"), OverLimit.Error, FString(TEXT("SCS raw list entry limit exceeded before copying")));
    TestEqual(TEXT("Reader preserves oversized input count"), Roots->Num(), 129);
    TestEqual(TEXT("List reads preserved dirty state"), ChildPackage->IsDirty(), ListDirty);
    *Roots = OriginalRoots;
    *Registry = OriginalRegistry;
    // Restore only synthetic setup fields explicitly changed above. No asset Save.
    PutPointer(OwnerSchema.BlueprintSCS, Child.Get(), nullptr);
    PutPointer(OwnerSchema.GeneratedClassSCS, ChildClass, nullptr);
    PutPointer(OwnerSchema.GeneratedClassHandler, ChildClass, nullptr);
    TestTrue(TEXT("Record-bearing chain admitted"), Chain.bAccepted);
    TestFalse(TEXT("Record-bearing chain is not complete capture"), Chain.bComplete);
    TestEqual(TEXT("Record-bearing native terminal"), static_cast<int32>(Chain.Stop), static_cast<int32>(EChainStop::NativeTerminal));
    TestEqual(TEXT("Two record-bearing layers"), Chain.Layers.Num(), 2);
    if (Chain.Layers.Num() != 2) return false;
    TestEqual(TEXT("Exact parent class provenance"), Chain.Layers[0].ParentClass.Path, ParentClass->GetPathName());
    TestEqual(TEXT("Exact generated-by provenance"), Chain.Layers[0].ClassGeneratedBy.Path, Parent->GetPathName());
    TestEqual(TEXT("Terminal native class path"), Chain.Layers[1].ParentClass.Path, UObject::StaticClass()->GetPathName());
    TestEqual(TEXT("Native generated-by is null"), static_cast<int32>(Chain.Layers[1].ClassGeneratedBy.State), static_cast<int32>(EPointerRead::Null));
    TestTrue(TEXT("Child dirty rechecked"), Chain.Layers[0].PackageDirtyAfter.IsSet());
    TestTrue(TEXT("Parent dirty rechecked"), Chain.Layers[1].PackageDirtyAfter.IsSet());
    for (int32 Layer = 0; Layer < 2; ++Layer)
    {
        const FOverridesRead& Own = Chain.Layers[Layer].Own;
        TestEqual(TEXT("Layer owner provenance"), Own.OwnerPath, Layers[Layer]->GetPathName());
        TestEqual(TEXT("Layer handler provenance"), Own.Handler.Path, Handlers[Layer]->GetPathName());
        TestEqual(TEXT("One record per layer"), Own.Records.Num(), 1);
        if (Own.Records.Num() != 1) return false;
        const FOverrideRead& Record = Own.Records[0];
        TestEqual(TEXT("Layer-specific template provenance"), Record.ComponentTemplate.Path, Templates[Layer]->GetPathName());
        TestTrue(TEXT("Shared key GUID captured"), Record.AssociatedGuid == KeyGuid);
        TestEqual(TEXT("Shared stored key owner"), Record.KeyOwner.Path, UBlueprint::StaticClass()->GetPathName());
        TestEqual(TEXT("Different raw names retained"), Record.VariableName, FName(Layer == 0 ? TEXT("ChildAlias") : TEXT("ParentAlias")));
        TestTrue(TEXT("Visible flag present"), Record.TemplateVisible.IsSet());
        TestTrue(TEXT("Hidden flag present"), Record.TemplateHiddenInGame.IsSet());
        if (Record.TemplateVisible.IsSet()) TestEqual(TEXT("Layer visible flag"), Record.TemplateVisible.GetValue(), Layer == 1);
        if (Record.TemplateHiddenInGame.IsSet()) TestEqual(TEXT("Layer hidden flag"), Record.TemplateHiddenInGame.GetValue(), Layer == 0);
    }
    const FOverridePathReview Review = ReviewOverridePathCandidates(Chain);
    TestTrue(TEXT("Captured chain DTO review admitted"), Review.bReviewed);
    TestFalse(TEXT("No live identity certification"), Review.bEngineIdentityVerified);
    TestFalse(TEXT("No effective-template completeness"), Review.bComplete);
    TestEqual(TEXT("Names do not split shared path-key"), Review.Groups.Num(), 1);
    if (Review.Groups.Num() == 1)
    {
        const FOverridePathKeyGroup& Group = Review.Groups[0];
        TestFalse(TEXT("Different layers are not same-layer duplicates"), Group.bSameLayerConflict);
        TestEqual(TEXT("Both sources preserved"), Group.Sources.Num(), 2);
        if (Group.Sources.Num() == 2)
        {
            TestEqual(TEXT("Nearest source layer"), Group.Sources[0].Layer, 0);
            TestEqual(TEXT("Ancestor source layer"), Group.Sources[1].Layer, 1);
            TestEqual(TEXT("Nearest source record"), Group.Sources[0].Record, 0);
            TestEqual(TEXT("Ancestor source record"), Group.Sources[1].Record, 0);
        }
        TestEqual(TEXT("Snapshot candidate is child, not effective template certification"), Group.Candidate.Layer, 0);
        TestEqual(TEXT("Snapshot candidate record"), Group.Candidate.Record, 0);
    }
    TestEqual(TEXT("Child package dirty unchanged by readers"), ChildPackage->IsDirty(), ChildDirty);
    TestEqual(TEXT("Parent package dirty unchanged by readers"), ParentPackage->IsDirty(), ParentDirty);
    const TObjectPtr<UObject> ChildParentAfter = StoredParent(Child.Get());
    const TObjectPtr<UObject> ParentParentAfter = StoredParent(Parent.Get());
    TestTrue(TEXT("Child raw parent link preserved"), ChildParentAfter.IsResolved() && ChildParentAfter.Get() == ChildParentBefore.Get());
    TestTrue(TEXT("Parent raw native link preserved"), ParentParentAfter.IsResolved() && ParentParentAfter.Get() == ParentParentBefore.Get());
    Parent->ParentClass = nullptr;
    const FOverrideChainRead Missing = ReadOverrideChain(Child.Get());
    TestFalse(TEXT("Missing parent is not a native terminal"), Missing.bAccepted);
    TestFalse(TEXT("Missing parent cannot be complete"), Missing.bComplete);
    TestEqual(TEXT("Null-parent stop distinguished"), static_cast<int32>(Missing.Stop), static_cast<int32>(EChainStop::NullParent));
    TestFalse(TEXT("Refused null-ended chain cannot be reviewed"), ReviewOverridePathCandidates(Missing).bReviewed);
    Parent->ParentClass = ChildClass;
    const FOverrideChainRead Cycle = ReadOverrideChain(Child.Get());
    TestFalse(TEXT("Cycle refused"), Cycle.bAccepted);
    TestFalse(TEXT("Cycle cannot be complete"), Cycle.bComplete);
    TestEqual(TEXT("Cycle stop distinguished from depth limit"), static_cast<int32>(Cycle.Stop), static_cast<int32>(EChainStop::Cycle));
    TestEqual(TEXT("Cycle does not duplicate child layer"), Cycle.Layers.Num(), 2);
    TestFalse(TEXT("Refused cyclic chain cannot be reviewed"), ReviewOverridePathCandidates(Cycle).bReviewed);
    TestEqual(TEXT("Reader preserved child dirty after refusals"), ChildPackage->IsDirty(), ChildDirty);
    TestEqual(TEXT("Reader preserved parent dirty after refusals"), ParentPackage->IsDirty(), ParentDirty);
    return true;
}
#endif
