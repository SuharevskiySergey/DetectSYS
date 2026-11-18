#include "Domains/Blueprint/Queries/McpBPOwnershipSCSWalkFrontier.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

namespace
{
using namespace McpBPOwnershipBindingReader;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkFrontierDefaults,
    "EngineWire.OwnershipSCSWalkFrontier.Defaults",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkFrontierDefaults::RunTest(const FString& Parameters)
{
    FSCSWalkBudget Budget;
    FSCSWalkFrontier Frontier(Budget);
    TestEqual(TEXT("Empty identity table"), Frontier.GetCount(), 0);
    TestTrue(TEXT("No failure"), Frontier.GetStop() == ESCSWalkFrontierStop::None);
    TestEqual(TEXT("No next parent before sealing"), Frontier.PeekNextParent(), INDEX_NONE);
    TestNull(TEXT("Negative record refused"), Frontier.GetRecord(-1));
    TestNull(TEXT("Empty record absent"), Frontier.GetRecord(0));
    TestTrue(TEXT("Empty seeds sealed"), Frontier.SealSeeds());
    int32 Node = 77;
    TestTrue(TEXT("Empty FIFO exhausted"), Frontier.BeginNextParent(0, Node));
    TestEqual(TEXT("Exhaustion clears output"), Node, INDEX_NONE);
    TestTrue(TEXT("Repeated exhaustion is harmless"), Frontier.BeginNextParent(0, Node));
    TestEqual(TEXT("No node budget used"), Budget.GetNodes(), 0);
    TestEqual(TEXT("No child budget used"), Budget.GetChildSlots(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkFrontierSeeds,
    "EngineWire.OwnershipSCSWalkFrontier.SeedProvenance",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkFrontierSeeds::RunTest(const FString& Parameters)
{
    const int32 A = 1, B = 1; // Equal values, distinct addresses: never name/value dedup.
    FSCSWalkBudget Budget;
    FSCSWalkFrontier Frontier(Budget);
    int32 Node = 77;
    TestTrue(TEXT("Null root slot"), Frontier.AddRoot(nullptr, 0, Node));
    TestEqual(TEXT("Null has no identity"), Node, INDEX_NONE);
    TestTrue(TEXT("First A root"), Frontier.AddRoot(&A, 1, Node));
    TestEqual(TEXT("A index0"), Node, 0);
    TestTrue(TEXT("Repeated A root"), Frontier.AddRoot(&A, 2, Node));
    TestEqual(TEXT("Repeat same index"), Node, 0);
    TestTrue(TEXT("A registry overlap"), Frontier.AddRegistry(&A, 0, Node));
    TestTrue(TEXT("Registry-only B"), Frontier.AddRegistry(&B, 1, Node));
    TestEqual(TEXT("B distinct identity"), Node, 1);
    TestTrue(TEXT("Null registry slot"), Frontier.AddRegistry(nullptr, 2, Node));
    TestEqual(TEXT("Null resets output after B"), Node, INDEX_NONE);
    TestEqual(TEXT("All roots charged"), Budget.GetRootSlots(), 3);
    TestEqual(TEXT("All registry slots charged"), Budget.GetRegistrySlots(), 3);
    TestEqual(TEXT("Only two identities charged"), Budget.GetNodes(), 2);
    const FSCSWalkDiscoveryRecord* First = Frontier.GetRecord(0);
    const FSCSWalkDiscoveryRecord* Second = Frontier.GetRecord(1);
    if (!First || !Second) { AddError(TEXT("Expected two discovery records")); return false; }
    TestTrue(TEXT("A preserves first root provenance"), First->Identity == &A
        && First->Source == ESCSWalkDiscovery::Root && First->SourceIndex == 1
        && First->SourceNode == INDEX_NONE && First->Depth == 0);
    TestTrue(TEXT("B registry provenance"), Second->Identity == &B
        && Second->Source == ESCSWalkDiscovery::Registry && Second->SourceIndex == 1
        && Second->SourceNode == INDEX_NONE && Second->Depth == 0);
    TestNull(TEXT("Beyond record table"), Frontier.GetRecord(2));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkFrontierFIFO,
    "EngineWire.OwnershipSCSWalkFrontier.BreadthFirst",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkFrontierFIFO::RunTest(const FString& Parameters)
{
    int32 Identities[5] = {};
    FSCSWalkBudget Budget;
    FSCSWalkFrontier Frontier(Budget);
    int32 Node = INDEX_NONE;
    if (!Frontier.AddRoot(&Identities[0], 0, Node)
        || !Frontier.AddRegistry(&Identities[1], 0, Node) || !Frontier.SealSeeds())
    { AddError(TEXT("Seed preparation failed")); return false; }
    TestEqual(TEXT("Root first"), Frontier.PeekNextParent(), 0);
    if (!Frontier.BeginNextParent(3, Node)) { AddError(TEXT("Root begin failed")); return false; }
    TestEqual(TEXT("Active root index"), Node, 0);
    TestEqual(TEXT("Cannot peek through incomplete array"), Frontier.PeekNextParent(), INDEX_NONE);
    TestTrue(TEXT("A discovers child C"), Frontier.AddChild(&Identities[2], 0, Node));
    TestEqual(TEXT("C index2 behind all seeds"), Node, 2);
    TestTrue(TEXT("Null child"), Frontier.AddChild(nullptr, 1, Node));
    TestEqual(TEXT("Null output"), Node, INDEX_NONE);
    TestTrue(TEXT("Self edge"), Frontier.AddChild(&Identities[0], 2, Node));
    TestEqual(TEXT("Self resolves existing identity"), Node, 0);
    TestEqual(TEXT("Registry seed before children"), Frontier.PeekNextParent(), 1);
    if (!Frontier.BeginNextParent(2, Node)) { AddError(TEXT("Registry begin failed")); return false; }
    TestEqual(TEXT("Registry active index"), Node, 1);
    TestTrue(TEXT("Diamond/shared C edge"), Frontier.AddChild(&Identities[2], 0, Node));
    TestEqual(TEXT("Shared C not requeued"), Node, 2);
    TestTrue(TEXT("B discovers D"), Frontier.AddChild(&Identities[3], 1, Node));
    TestEqual(TEXT("D index3"), Node, 3);
    TestEqual(TEXT("C next"), Frontier.PeekNextParent(), 2);
    if (!Frontier.BeginNextParent(1, Node)) { AddError(TEXT("C begin failed")); return false; }
    TestTrue(TEXT("C discovers E"), Frontier.AddChild(&Identities[4], 0, Node));
    TestEqual(TEXT("E queued behind D"), Node, 4);
    TestEqual(TEXT("D before E"), Frontier.PeekNextParent(), 3);
    TestTrue(TEXT("D leaf"), Frontier.BeginNextParent(0, Node));
    TestEqual(TEXT("D active"), Node, 3);
    TestTrue(TEXT("E leaf"), Frontier.BeginNextParent(0, Node));
    TestEqual(TEXT("E active"), Node, 4);
    TestTrue(TEXT("FIFO exhausted"), Frontier.BeginNextParent(0, Node));
    TestEqual(TEXT("No repeated payload scheduled"), Node, INDEX_NONE);
    TestEqual(TEXT("Five distinct identities"), Frontier.GetCount(), 5);
    TestEqual(TEXT("Six raw child slots including null/self/shared"), Budget.GetChildSlots(), 6);
    const auto* C = Frontier.GetRecord(2);
    const auto* E = Frontier.GetRecord(4);
    if (!C || !E) { AddError(TEXT("Missing child provenance")); return false; }
    TestTrue(TEXT("Shared C retains FIRST parent"), C->Source == ESCSWalkDiscovery::Child
        && C->SourceNode == 0 && C->SourceIndex == 0 && C->Depth == 1);
    TestTrue(TEXT("E depth2 and C provenance"), E->SourceNode == 2 && E->SourceIndex == 0 && E->Depth == 2);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkFrontierDepth,
    "EngineWire.OwnershipSCSWalkFrontier.DepthAndBackEdges",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkFrontierDepth::RunTest(const FString& Parameters)
{
    int32 Identities[10] = {};
    FSCSWalkBudget Budget;
    FSCSWalkFrontier Frontier(Budget);
    int32 Node = INDEX_NONE;
    if (!Frontier.AddRoot(&Identities[0], 0, Node) || !Frontier.SealSeeds()) return false;
    for (int32 Depth = 0; Depth < 8; ++Depth)
    {
        if (!Frontier.BeginNextParent(1, Node) || Node != Depth
            || !Frontier.AddChild(&Identities[Depth + 1], 0, Node))
        { AddError(TEXT("Depth0..8 chain preparation failed")); return false; }
    }
    const auto* Last = Frontier.GetRecord(8);
    if (!Last) { AddError(TEXT("Depth8 node absent")); return false; }
    TestEqual(TEXT("Depth8 admitted"), Last->Depth, 8);
    if (!Frontier.BeginNextParent(3, Node)) return false;
    TestTrue(TEXT("Back edge at depth8 allowed"), Frontier.AddChild(&Identities[0], 0, Node));
    TestEqual(TEXT("Back edge index0"), Node, 0);
    TestTrue(TEXT("Self edge at depth8 allowed"), Frontier.AddChild(&Identities[8], 1, Node));
    TestEqual(TEXT("Self index8"), Node, 8);
    TestFalse(TEXT("New node at depth9 refused"), Frontier.AddChild(&Identities[9], 2, Node));
    TestEqual(TEXT("Refused output absent"), Node, INDEX_NONE);
    TestEqual(TEXT("Only nine identities retained"), Frontier.GetCount(), 9);
    TestEqual(TEXT("Whole last array charged even after refusal"), Budget.GetChildSlots(), 11);
    TestTrue(TEXT("Budget depth reason"), Budget.GetStop() == ESCSWalkBudgetStop::Depth);
    TestTrue(TEXT("Frontier budget refusal"), Frontier.GetStop() == ESCSWalkFrontierStop::Budget);
    TestEqual(TEXT("No next parent after refusal"), Frontier.PeekNextParent(), INDEX_NONE);
    // These are opaque synthetic identity edges, not a live SCS cycle test.
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkFrontierLimits,
    "EngineWire.OwnershipSCSWalkFrontier.SharedLimits",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkFrontierLimits::RunTest(const FString& Parameters)
{
    int32 Identities[129] = {};
    FSCSWalkBudget Nodes;
    FSCSWalkFrontier Full(Nodes);
    int32 Node = INDEX_NONE;
    for (int32 Index = 0; Index < 128; ++Index)
    {
        if (!Full.AddRoot(&Identities[Index], Index, Node))
        { AddError(TEXT("128 root identities should fit")); return false; }
    }
    TestTrue(TEXT("Repeat at full node table still admitted"), Full.AddRegistry(&Identities[0], 0, Node));
    TestEqual(TEXT("Repeat index preserved"), Node, 0);
    TestFalse(TEXT("Distinct node129 refused"), Full.AddRegistry(&Identities[128], 1, Node));
    TestEqual(TEXT("Table bounded128"), Full.GetCount(), 128);
    TestEqual(TEXT("Node counter bounded128"), Nodes.GetNodes(), 128);
    TestEqual(TEXT("Offending registry slot remains charged"), Nodes.GetRegistrySlots(), 2);
    TestTrue(TEXT("Full frontier stopped"), Full.GetStop() == ESCSWalkFrontierStop::Budget);

    FSCSWalkBudget Edges;
    FSCSWalkFrontier Split(Edges);
    if (!Split.AddRoot(&Identities[0], 0, Node) || !Split.AddRoot(&Identities[1], 1, Node)
        || !Split.SealSeeds() || !Split.BeginNextParent(256, Node)) return false;
    for (int32 Index = 0; Index < 256; ++Index)
    {
        if (!Split.AddChild(nullptr, Index, Node))
        { AddError(TEXT("256 null child slots should fit")); return false; }
    }
    TestFalse(TEXT("Next parent's array exceeds global slots"), Split.BeginNextParent(1, Node));
    TestEqual(TEXT("Refused parent output cleared"), Node, INDEX_NONE);
    TestEqual(TEXT("Global edges remain256"), Edges.GetChildSlots(), 256);
    TestTrue(TEXT("Global child-slot budget reason"), Edges.GetStop() == ESCSWalkBudgetStop::ChildSlots);

    FSCSWalkBudget Shared;
    FSCSWalkFrontier External(Shared);
    TestTrue(TEXT("External owner uses normal text allowance"),
        Shared.ReserveText(FSCSWalkBudget::MaxTextChars - FSCSWalkBudget::DiagnosticReserveChars));
    TestFalse(TEXT("External owner stops shared budget"), Shared.ReserveText(1));
    TestFalse(TEXT("Stopped shared budget blocks frontier"), External.AddRoot(&Identities[0], 0, Node));
    TestEqual(TEXT("No identity retained after external stop"), External.GetCount(), 0);
    TestEqual(TEXT("No root slot charged after external stop"), Shared.GetRootSlots(), 0);
    TestTrue(TEXT("External stop translated"), External.GetStop() == ESCSWalkFrontierStop::Budget);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkFrontierRefusals,
    "EngineWire.OwnershipSCSWalkFrontier.PhasesAndRefusal",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkFrontierRefusals::RunTest(const FString& Parameters)
{
    const int32 Identity = 0;
    int32 Node = 77;
    {
        FSCSWalkBudget Budget;
        FSCSWalkFrontier Frontier(Budget);
        TestFalse(TEXT("Begin before seal refused"), Frontier.BeginNextParent(0, Node));
        TestEqual(TEXT("Failure clears output"), Node, INDEX_NONE);
        TestTrue(TEXT("Wrong phase reason"), Frontier.GetStop() == ESCSWalkFrontierStop::WrongPhase);
        TestFalse(TEXT("Sticky failure blocks roots"), Frontier.AddRoot(&Identity, 0, Node));
        TestEqual(TEXT("No roots charged after failure"), Budget.GetRootSlots(), 0);
    }
    {
        FSCSWalkBudget Budget;
        FSCSWalkFrontier Frontier(Budget);
        TestFalse(TEXT("Skipped root index refused"), Frontier.AddRoot(&Identity, 1, Node));
        TestTrue(TEXT("Index reason"), Frontier.GetStop() == ESCSWalkFrontierStop::InvalidProvenance);
        TestFalse(TEXT("Sealing does not erase first refusal"), Frontier.SealSeeds());
        TestTrue(TEXT("Index reason remains first"), Frontier.GetStop() == ESCSWalkFrontierStop::InvalidProvenance);
    }
    {
        FSCSWalkBudget Budget;
        FSCSWalkFrontier Frontier(Budget);
        TestTrue(TEXT("Registry-only input allowed"), Frontier.AddRegistry(&Identity, 0, Node));
        TestFalse(TEXT("Root after registry refused"), Frontier.AddRoot(&Identity, 0, Node));
        TestEqual(TEXT("Refused root not charged"), Budget.GetRootSlots(), 0);
    }
    {
        FSCSWalkBudget Budget;
        FSCSWalkFrontier Frontier(Budget);
        if (!Frontier.AddRoot(&Identity, 0, Node) || !Frontier.SealSeeds()
            || !Frontier.BeginNextParent(2, Node) || !Frontier.AddChild(nullptr, 0, Node)) return false;
        TestFalse(TEXT("Cannot skip unfinished child array"), Frontier.BeginNextParent(0, Node));
        TestEqual(TEXT("Whole two-slot array already charged"), Budget.GetChildSlots(), 2);
        TestFalse(TEXT("Refusal cannot be repaired by remaining slot"), Frontier.AddChild(nullptr, 1, Node));
    }
    {
        FSCSWalkBudget Budget;
        FSCSWalkFrontier Frontier(Budget);
        if (!Frontier.AddRoot(&Identity, 0, Node) || !Frontier.SealSeeds()
            || !Frontier.BeginNextParent(1, Node)) return false;
        TestFalse(TEXT("Child raw index cannot skip zero"), Frontier.AddChild(nullptr, 1, Node));
        TestTrue(TEXT("Child provenance reason"), Frontier.GetStop() == ESCSWalkFrontierStop::InvalidProvenance);
    }
    {
        FSCSWalkBudget Budget;
        FSCSWalkFrontier Frontier(Budget);
        if (!Frontier.SealSeeds()) return false;
        TestFalse(TEXT("Nonempty array without parent refused"), Frontier.BeginNextParent(1, Node));
        TestEqual(TEXT("Missing parent array uncharged"), Budget.GetChildSlots(), 0);
    }
    {
        FSCSWalkBudget Budget;
        FSCSWalkFrontier Frontier(Budget);
        if (!Frontier.AddRoot(&Identity, 0, Node) || !Frontier.SealSeeds()) return false;
        TestFalse(TEXT("Negative child count refused"), Frontier.BeginNextParent(-1, Node));
        TestTrue(TEXT("Negative count budget reason"), Budget.GetStop() == ESCSWalkBudgetStop::InvalidCount);
        TestEqual(TEXT("Negative array uncharged"), Budget.GetChildSlots(), 0);
    }
    return true;
}
#endif
