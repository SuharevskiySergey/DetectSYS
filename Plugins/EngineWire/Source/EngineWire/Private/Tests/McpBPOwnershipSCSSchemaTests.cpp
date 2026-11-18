#include "Domains/Blueprint/Queries/McpBPOwnershipSCSSchema.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSInventory.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Async/Async.h"
#include "Misc/AutomationTest.h"

namespace
{
using namespace McpBPOwnershipBindingReader;

struct FSCSAllSchemas
{
    FSCSListSchema Lists;
    FSCSNodeSchema Node;
    FSCSOwnerSchema Owner;
};

void CheckNoDescriptors(FAutomationTestBase& Test, const FSCSAllSchemas& Schema)
{
    Test.TestTrue(TEXT("No list descriptors"), !Schema.Lists.Roots && !Schema.Lists.Registry && !Schema.Lists.Children);
    Test.TestTrue(TEXT("No node descriptors"), !Schema.Node.ComponentClass && !Schema.Node.ComponentTemplate
        && !Schema.Node.VariableGuid && !Schema.Node.VariableName && !Schema.Node.AttachToName
        && !Schema.Node.ParentName && !Schema.Node.ParentOwnerClassName && !Schema.Node.IsParentNative);
    Test.TestTrue(TEXT("No owner descriptors"), !Schema.Owner.BlueprintGeneratedClass && !Schema.Owner.BlueprintSCS
        && !Schema.Owner.BlueprintHandler && !Schema.Owner.GeneratedClassSCS && !Schema.Owner.GeneratedClassHandler);
    Test.TestFalse(TEXT("List schema not admitted"), Schema.Lists.IsSupported());
    Test.TestFalse(TEXT("Node schema not admitted"), Schema.Node.IsSupported());
    Test.TestFalse(TEXT("Owner schema not admitted"), Schema.Owner.IsSupported());
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSSchemaDefaults,
    "EngineWire.OwnershipSCSSchema.Defaults",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSSchemaDefaults::RunTest(const FString& Parameters)
{
    const FSCSAllSchemas Schema;
    CheckNoDescriptors(*this, Schema);
    TestTrue(TEXT("Default schemas have no fabricated error"), Schema.Lists.Error.IsEmpty()
        && Schema.Node.Error.IsEmpty() && Schema.Owner.Error.IsEmpty());
    const FSCSInventory Inventory;
    TestFalse(TEXT("Default inventory not admitted"), Inventory.bAccepted);
    TestFalse(TEXT("Default inventory incomplete"), Inventory.bComplete);
    TestFalse(TEXT("Default inventory not engine-verified"), Inventory.bEngineIdentityVerified);
    TestEqual(TEXT("Default stop is not null-SCS success"), static_cast<int32>(Inventory.Stop), static_cast<int32>(ESCSInventoryStop::NotStarted));
    TestEqual(TEXT("Default outer not inferred"), static_cast<int32>(Inventory.OuterForm), static_cast<int32>(ESCSOuterForm::NotCaptured));
    TestEqual(TEXT("Default SCS not observed null"), static_cast<int32>(Inventory.BlueprintSCS.State), static_cast<int32>(EPointerRead::NotCaptured));
    TestTrue(TEXT("Default lists and payloads empty"), Inventory.Roots.IsEmpty() && Inventory.Registry.IsEmpty()
        && Inventory.Nodes.IsEmpty() && Inventory.ChildEdges.IsEmpty());
    TestFalse(TEXT("Dirty-before not observed false"), Inventory.PackageDirtyBefore.IsSet());
    TestFalse(TEXT("Dirty-after not observed false"), Inventory.PackageDirtyAfter.IsSet());
    const FSCSNodeInventory Node;
    TestFalse(TEXT("Visible missing, not false"), Node.TemplateVisible.IsSet());
    TestFalse(TEXT("Hidden missing, not false"), Node.TemplateHiddenInGame.IsSet());
    TestFalse(TEXT("Native-parent flag missing, not false"), Node.IsParentComponentNative.IsSet());
    TestEqual(TEXT("Discovery depth absent"), Node.DiscoveryDepth, INDEX_NONE);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSSchemaNativeLayout,
    "EngineWire.OwnershipSCSSchema.NativeLayout",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSSchemaNativeLayout::RunTest(const FString& Parameters)
{
    if (!IsInGameThread())
    {
        AddError(TEXT("Native layout test requires game thread"));
        return false;
    }
    // Metadata only: no SCS instance, asset loading, compiler or template getter.
    const FSCSListSchema Lists = InspectSCSListSchema();
    const FSCSNodeSchema Node = InspectSCSNodeSchema();
    const FSCSOwnerSchema Owner = InspectSCSOwnerSchema();
    TestTrue(FString::Printf(TEXT("Native list layout supported: %s"), *Lists.Error), Lists.IsSupported());
    TestTrue(FString::Printf(TEXT("Native node layout supported: %s"), *Node.Error), Node.IsSupported());
    TestTrue(FString::Printf(TEXT("Native owner layout supported: %s"), *Owner.Error), Owner.IsSupported());
    TestTrue(TEXT("Successful layout checks have no error"), Lists.Error.IsEmpty() && Node.Error.IsEmpty() && Owner.Error.IsEmpty());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSSchemaWrongThread,
    "EngineWire.OwnershipSCSSchema.WrongThread",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSSchemaWrongThread::RunTest(const FString& Parameters)
{
    if (!GThreadPool)
    {
        AddError(TEXT("Existing engine thread pool required"));
        return false;
    }
    auto Future = Async(EAsyncExecution::ThreadPool, []()
    {
        FSCSAllSchemas Schema;
        Schema.Lists = InspectSCSListSchema();
        Schema.Node = InspectSCSNodeSchema();
        Schema.Owner = InspectSCSOwnerSchema();
        return Schema;
    });
    const FSCSAllSchemas Schema = Future.Get();
    CheckNoDescriptors(*this, Schema);
    TestEqual(TEXT("Worker list refusal"), Schema.Lists.Error, FString(TEXT("SCS list schema inspection requires game thread")));
    TestEqual(TEXT("Worker node refusal"), Schema.Node.Error, FString(TEXT("SCS node schema inspection requires game thread")));
    TestEqual(TEXT("Worker owner refusal"), Schema.Owner.Error, FString(TEXT("SCS owner schema inspection requires game thread")));
    return true;
}
#endif
