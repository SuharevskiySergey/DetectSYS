#include "Domains/Blueprint/Queries/McpBPOwnershipStructureReader.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Async/Async.h"
#include "Misc/AutomationTest.h"

namespace
{
using namespace McpBPOwnershipBindingReader;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipStructureDefaults,
    "EngineWire.OwnershipStructureReader.Defaults",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipStructureDefaults::RunTest(const FString& Parameters)
{
    const FOverridesRead Overrides;
    const FGraphTreeRead Graph;
    const FOverrideRead Record;
    TestFalse(TEXT("Overrides not admitted by default"), Overrides.bAccepted);
    TestFalse(TEXT("Overrides incomplete by default"), Overrides.bComplete);
    TestFalse(TEXT("Graph not admitted by default"), Graph.bAccepted);
    TestFalse(TEXT("Graph incomplete by default"), Graph.bComplete);
    TestEqual(TEXT("Unknown owner is not null"), static_cast<int32>(Record.KeyOwner.State),
        static_cast<int32>(EPointerRead::NotCaptured));
    TestFalse(TEXT("Unknown visible is not false"), Record.TemplateVisible.IsSet());
    TestFalse(TEXT("Unknown hidden is not false"), Record.TemplateHiddenInGame.IsSet());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipStructureNull,
    "EngineWire.OwnershipStructureReader.NullInputs",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipStructureNull::RunTest(const FString& Parameters)
{
    const FOverridesRead Overrides = ReadOwnOverrides(nullptr);
    const FGraphTreeRead Graph = ReadGraphTree(nullptr);
    TestFalse(TEXT("Null BP refused"), Overrides.bAccepted);
    TestFalse(TEXT("Null graph refused"), Graph.bAccepted);
    TestFalse(TEXT("Null BP not complete"), Overrides.bComplete);
    TestFalse(TEXT("Null graph not complete"), Graph.bComplete);
    TestTrue(TEXT("BP refusal has reason"), !Overrides.Error.IsEmpty());
    TestEqual(TEXT("Null graph gate reason"), Graph.Error, FString(TEXT("Live graph on game thread required")));
    TestTrue(TEXT("No override records read"), Overrides.Records.IsEmpty());
    TestTrue(TEXT("No nodes read"), Graph.Nodes.IsEmpty());
    TestTrue(TEXT("No edges read"), Graph.Edges.IsEmpty());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipStructureWrongThread,
    "EngineWire.OwnershipStructureReader.WrongThread",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipStructureWrongThread::RunTest(const FString& Parameters)
{
    if (!GThreadPool)
    {
        AddError(TEXT("Existing engine thread pool required"));
        return false;
    }
    auto Future = Async(EAsyncExecution::ThreadPool, []()
    {
        return TPair<FOverridesRead, FGraphTreeRead>(ReadOwnOverrides(nullptr), ReadGraphTree(nullptr));
    });
    const auto Read = Future.Get();
    TestFalse(TEXT("Worker overrides refused"), Read.Key.bAccepted);
    TestFalse(TEXT("Worker graph refused"), Read.Value.bAccepted);
    TestFalse(TEXT("Worker overrides incomplete"), Read.Key.bComplete);
    TestFalse(TEXT("Worker graph incomplete"), Read.Value.bComplete);
    TestTrue(TEXT("No worker records"), Read.Key.Records.IsEmpty());
    TestTrue(TEXT("No worker graphs"), Read.Value.GraphPaths.IsEmpty());
    TestEqual(TEXT("Worker BP gate reason"), Read.Key.Error,
        FString(TEXT("Idle game-thread editor and exact allowlisted Blueprint required")));
    TestEqual(TEXT("Worker graph gate reason"), Read.Value.Error,
        FString(TEXT("Live graph on game thread required")));
    return true;
}
#endif
