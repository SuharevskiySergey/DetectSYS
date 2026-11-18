#include "Domains/Blueprint/Queries/McpBPOwnershipSCSListReader.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Async/Async.h"
#include "Misc/AutomationTest.h"

namespace
{
using namespace McpBPOwnershipBindingReader;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSListsDefaults,
    "EngineWire.OwnershipSCSListReader.Defaults",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSListsDefaults::RunTest(const FString& Parameters)
{
    const FSCSListsRead Read;
    TestFalse(TEXT("Default not admitted"), Read.bAccepted);
    TestFalse(TEXT("Default incomplete"), Read.bComplete);
    TestTrue(TEXT("No fabricated lists or identity"), Read.Roots.IsEmpty() && Read.Registry.IsEmpty() && Read.SCSPath.IsEmpty());
    TestTrue(TEXT("No default error"), Read.Error.IsEmpty());
    TestFalse(TEXT("Dirty-before unknown"), Read.PackageDirtyBefore.IsSet());
    TestFalse(TEXT("Dirty-after unknown"), Read.PackageDirtyAfter.IsSet());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSListsNull,
    "EngineWire.OwnershipSCSListReader.NullInputs",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSListsNull::RunTest(const FString& Parameters)
{
    const FSCSListsRead Read = ReadSCSRawLists(nullptr, nullptr);
    TestFalse(TEXT("Null owner refused"), Read.bAccepted);
    TestFalse(TEXT("Null owner incomplete"), Read.bComplete);
    TestEqual(TEXT("Owner refusal precedes SCS access"), Read.Error,
        FString(TEXT("Idle game-thread editor and exact allowlisted SCS Blueprint required")));
    TestTrue(TEXT("No null-input lists"), Read.Roots.IsEmpty() && Read.Registry.IsEmpty());
    TestFalse(TEXT("No dirty read"), Read.PackageDirtyBefore.IsSet());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSListsWrongThread,
    "EngineWire.OwnershipSCSListReader.WrongThread",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSListsWrongThread::RunTest(const FString& Parameters)
{
    if (!GThreadPool) { AddError(TEXT("Existing engine thread pool required")); return false; }
    auto Future = Async(EAsyncExecution::ThreadPool, []() { return ReadSCSRawLists(nullptr, nullptr); });
    const FSCSListsRead Read = Future.Get();
    TestFalse(TEXT("Worker refused"), Read.bAccepted);
    TestFalse(TEXT("Worker incomplete"), Read.bComplete);
    TestEqual(TEXT("Worker owner gate precedes object/schema access"), Read.Error,
        FString(TEXT("Idle game-thread editor and exact allowlisted SCS Blueprint required")));
    TestTrue(TEXT("No worker lists"), Read.Roots.IsEmpty() && Read.Registry.IsEmpty());
    TestFalse(TEXT("No worker dirty observation"), Read.PackageDirtyAfter.IsSet());
    return true;
}
#endif
