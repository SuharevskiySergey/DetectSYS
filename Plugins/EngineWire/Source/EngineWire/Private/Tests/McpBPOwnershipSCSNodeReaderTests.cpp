#include "Domains/Blueprint/Queries/McpBPOwnershipSCSNodeReader.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Async/Async.h"
#include "Misc/AutomationTest.h"

namespace
{
using namespace McpBPOwnershipBindingReader;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSNodeDefaults,
    "EngineWire.OwnershipSCSNodeReader.Defaults",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSNodeDefaults::RunTest(const FString& Parameters)
{
    const FSCSNodeRead Read;
    TestFalse(TEXT("Default not admitted"), Read.bAccepted);
    TestFalse(TEXT("Default incomplete"), Read.bComplete);
    TestTrue(TEXT("Default identity/error absent"), Read.Node.NodePath.IsEmpty() && Read.Error.IsEmpty());
    TestFalse(TEXT("Default GUID not fabricated"), Read.Node.VariableGuid.IsValid());
    TestTrue(TEXT("Default name absent"), Read.Node.VariableName.IsNone());
    TestEqual(TEXT("Default template unknown"), static_cast<int32>(Read.Node.ComponentTemplate.State), static_cast<int32>(EPointerRead::NotCaptured));
    TestFalse(TEXT("Default native-parent flag unknown"), Read.Node.IsParentComponentNative.IsSet());
    TestFalse(TEXT("Default scene visibility unknown"), Read.Node.TemplateVisible.IsSet());
    TestFalse(TEXT("Default scene hidden unknown"), Read.Node.TemplateHiddenInGame.IsSet());
    TestFalse(TEXT("Default dirty-before unknown"), Read.PackageDirtyBefore.IsSet());
    TestFalse(TEXT("Default dirty-after unknown"), Read.PackageDirtyAfter.IsSet());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSNodeNull,
    "EngineWire.OwnershipSCSNodeReader.NullInputs",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSNodeNull::RunTest(const FString& Parameters)
{
    const FSCSNodeRead Read = ReadSCSNodePayload(nullptr, nullptr, nullptr);
    TestFalse(TEXT("Null refused"), Read.bAccepted);
    TestFalse(TEXT("Null incomplete"), Read.bComplete);
    TestEqual(TEXT("Owner refusal before node access"), Read.Error,
        FString(TEXT("Idle game-thread editor and exact allowlisted SCS Blueprint required")));
    TestTrue(TEXT("No node payload captured"), Read.Node.NodePath.IsEmpty());
    TestFalse(TEXT("No dirty observation"), Read.PackageDirtyBefore.IsSet());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSNodeWrongThread,
    "EngineWire.OwnershipSCSNodeReader.WrongThread",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSNodeWrongThread::RunTest(const FString& Parameters)
{
    if (!GThreadPool) { AddError(TEXT("Existing engine thread pool required")); return false; }
    auto Future = Async(EAsyncExecution::ThreadPool, []() { return ReadSCSNodePayload(nullptr, nullptr, nullptr); });
    const FSCSNodeRead Read = Future.Get();
    TestFalse(TEXT("Worker refused"), Read.bAccepted);
    TestFalse(TEXT("Worker incomplete"), Read.bComplete);
    TestEqual(TEXT("Worker owner gate before schema/object access"), Read.Error,
        FString(TEXT("Idle game-thread editor and exact allowlisted SCS Blueprint required")));
    TestTrue(TEXT("No worker node identity"), Read.Node.NodePath.IsEmpty());
    TestFalse(TEXT("No worker native flag"), Read.Node.IsParentComponentNative.IsSet());
    return true;
}
#endif
