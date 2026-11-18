#include "Domains/Blueprint/Queries/McpBPOwnershipSCSOwnerReader.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Async/Async.h"
#include "Misc/AutomationTest.h"

namespace
{
using namespace McpBPOwnershipBindingReader;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSOwnerDefaults,
    "EngineWire.OwnershipSCSOwnerReader.Defaults",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSOwnerDefaults::RunTest(const FString& Parameters)
{
    const FSCSOwnerRead Read;
    TestFalse(TEXT("Default not admitted"), Read.bAccepted);
    TestFalse(TEXT("Default incomplete"), Read.bComplete);
    TestTrue(TEXT("No fabricated identity/error"), Read.BlueprintPath.IsEmpty() && Read.Error.IsEmpty());
    for (const FPointerObservation* Pointer : {&Read.GeneratedClass, &Read.BlueprintSCS, &Read.BlueprintHandler,
        &Read.ClassSCS, &Read.ClassHandler, &Read.ClassGeneratedBy})
    {
        TestEqual(TEXT("Pointer unknown, not observed null"), static_cast<int32>(Pointer->State), static_cast<int32>(EPointerRead::NotCaptured));
        TestTrue(TEXT("No fabricated path"), Pointer->Path.IsEmpty());
    }
    TestFalse(TEXT("SCS comparison absent"), Read.SameSCS.IsSet());
    TestFalse(TEXT("Handler comparison absent"), Read.SameHandler.IsSet());
    TestFalse(TEXT("Generated-by comparison absent"), Read.ClassGeneratedByIsBlueprint.IsSet());
    TestFalse(TEXT("Dirty-before absent"), Read.PackageDirtyBefore.IsSet());
    TestFalse(TEXT("Dirty-after absent"), Read.PackageDirtyAfter.IsSet());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSOwnerNull,
    "EngineWire.OwnershipSCSOwnerReader.NullInput",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSOwnerNull::RunTest(const FString& Parameters)
{
    const FSCSOwnerRead Read = ReadSCSOwnerPointers(nullptr);
    TestFalse(TEXT("Null refused"), Read.bAccepted);
    TestFalse(TEXT("Null incomplete"), Read.bComplete);
    TestEqual(TEXT("Exact admission refusal"), Read.Error,
        FString(TEXT("Idle game-thread editor and exact allowlisted SCS Blueprint required")));
    TestTrue(TEXT("No owner path read"), Read.BlueprintPath.IsEmpty());
    TestFalse(TEXT("No SCS comparison"), Read.SameSCS.IsSet());
    TestFalse(TEXT("No handler comparison"), Read.SameHandler.IsSet());
    TestFalse(TEXT("No dirty-before read"), Read.PackageDirtyBefore.IsSet());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSOwnerWrongThread,
    "EngineWire.OwnershipSCSOwnerReader.WrongThread",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSOwnerWrongThread::RunTest(const FString& Parameters)
{
    if (!GThreadPool)
    {
        AddError(TEXT("Existing engine thread pool required"));
        return false;
    }
    auto Future = Async(EAsyncExecution::ThreadPool, []() { return ReadSCSOwnerPointers(nullptr); });
    const FSCSOwnerRead Read = Future.Get();
    TestFalse(TEXT("Worker refused before object/schema access"), Read.bAccepted);
    TestFalse(TEXT("Worker incomplete"), Read.bComplete);
    TestEqual(TEXT("Exact worker admission refusal"), Read.Error,
        FString(TEXT("Idle game-thread editor and exact allowlisted SCS Blueprint required")));
    TestEqual(TEXT("Worker class uncaptured"), static_cast<int32>(Read.GeneratedClass.State), static_cast<int32>(EPointerRead::NotCaptured));
    TestFalse(TEXT("Worker generated-by comparison absent"), Read.ClassGeneratedByIsBlueprint.IsSet());
    TestFalse(TEXT("Worker dirty-after absent"), Read.PackageDirtyAfter.IsSet());
    return true;
}
#endif
