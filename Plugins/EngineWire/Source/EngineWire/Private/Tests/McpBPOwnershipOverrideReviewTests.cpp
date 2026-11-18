#include "Domains/Blueprint/Queries/McpBPOwnershipOverrideReview.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

namespace
{
using namespace McpBPOwnershipBindingReader;

FOverrideChainRead ReviewFixture(int32 Count = 2)
{
    FOverrideChainRead Chain;
    Chain.bAccepted = true;
    Chain.Stop = EChainStop::NativeTerminal;
    for (int32 I = 0; I < Count; ++I)
    {
        FOverrideLayerRead Layer;
        Layer.Depth = I;
        Layer.Own.bAccepted = true;
        Chain.Layers.Add(MoveTemp(Layer));
    }
    return Chain;
}

FOverrideRead ReviewRecord(const TCHAR* Owner = TEXT("/Fixture/ClassA"), FGuid Guid = FGuid(1, 2, 3, 4),
    const TCHAR* Name = TEXT("SocketHousing"))
{
    FOverrideRead Record;
    Record.KeyOwner.State = EPointerRead::Resolved;
    Record.KeyOwner.Path = Owner;
    Record.AssociatedGuid = Guid;
    Record.VariableName = FName(Name);
    return Record;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipPathReviewGrouping,
    "EngineWire.OwnershipOverrideReview.PathKeyGrouping",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipPathReviewGrouping::RunTest(const FString& Parameters)
{
    FOverrideChainRead Chain = ReviewFixture();
    Chain.Layers[0].Own.Records.Add(ReviewRecord());
    Chain.Layers[0].Own.Records.Add(ReviewRecord(TEXT("/Fixture/ClassB")));
    Chain.Layers[1].Own.Records.Add(ReviewRecord(TEXT("/Fixture/ClassA"), FGuid(1, 2, 3, 4), TEXT("RenamedPart")));
    Chain.Layers[1].Own.Records.Add(ReviewRecord(TEXT("/Fixture/ClassA"), FGuid(5, 6, 7, 8)));
    const FOverridePathReview Read = ReviewOverridePathCandidates(Chain);
    TestTrue(TEXT("DTO review completed"), Read.bReviewed);
    TestFalse(TEXT("DTO paths do not certify native identity"), Read.bEngineIdentityVerified);
    TestFalse(TEXT("DTO candidates do not make complete capture"), Read.bComplete);
    TestEqual(TEXT("Owner and GUID separate groups, component name does not"), Read.Groups.Num(), 3);
    if (Read.Groups.Num() == 3)
    {
        TestEqual(TEXT("Renamed ancestor retains same snapshot key group"), Read.Groups[0].Sources.Num(), 2);
        TestEqual(TEXT("Nearest candidate is child"), Read.Groups[0].Candidate.Layer, 0);
        TestEqual(TEXT("Nearest record index"), Read.Groups[0].Candidate.Record, 0);
        TestFalse(TEXT("Cross-layer shadow is not same-layer conflict"), Read.Groups[0].bSameLayerConflict);
        TestEqual(TEXT("Ancestor provenance kept"), Read.Groups[0].Sources[1].Layer, 1);
        TestEqual(TEXT("Different-owner candidate retains its own record index"), Read.Groups[1].Candidate.Record, 1);
        TestEqual(TEXT("Different-GUID candidate remains parent-layer"), Read.Groups[2].Candidate.Layer, 1);
    }
    TestEqual(TEXT("Input metadata was not rewritten"), Chain.Layers[1].Own.Records[0].VariableName, FName(TEXT("RenamedPart")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipPathReviewConflicts,
    "EngineWire.OwnershipOverrideReview.DuplicateConflicts",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipPathReviewConflicts::RunTest(const FString& Parameters)
{
    for (const int32 ConflictLayer : {0, 1})
    {
        FOverrideChainRead Chain = ReviewFixture();
        Chain.Layers[0].Own.Records.Add(ReviewRecord());
        Chain.Layers[1].Own.Records.Add(ReviewRecord());
        Chain.Layers[ConflictLayer].Own.Records.Add(ReviewRecord());
        const FOverridePathReview Read = ReviewOverridePathCandidates(Chain);
        TestTrue(TEXT("Conflicted DTOs are reviewed, not silently dropped"), Read.bReviewed);
        TestEqual(TEXT("One ambiguous snapshot key"), Read.Groups.Num(), 1);
        if (Read.Groups.Num() == 1)
        {
            TestTrue(TEXT("Duplicate in any one layer is conflict"), Read.Groups[0].bSameLayerConflict);
            TestEqual(TEXT("No last-write-wins candidate"), Read.Groups[0].Candidate.Layer, INDEX_NONE);
            TestEqual(TEXT("No partial candidate record"), Read.Groups[0].Candidate.Record, INDEX_NONE);
            TestEqual(TEXT("All conflicting provenance retained"), Read.Groups[0].Sources.Num(), 3);
        }
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipPathReviewUnknown,
    "EngineWire.OwnershipOverrideReview.UnknownKeys",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipPathReviewUnknown::RunTest(const FString& Parameters)
{
    for (int32 Form = 0; Form < 4; ++Form)
    {
        FOverrideChainRead Chain = ReviewFixture();
        Chain.Layers[0].Own.Records.Add(ReviewRecord());
        FOverrideRead Unknown = ReviewRecord();
        if (Form == 0) Unknown.KeyOwner.State = EPointerRead::Unresolved;
        else if (Form == 1) Unknown.KeyOwner.State = EPointerRead::Null;
        else if (Form == 2) Unknown.KeyOwner.Path.Reset();
        else Unknown.AssociatedGuid.Invalidate();
        Chain.Layers[1].Own.Records.Add(Unknown);
        const FOverridePathReview Read = ReviewOverridePathCandidates(Chain);
        TestTrue(TEXT("Unknown keys recorded, not accepted as native identity"), Read.bReviewed);
        TestEqual(TEXT("Unknown source retained"), Read.Uncomparable.Num(), 1);
        TestEqual(TEXT("Known group provenance retained"), Read.Groups.Num(), 1);
        if (Read.Groups.Num() == 1)
            TestEqual(TEXT("Unknown key blocks even otherwise unique candidate"), Read.Groups[0].Candidate.Layer, INDEX_NONE);
        TestFalse(TEXT("Unknown key never certifies completeness"), Read.bComplete);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipPathReviewAdmission,
    "EngineWire.OwnershipOverrideReview.AdmissionLimits",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipPathReviewAdmission::RunTest(const FString& Parameters)
{
    for (int32 Form = 0; Form < 7; ++Form)
    {
        FOverrideChainRead Chain = ReviewFixture();
        if (Form == 0) Chain.bAccepted = false;
        else if (Form == 1) Chain.Stop = EChainStop::Cycle;
        else if (Form == 2) Chain.Layers.Reset();
        else if (Form == 3) Chain = ReviewFixture(9);
        else if (Form == 4) Chain.Layers[1].Depth = 0;
        else if (Form == 5) Chain.Layers[1].Own.bAccepted = false;
        else
            for (int32 I = 0; I < 129; ++I) Chain.Layers[0].Own.Records.Add(ReviewRecord());
        const FOverridePathReview Read = ReviewOverridePathCandidates(Chain);
        TestFalse(TEXT("Invalid input rejected before review output"), Read.bReviewed);
        TestTrue(TEXT("No candidates emitted from invalid input"), Read.Groups.IsEmpty());
        TestTrue(TEXT("Invalid input has explicit reason"), !Read.Error.IsEmpty());
        TestFalse(TEXT("Invalid input never certifies native identity"), Read.bEngineIdentityVerified);
    }
    FOverrideChainRead Boundary = ReviewFixture(8);
    for (int32 I = 0; I < 128; ++I) Boundary.Layers[0].Own.Records.Add(ReviewRecord());
    TestTrue(TEXT("8 layers and 128 records are admitted as bounded DTO input"), ReviewOverridePathCandidates(Boundary).bReviewed);
    FOverrideChainRead TooMuchText = ReviewFixture();
    FOverrideRead Long = ReviewRecord();
    Long.KeyOwner.Path = FString::ChrN(240000, TCHAR('x'));
    TooMuchText.Layers[0].Own.Records.Add(Long);
    TestTrue(TEXT("Exact owner text budget accepted for DTO review only"), ReviewOverridePathCandidates(TooMuchText).bReviewed);
    TooMuchText.Layers[0].Own.Records.Reset();
    Long.KeyOwner.Path = FString::ChrN(240001, TCHAR('x'));
    TooMuchText.Layers[0].Own.Records.Add(MoveTemp(Long));
    TestFalse(TEXT("Owner text budget overflow rejected"), ReviewOverridePathCandidates(TooMuchText).bReviewed);
    return true;
}
#endif
