#include "Domains/Blueprint/Queries/McpBPOwnershipSCSWalkBudget.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

namespace
{
using namespace McpBPOwnershipBindingReader;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkBudgetDefaults,
    "EngineWire.OwnershipSCSWalkBudget.Defaults",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkBudgetDefaults::RunTest(const FString& Parameters)
{
    FSCSWalkBudget Budget;
    TestFalse(TEXT("Initially not stopped"), Budget.IsStopped());
    TestTrue(TEXT("Initially no reason"), Budget.GetStop() == ESCSWalkBudgetStop::None);
    TestTrue(TEXT("All counters zero"), Budget.GetRootSlots() == 0 && Budget.GetRegistrySlots() == 0
        && Budget.GetNodes() == 0 && Budget.GetChildSlots() == 0
        && Budget.GetGuards() == 0 && Budget.GetTextChars() == 0);
    TestTrue(TEXT("Empty reservations accepted"), Budget.ReserveRoots(0) && Budget.ReserveRegistry(0)
        && Budget.ReserveChildren(0) && Budget.ReserveText(0));
    TestFalse(TEXT("Empty reservations do not stop"), Budget.IsStopped());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkBudgetLists,
    "EngineWire.OwnershipSCSWalkBudget.ListSlots",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkBudgetLists::RunTest(const FString& Parameters)
{
    FSCSWalkBudget Roots;
    TestTrue(TEXT("Root128 accepted"), Roots.ReserveRoots(128));
    TestTrue(TEXT("Independent registry128 accepted"), Roots.ReserveRegistry(128));
    TestFalse(TEXT("Root129 refused"), Roots.ReserveRoots(1));
    TestEqual(TEXT("Root failure retains count128"), Roots.GetRootSlots(), 128);
    TestEqual(TEXT("Registry untouched by root failure"), Roots.GetRegistrySlots(), 128);
    TestTrue(TEXT("Root reason"), Roots.GetStop() == ESCSWalkBudgetStop::Roots);

    FSCSWalkBudget Registry;
    TestFalse(TEXT("Registry129 refused before charge"), Registry.ReserveRegistry(129));
    TestEqual(TEXT("No partial registry charge"), Registry.GetRegistrySlots(), 0);
    TestTrue(TEXT("Registry reason"), Registry.GetStop() == ESCSWalkBudgetStop::Registry);
    FSCSWalkBudget OversizedRoots;
    TestFalse(TEXT("Single root129 refused"), OversizedRoots.ReserveRoots(129));
    TestEqual(TEXT("No partial root charge"), OversizedRoots.GetRootSlots(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkBudgetEdges,
    "EngineWire.OwnershipSCSWalkBudget.AggregateChildSlots",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkBudgetEdges::RunTest(const FString& Parameters)
{
    FSCSWalkBudget Budget;
    TestTrue(TEXT("First parent200"), Budget.ReserveChildren(200));
    TestTrue(TEXT("Second parent56 reaches total256"), Budget.ReserveChildren(56));
    TestTrue(TEXT("Empty parent still accepted at limit"), Budget.ReserveChildren(0));
    TestFalse(TEXT("Third parent1 exceeds global bound"), Budget.ReserveChildren(1));
    TestEqual(TEXT("No over-limit charge"), Budget.GetChildSlots(), 256);
    TestTrue(TEXT("Child-slot reason"), Budget.GetStop() == ESCSWalkBudgetStop::ChildSlots);
    FSCSWalkBudget Oversized;
    TestFalse(TEXT("Single parent257 refused"), Oversized.ReserveChildren(257));
    TestEqual(TEXT("Whole oversized array uncharged"), Oversized.GetChildSlots(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkBudgetNodes,
    "EngineWire.OwnershipSCSWalkBudget.NodesAndDepth",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkBudgetNodes::RunTest(const FString& Parameters)
{
    FSCSWalkBudget Nodes;
    bool AllAccepted = true;
    for (int32 Index = 0; Index < 128; ++Index) AllAccepted &= Nodes.ReserveNode(0);
    TestTrue(TEXT("128 new seed identities accepted"), AllAccepted);
    TestFalse(TEXT("Node129 refused"), Nodes.ReserveNode(0));
    TestEqual(TEXT("Node count remains128"), Nodes.GetNodes(), 128);
    TestTrue(TEXT("Node reason"), Nodes.GetStop() == ESCSWalkBudgetStop::Nodes);

    FSCSWalkBudget Depth;
    TestTrue(TEXT("Seed depth0 accepted"), Depth.ReserveNode(0));
    TestTrue(TEXT("Discovery depth8 accepted"), Depth.ReserveNode(8));
    TestTrue(TEXT("Back-edge slot can be charged without reserving another node"), Depth.ReserveChildren(1));
    TestEqual(TEXT("Edge reservation adds no identity"), Depth.GetNodes(), 2);
    TestFalse(TEXT("New identity at depth9 refused"), Depth.ReserveNode(9));
    TestEqual(TEXT("Depth failure adds no node"), Depth.GetNodes(), 2);
    TestTrue(TEXT("Depth reason"), Depth.GetStop() == ESCSWalkBudgetStop::Depth);
    // This is arithmetic/API usage only, not actual cycle/dedup traversal.
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkBudgetGuards,
    "EngineWire.OwnershipSCSWalkBudget.Guards",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkBudgetGuards::RunTest(const FString& Parameters)
{
    FSCSWalkBudget Budget;
    bool AllAccepted = true;
    for (int32 Index = 0; Index < 392; ++Index) AllAccepted &= Budget.ReserveGuard();
    TestTrue(TEXT("Guard392 accepted"), AllAccepted);
    TestFalse(TEXT("Guard393 refused"), Budget.ReserveGuard());
    TestEqual(TEXT("Guard count bounded"), Budget.GetGuards(), 392);
    TestTrue(TEXT("Guard reason"), Budget.GetStop() == ESCSWalkBudgetStop::Guards);
    // No strong pointer is created by this test.
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkBudgetText,
    "EngineWire.OwnershipSCSWalkBudget.Text",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkBudgetText::RunTest(const FString& Parameters)
{
    FSCSWalkBudget Budget;
    const int64 NormalLimit = FSCSWalkBudget::MaxTextChars - FSCSWalkBudget::DiagnosticReserveChars;
    TestTrue(TEXT("First text fragment"), Budget.ReserveText(100));
    TestTrue(TEXT("Exact normal text limit accepted"), Budget.ReserveText(NormalLimit - 100));
    TestTrue(TEXT("Empty field at limit accepted"), Budget.ReserveText(0));
    TestFalse(TEXT("Diagnostic reserve unavailable to normal text"), Budget.ReserveText(1));
    TestEqual(TEXT("Text count bounded"), Budget.GetTextChars(), NormalLimit);
    TestTrue(TEXT("Text reason"), Budget.GetStop() == ESCSWalkBudgetStop::Text);

    FSCSWalkBudget Overflow;
    TestTrue(TEXT("Nonzero before extreme input"), Overflow.ReserveText(1));
    TestFalse(TEXT("INT64_MAX refuses without adding"), Overflow.ReserveText(9223372036854775807LL));
    TestEqual(TEXT("Extreme input preserves prior text"), Overflow.GetTextChars(), int64(1));
    TestTrue(TEXT("Extreme input text reason"), Overflow.GetStop() == ESCSWalkBudgetStop::Text);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkBudgetRefusal,
    "EngineWire.OwnershipSCSWalkBudget.InvalidAndSticky",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkBudgetRefusal::RunTest(const FString& Parameters)
{
    FSCSWalkBudget NegativeRoots;
    FSCSWalkBudget NegativeRegistry;
    FSCSWalkBudget NegativeChildren;
    FSCSWalkBudget NegativeDepth;
    FSCSWalkBudget NegativeText;
    TestFalse(TEXT("Negative roots refused"), NegativeRoots.ReserveRoots(-1));
    TestFalse(TEXT("Negative registry refused"), NegativeRegistry.ReserveRegistry(-1));
    TestFalse(TEXT("Negative child slots refused"), NegativeChildren.ReserveChildren(-1));
    TestFalse(TEXT("Negative depth refused"), NegativeDepth.ReserveNode(-1));
    TestFalse(TEXT("Negative text refused"), NegativeText.ReserveText(-1));
    TestTrue(TEXT("All negative reasons are InvalidCount"),
        NegativeRoots.GetStop() == ESCSWalkBudgetStop::InvalidCount
        && NegativeRegistry.GetStop() == ESCSWalkBudgetStop::InvalidCount
        && NegativeChildren.GetStop() == ESCSWalkBudgetStop::InvalidCount
        && NegativeDepth.GetStop() == ESCSWalkBudgetStop::InvalidCount
        && NegativeText.GetStop() == ESCSWalkBudgetStop::InvalidCount);

    FSCSWalkBudget Sticky;
    TestTrue(TEXT("Initial root charge"), Sticky.ReserveRoots(3));
    TestFalse(TEXT("First refusal is depth"), Sticky.ReserveNode(9));
    TestFalse(TEXT("Later invalid input refused"), Sticky.ReserveText(-1));
    TestFalse(TEXT("Later roots refused"), Sticky.ReserveRoots(1));
    TestFalse(TEXT("Later registry refused"), Sticky.ReserveRegistry(1));
    TestFalse(TEXT("Later children refused"), Sticky.ReserveChildren(1));
    TestFalse(TEXT("Later node refused"), Sticky.ReserveNode(0));
    TestFalse(TEXT("Later guard refused"), Sticky.ReserveGuard());
    TestFalse(TEXT("Even zero text refused after stop"), Sticky.ReserveText(0));
    TestTrue(TEXT("First reason preserved"), Sticky.GetStop() == ESCSWalkBudgetStop::Depth);
    TestTrue(TEXT("All counters frozen after stop"), Sticky.GetRootSlots() == 3
        && Sticky.GetRegistrySlots() == 0 && Sticky.GetNodes() == 0
        && Sticky.GetChildSlots() == 0 && Sticky.GetGuards() == 0 && Sticky.GetTextChars() == 0);
    return true;
}
#endif
