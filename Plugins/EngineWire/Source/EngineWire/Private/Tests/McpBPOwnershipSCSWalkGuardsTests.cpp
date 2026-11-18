#include "Domains/Blueprint/Queries/McpBPOwnershipSCSWalkGuards.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Async/Async.h"
#include "Editor.h"
#include "HAL/PlatformMisc.h"
#include "Misc/App.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UObject/Package.h"
#include "UObject/UObjectArray.h"
#include "UObject/UObjectGlobals.h"

namespace
{
using namespace McpBPOwnershipBindingReader;

bool PermitGuardBookkeeping(FAutomationTestBase& Test)
{
    const FString Local = FPlatformMisc::GetEnvironmentVariable(TEXT("LOCALAPPDATA"));
    const FString ProjectDir = FPaths::GetPath(FPaths::ConvertRelativePathToFull(FPaths::GetProjectFilePath()));
    if (Local.IsEmpty() || !IsInGameThread() || !GEditor || GEditor->IsPlaySessionInProgress()
        || FString(FApp::GetProjectName()) != TEXT("BeholderStructureTestHost")
        || !FPaths::IsUnderDirectory(ProjectDir, FPaths::Combine(Local, TEXT("Temp/opencode")))
        || !FParse::Param(FCommandLine::Get(), TEXT("McpOwnershipGuardBookkeeping")))
    {
        Test.AddError(TEXT("Guard bookkeeping requires isolated Temp/opencode host and explicit -McpOwnershipGuardBookkeeping opt-in"));
        return false;
    }
    return true;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkGuardsDefaults,
    "EngineWire.OwnershipSCSWalkGuards.Defaults",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkGuardsDefaults::RunTest(const FString& Parameters)
{
    FSCSWalkBudget Budget;
    const FSCSWalkGuards Guards(Budget);
    TestEqual(TEXT("No held objects"), Guards.GetCount(), 0);
    TestTrue(TEXT("No default refusal"), Guards.GetStop() == ESCSWalkGuardStop::None);
    TestEqual(TEXT("No guard charges"), Budget.GetGuards(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkGuardsNull,
    "EngineWire.OwnershipSCSWalkGuards.NullIdleContext",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkGuardsNull::RunTest(const FString& Parameters)
{
    FSCSWalkBudget Budget;
    FSCSWalkGuards Guards(Budget);
    TestTrue(TEXT("Null accepted only in idle context"), Guards.HoldResolvedBorrowed(nullptr));
    TestTrue(TEXT("Empty set recheck"), Guards.Recheck());
    TestEqual(TEXT("Null holds nothing"), Guards.GetCount(), 0);
    TestEqual(TEXT("Null consumes no guard allowance"), Budget.GetGuards(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkGuardsThread,
    "EngineWire.OwnershipSCSWalkGuards.WrongThread",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkGuardsThread::RunTest(const FString& Parameters)
{
    if (!GThreadPool) { AddError(TEXT("Existing thread pool required")); return false; }
    // Construct/destroy on game thread; worker only probes an empty guard set.
    FSCSWalkBudget Budget;
    FSCSWalkGuards Guards(Budget);
    auto Future = Async(EAsyncExecution::ThreadPool, [&Guards]()
    {
        return Guards.HoldResolvedBorrowed(nullptr);
    });
    TestFalse(TEXT("Worker refused before object access"), Future.Get());
    TestTrue(TEXT("Context refusal recorded"), Guards.GetStop() == ESCSWalkGuardStop::ContextUnavailable);
    TestFalse(TEXT("Game-thread retry cannot erase refusal"), Guards.Recheck());
    TestEqual(TEXT("No worker-held objects"), Guards.GetCount(), 0);
    TestEqual(TEXT("No worker guard charge"), Budget.GetGuards(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkGuardsPackage,
    "EngineWire.OwnershipSCSWalkGuards.BorrowedPackage",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkGuardsPackage::RunTest(const FString& Parameters)
{
    // Source preparation does not authorize this opt-in or any execution.
    if (!PermitGuardBookkeeping(*this)) return false;
    UPackage* Package = GetTransientPackage(); // Existing engine-owned object, no NewObject/load.
    if (!IsValid(Package) || !Package->IsRooted())
    { AddError(TEXT("Existing rooted transient package required")); return false; }
    FUObjectItem* Item = GUObjectArray.ObjectToObjectItem(Package);
    if (!Item) { AddError(TEXT("Existing object item required")); return false; }
    const int32 BeforeRefs = Item->GetRefCount();
    const bool BeforeDirty = Package->IsDirty();
    const bool BeforeRooted = Package->IsRooted();
    FSCSWalkBudget Budget;
    {
        FSCSWalkGuards Guards(Budget);
        if (!Guards.HoldResolvedBorrowed(Package))
        { AddError(TEXT("Idle-context package hold refused")); return false; }
        TestEqual(TEXT("One acquired ref"), Item->GetRefCount(), BeforeRefs + 1);
        TestEqual(TEXT("One identity"), Guards.GetCount(), 1);
        TestTrue(TEXT("Duplicate package hold accepted"), Guards.HoldResolvedBorrowed(Package));
        TestEqual(TEXT("Duplicate does not AddRef again"), Item->GetRefCount(), BeforeRefs + 1);
        TestEqual(TEXT("Duplicate consumes no guard slot"), Budget.GetGuards(), 1);
        TestTrue(TEXT("Held package recheck"), Guards.Recheck());
        // A second set has its own ref, even when sharing one accounting budget.
        {
            FSCSWalkGuards Other(Budget);
            TestTrue(TEXT("Independent set holds package"), Other.HoldResolvedBorrowed(Package));
            TestEqual(TEXT("Two active references"), Item->GetRefCount(), BeforeRefs + 2);
            TestEqual(TEXT("Independent acquisition charged"), Budget.GetGuards(), 2);
        }
        TestEqual(TEXT("Inner destructor releases its ref"), Item->GetRefCount(), BeforeRefs + 1);
        TestTrue(TEXT("Stop shared text budget"), Budget.ReserveText(
            FSCSWalkBudget::MaxTextChars - FSCSWalkBudget::DiagnosticReserveChars));
        TestFalse(TEXT("Over-limit text refuses"), Budget.ReserveText(1));
        TestFalse(TEXT("Shared stop blocks guard recheck"), Guards.Recheck());
        TestTrue(TEXT("Guard reports shared budget refusal"), Guards.GetStop() == ESCSWalkGuardStop::Budget);
        TestEqual(TEXT("Ref held until scope exit even after refusal"), Item->GetRefCount(), BeforeRefs + 1);
    }
    TestEqual(TEXT("Outer destructor releases remaining ref"), Item->GetRefCount(), BeforeRefs);
    TestEqual(TEXT("Reservations are not rolled back"), Budget.GetGuards(), 2);
    TestEqual(TEXT("Package dirty unchanged"), Package->IsDirty(), BeforeDirty);
    TestEqual(TEXT("RootSet observation unchanged"), Package->IsRooted(), BeforeRooted);
    // Already rooted object: NOT collection survival, explicit destruction,
    // pending-GC barrier, outer-chain protection or atomic snapshot verification.
    return true;
}
#endif
