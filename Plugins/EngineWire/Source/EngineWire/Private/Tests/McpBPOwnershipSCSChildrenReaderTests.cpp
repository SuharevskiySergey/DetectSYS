#include "Domains/Blueprint/Queries/McpBPOwnershipSCSChildrenReader.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Async/Async.h"
#include "Misc/AutomationTest.h"

namespace
{
using namespace McpBPOwnershipBindingReader;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSChildrenDefaults,
    "EngineWire.OwnershipSCSChildrenReader.Defaults",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSChildrenDefaults::RunTest(const FString& Parameters)
{
    const FSCSChildrenRead Read;
    TestFalse(TEXT("Default not admitted"), Read.bAccepted);
    TestFalse(TEXT("Default incomplete"), Read.bComplete);
    TestTrue(TEXT("Default edges/source absent"), Read.Children.IsEmpty() && Read.SourceNodePath.IsEmpty());
    TestTrue(TEXT("Default error absent"), Read.Error.IsEmpty());
    TestFalse(TEXT("Dirty-before unknown"), Read.PackageDirtyBefore.IsSet());
    TestFalse(TEXT("Dirty-after unknown"), Read.PackageDirtyAfter.IsSet());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSChildrenNull,
    "EngineWire.OwnershipSCSChildrenReader.NullInputs",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSChildrenNull::RunTest(const FString& Parameters)
{
    const FSCSChildrenRead Read = ReadSCSChildPointers(nullptr, nullptr, nullptr);
    TestFalse(TEXT("Null refused"), Read.bAccepted);
    TestFalse(TEXT("Null incomplete"), Read.bComplete);
    TestEqual(TEXT("Owner refusal before child array access"), Read.Error,
        FString(TEXT("Idle game-thread editor and exact allowlisted SCS Blueprint required")));
    TestTrue(TEXT("Null input captures no edges"), Read.Children.IsEmpty());
    TestFalse(TEXT("No dirty-before read"), Read.PackageDirtyBefore.IsSet());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSChildrenWrongThread,
    "EngineWire.OwnershipSCSChildrenReader.WrongThread",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSChildrenWrongThread::RunTest(const FString& Parameters)
{
    if (!GThreadPool) { AddError(TEXT("Existing engine thread pool required")); return false; }
    auto Future = Async(EAsyncExecution::ThreadPool, []() { return ReadSCSChildPointers(nullptr, nullptr, nullptr); });
    const FSCSChildrenRead Read = Future.Get();
    TestFalse(TEXT("Worker refused"), Read.bAccepted);
    TestFalse(TEXT("Worker incomplete"), Read.bComplete);
    TestEqual(TEXT("Worker admission refusal"), Read.Error,
        FString(TEXT("Idle game-thread editor and exact allowlisted SCS Blueprint required")));
    TestTrue(TEXT("No worker child edges"), Read.Children.IsEmpty());
    TestFalse(TEXT("No worker dirty observation"), Read.PackageDirtyAfter.IsSet());
    return true;
}
#endif
