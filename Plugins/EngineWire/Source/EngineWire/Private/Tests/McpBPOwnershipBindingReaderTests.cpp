#include "Domains/Blueprint/Queries/McpBPOwnershipBindingReader.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Async/Async.h"
#include "Editor.h"
#include "Misc/AutomationTest.h"

namespace
{
using namespace McpBPOwnershipBindingReader;

bool RequireIdleEditor(FAutomationTestBase& Test)
{
    if (!IsInGameThread() || !GEditor || GEditor->IsPlaySessionInProgress())
    {
        Test.AddError(TEXT("This case requires the game thread and an idle editor; no session is changed by the test"));
        return false;
    }
    return true;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipReaderDefaults,
    "EngineWire.OwnershipBindingReader.Defaults",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipReaderDefaults::RunTest(const FString& Parameters)
{
    const FNodeRead Node;
    const FBatchRead Batch;
    const FMemberScalars Member;
    TestFalse(TEXT("Default node is not admitted"), Node.bAccepted);
    TestFalse(TEXT("Default node is not complete"), Node.bComplete);
    TestFalse(TEXT("Default batch is not admitted"), Batch.bAccepted);
    TestFalse(TEXT("Default batch is not complete"), Batch.bComplete);
    TestFalse(TEXT("Missing deprecated value is not silently false"), Member.WasDeprecated.IsSet());
    TestEqual(TEXT("Default raw parent is unknown, not null"), static_cast<int32>(Member.RawParent.State),
        static_cast<int32>(EPointerRead::NotCaptured));
    TestTrue(TEXT("Default raw parent has no invented path"), Member.RawParent.Path.IsEmpty());
    TestFalse(TEXT("Before dirty observation is absent"), Node.PackageDirtyBefore.IsSet());
    TestFalse(TEXT("After dirty observation is absent"), Node.PackageDirtyAfter.IsSet());
    TestEqual(TEXT("No processed inputs"), Batch.ProcessedNodes, 0);
    TestEqual(TEXT("No retained text"), Batch.RetainedTextChars, int64(0));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipReaderNull,
    "EngineWire.OwnershipBindingReader.NullNode",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipReaderNull::RunTest(const FString& Parameters)
{
    if (!RequireIdleEditor(*this)) return false;
    const FNodeRead Read = ReadNodeScalars(nullptr);
    TestFalse(TEXT("Null is refused"), Read.bAccepted);
    TestFalse(TEXT("Null cannot be complete"), Read.bComplete);
    TestEqual(TEXT("Refusal is specifically the node validity gate"), Read.Error,
        FString(TEXT("A live, already-loaded node is required")));
    TestTrue(TEXT("No member payload"), Read.Members.IsEmpty());
    TestFalse(TEXT("No package dirty read"), Read.PackageDirtyBefore.IsSet());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipReaderBatchLimits,
    "EngineWire.OwnershipBindingReader.BatchAdmission",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipReaderBatchLimits::RunTest(const FString& Parameters)
{
    if (!RequireIdleEditor(*this)) return false;
    TArray<const UEdGraphNode*> Inputs;
    const FBatchRead Empty = ReadNodeBatch(Inputs);
    Inputs.Init(nullptr, 17);
    const FBatchRead TooMany = ReadNodeBatch(Inputs);
    TestEqual(TEXT("Empty batch refused before node processing"), Empty.ProcessedNodes, 0);
    TestEqual(TEXT("Oversized batch refused before node processing"), TooMany.ProcessedNodes, 0);
    TestEqual(TEXT("Oversized requested count retained"), TooMany.RequestedNodes, 17);
    TestEqual(TEXT("Empty count gate"), Empty.Error, FString(TEXT("Expected 1..16 already-loaded node entries")));
    TestEqual(TEXT("Oversized count gate"), TooMany.Error, Empty.Error);
    TestFalse(TEXT("Empty not admitted"), Empty.bAccepted);
    TestFalse(TEXT("Oversized not admitted"), TooMany.bAccepted);
    for (const int32 Count : {1, 16})
    {
        Inputs.Init(nullptr, Count);
        const FBatchRead Read = ReadNodeBatch(Inputs);
        TestEqual(TEXT("Admissible size reaches first null then stops"), Read.ProcessedNodes, 1);
        TestEqual(TEXT("Rejected prefix has exactly one record"), Read.Nodes.Num(), 1);
        TestEqual(TEXT("Requested count is not processed count"), Read.RequestedNodes, Count);
        TestFalse(TEXT("Null batch not admitted"), Read.bAccepted);
        TestFalse(TEXT("Null batch not complete"), Read.bComplete);
        if (Read.Nodes.Num() == 1)
        {
            TestEqual(TEXT("First failure is specifically null-node gate"), Read.Nodes[0].Error,
                FString(TEXT("A live, already-loaded node is required")));
            TestEqual(TEXT("Retained error text accounting"), Read.RetainedTextChars,
                int64(Read.Error.Len()) + Read.Nodes[0].Error.Len());
        }
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipReaderWrongThread,
    "EngineWire.OwnershipBindingReader.WrongThread",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipReaderWrongThread::RunTest(const FString& Parameters)
{
    if (!GThreadPool)
    {
        AddError(TEXT("WrongThread case requires the existing engine thread pool; none is created by the test"));
        return false;
    }
    // No UObject is created or dereferenced. Assertions remain on the test thread.
    auto Future = Async(EAsyncExecution::ThreadPool, []()
    {
        TArray<const UEdGraphNode*> Inputs;
        Inputs.Add(nullptr);
        return TPair<FNodeRead, FBatchRead>(ReadNodeScalars(nullptr), ReadNodeBatch(Inputs));
    });
    const TPair<FNodeRead, FBatchRead> Read = Future.Get();
    TestEqual(TEXT("Single read refuses before null/editor gate"), Read.Key.Error,
        FString(TEXT("Game-thread read required")));
    TestEqual(TEXT("Batch refuses before node/editor gate"), Read.Value.Error, Read.Key.Error);
    TestFalse(TEXT("Worker single not admitted"), Read.Key.bAccepted);
    TestFalse(TEXT("Worker batch not admitted"), Read.Value.bAccepted);
    TestFalse(TEXT("Worker single not complete"), Read.Key.bComplete);
    TestFalse(TEXT("Worker batch not complete"), Read.Value.bComplete);
    TestEqual(TEXT("No worker node processing"), Read.Value.ProcessedNodes, 0);
    TestTrue(TEXT("Worker returns no node payload"), Read.Value.Nodes.IsEmpty());
    TestEqual(TEXT("Worker retained text is refusal only"), Read.Value.RetainedTextChars,
        int64(Read.Value.Error.Len()));
    return true;
}
#endif
