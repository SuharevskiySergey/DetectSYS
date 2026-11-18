#include "Domains/Blueprint/Queries/McpBPOwnershipSCSWalkOuter.h"
#include "Domains/Blueprint/Queries/McpBPOwnershipSCSWalkGuards.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "UObject/ObjectHandleDefines.h"

namespace
{
using namespace McpBPOwnershipBindingReader;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkOuterDefaults,
    "EngineWire.OwnershipSCSWalkOuter.Defaults",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkOuterDefaults::RunTest(const FString& Parameters)
{
    const FSCSWalkOuterRead Read;
    TestFalse(TEXT("Not accepted by default"), Read.bAccepted);
    TestTrue(TEXT("Not started"), Read.Stop == ESCSWalkOuterStop::NotStarted);
    TestNull(TEXT("No borrowed outer"), Read.Outer);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMcpOwnershipSCSWalkOuterConfiguration,
    "EngineWire.OwnershipSCSWalkOuter.ConfigurationRefusal",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMcpOwnershipSCSWalkOuterConfiguration::RunTest(const FString& Parameters)
{
    AddInfo(FString::Printf(TEXT("Outer gate compiled macros: LATE_RESOLVE=%d REMOTE=%d EDITORONLY_DATA=%d"),
        int32(UE_WITH_OBJECT_HANDLE_LATE_RESOLVE), int32(UE_WITH_REMOTE_OBJECT_HANDLE), int32(WITH_EDITORONLY_DATA)));
    FSCSWalkBudget Budget;
    FSCSWalkGuards Guards(Budget);
    const FSCSWalkOuterRead Read = ReadSCSWalkOuter(nullptr, Guards);
    TestFalse(TEXT("Null cannot produce admitted outer"), Read.bAccepted);
    TestNull(TEXT("No returned identity"), Read.Outer);
#if UE_WITH_OBJECT_HANDLE_LATE_RESOLVE || UE_WITH_REMOTE_OBJECT_HANDLE
    TestFalse(TEXT("Unsupported macro combination closed"), IsSCSWalkOuterStorageSupported());
    TestTrue(TEXT("Config refusal before null input check"), Read.Stop == ESCSWalkOuterStop::UnsupportedConfiguration);
#else
    TestTrue(TEXT("Both features disabled admits storage configuration only"), IsSCSWalkOuterStorageSupported());
    TestTrue(TEXT("Supported config still refuses null object"), Read.Stop == ESCSWalkOuterStop::NullInput);
#endif
    TestEqual(TEXT("No strong refs acquired"), Guards.GetCount(), 0);
    TestEqual(TEXT("No guard budget consumed"), Budget.GetGuards(), 0);
    TestTrue(TEXT("Outer refusal leaves guard mechanism uncalled"), Guards.GetStop() == ESCSWalkGuardStop::None);
    // Arithmetic stop must not turn unsupported/null input into an observation.
    TestFalse(TEXT("Stop shared budget without object access"), Budget.ReserveText(-1));
    const FSCSWalkOuterRead Again = ReadSCSWalkOuter(nullptr, Guards);
    TestFalse(TEXT("Stopped budget cannot admit null"), Again.bAccepted);
    TestTrue(TEXT("Same outer refusal reason"), Again.Stop == Read.Stop);
    TestTrue(TEXT("No guard method called after budget stop"), Guards.GetStop() == ESCSWalkGuardStop::None);
    TestEqual(TEXT("Still no acquired ref"), Guards.GetCount(), 0);
    // Reports THIS test TU's flags and checks agreement with compiled gate;
    // does not authenticate all engine DLL flags or exercise a non-null outer.
    return true;
}
#endif
