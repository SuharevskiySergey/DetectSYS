# Native-граница: identity, owner, capture и apply intent

Следующий source-only аудит выявил конкретные места native enforcement: [BeholderNativeWriterInventory.md](BeholderNativeWriterInventory.md). DTO revisions нельзя связать только с новым API, игнорируя direct ApplyRedistribution transforms, body setters и parent handoff. Native fields/guards не создавались; тесты/Unreal не запускались.

## Актуальный результат ограниченной Python-проверки

По отдельному разрешению **«Запустить 8 тестов»** из `tools` выполнено `python -m unittest -v test_beholder_leg_native_contract`: **8/8 OK с первого запуска**. Проверены synthetic identity/owner/stamp coherence, intent serialization/отсутствие мутации, reported outcome/revision checks и local ledger busy/replay/hold. Прежние «не запускались» ниже — история подготовки.

**Unreal/PIE/акторы/применение поз/общий набор не запускались.** Native issuer/producer/consumer, actual pose review и native stop не реализованы/не подтверждены. Fixtures произвольные, не FK/engine evidence; passing result не переводит canContinue/runtimeReady/motionAuthorized в true.

Source-only дополнение intent serialization: пакет теперь включает `suppliedBeforePose` (полную копию существующего PoseEvidence, включая root/tip/contact anchors) и `suppliedBeforeCommandState`, а не только revisions. Consumer не должен восстанавливать отсутствующие anchors из текущей позы и тем самым принимать дрейф за baseline. `nativeGeometryRecheckRequired=true` сохраняет обязанность свежей native-проверки; supplied anchors/flags всё ещё не authentication и не motion grant. `asdict` создаёт отдельные containers, изменение пакета не меняет frozen capture. Подготовлены assertions anchors/отсутствия мутации, **контракт и восемь методов не запускались**.

Source-only уточнение no-write receipt: если доступны оба observed captures, after.capture_sequence должен быть **строго новее**, а after.probe_revision — не меньше before. Неизменность command/application counters при повторно присланном before не считается свежим after. Отсутствующий capture по-прежнему обозначается явно, без выдуманного no-write подтверждения. Prepared rejection test обновлён и дополнен repeated/regressing capture subcases; **восемь тестов и код не запускались**. Это metadata freshness, не доказательство native stop/целей/позы.

## Source-only локальный порядок intent/receipt

`NativeReceiptLedger` привязан к одному supplied subject/owner/epoch и хранит один pending intent. begin возвращает только DATA (`nativeCommandSubmitted=false`). Consumed transaction/sample IDs сохраняются; смена bound identity/owner, повторный/неожиданный receipt или попытка нового begin в busy state дают sticky **local** hold, не native Cancel.

Metadata-correlated applied receipt переводит лишь в `awaiting_actual_pose_review`, сохраняя intent. **Переход обратно в idle/подтверждение actual pose не реализованы.** Новый command или повтор receipt здесь запрещён; closed metadata само по себе не разрешает следующий шаг. Rejected/partial/unknown остаются held, без retry/reset. Наружу выдаётся копия metadata review, не изменяемая внутренняя ссылка.

Это не persistent/native ledger, не аутентификация receipt и не защита от создания второго Python экземпляра. Lifetime native ownership и фактическое stop/rollback остаются вне реализации. Подготовлены ещё два synthetic tests; **теперь восемь незапущенных методов**, код также не импортировался/не выполнялся. Никаких новых запусков/Unreal/PIE/движения не было.

Подготовлен `tools/test_beholder_leg_native_contract.py`: **шесть незапущенных test methods** на synthetic DTO для identity/owner/coherent stamps, intent preconditions, reported complete flags, неверных IDs/revisions, stale rejection/no-write и partial/unknown. Fixtures используют произвольные постоянные root/tip/contact, не FK/native capture. **Ни модуль контракта, ни тесты не импортировались/не выполнялись; Unreal/PIE не запускались.** Прежние числовые и adapter passing counts не покрывают эту границу.

## Source-only дополнение: reported receipt

`NativeApplyReceipt` различает `applied_reported/complete`, `rejected_reported/none` и `partial_failure_reported/partial|unknown`. Для reported commit обязательны coherent before/after captures; для rejected/partial — причина. Unknown нельзя переименовать в no-write rejection, а reported native hold не считается подтверждённым stop. После partial результат требует native recovery, но recovery method здесь отсутствует.

`review_native_receipt_data` только сопоставляет supplied transaction/sample/requested subject. Для reported commit сверяются subject/lifetime/geometry/owner/epoch/claim, required-before command/application/probe counters и ровно +1 command/application со свежими after probe/capture counters. Before capture_sequence может быть новее исходного snapshot, но не старее. Это предложенная metadata semantics, не реально измеренные счётчики.

Для rejected stale request наблюдаемый owner/revision может отличаться от старого intent — это не ошибка корреляции. Если оба observed captures доступны, no-write counters/owner/subject должны оставаться неизменными **между этими наблюдениями**. При отсутствующем capture результат честно сохраняет suppliedNoWriteCountersMatch=None. Не сравниваются сами goals/transforms, нет подтверждения rollback или «цели точно не изменились».

Даже metadata-correlated complete commit оставляет **actualPoseCompared/actualPoseConfirmed/canContinue/autoRetryAllowed/runtimeReady/motionAuthorized=false**. Stage/joint/root/tip/contact admission и actual-pose comparison по-прежнему отсутствуют. Stateless reviewer не предотвращает повторную обработку transaction, не удостоверяет sender и не выполняет transport/commands. **Новый код не импортировался/не выполнялся, тесты/Unreal не запускались.**

По выбору **«Готовить native-контракт»** подготовлен `tools/beholder_leg_native_contract.py`. **Исходник не импортировался/не выполнялся, тесты/Unreal/PIE не запускались.** Native методов/Blueprint assets этим шагом не создано, bindings/setters не подключены.

## Данные предложенного интерфейса

| DTO | Смысл |
|---|---|
| NativeLegIdentity | world instance ID, ID конкретного **leg actor instance**, lifetime ID, слот 0…7 и geometry revision |
| NativeOwnerEvidence | identity той же лапы, owner/controller ID, native epoch и claim revision; **supplied описание**, не grant |
| NativeCaptureRevision | command revision, application revision, probe revision и capture sequence — разные счётчики |
| NativeLegCapture | одинаковые before/after revisions, существующий PoseEvidence и reported flags exclusive owner/quiescent writers/goals match actual |
| NativeApplyIntent | transaction ID прежнего ApplicationProposal, тот же before capture, immutable NumericPoseSample и required-before/expected-next revisions |

`prepare_native_apply_intent` соединяет уже существующий proposal DTO с capture DTO, проверяя совпадение before pose. Никаких API/tool calls нет; intent **не является командой применения**. Его metadata: nativeCommandSubmitted/suppliedEvidenceAuthenticated/actualPoseConfirmed/runtimeReady/motionAuthorized=false. Даже reported flags=true не меняют границу доверия.

В PoseEvidence уже есть root/tip frames, десять stages/sleeve offsets/joint rotations, contact point, claws/eyelid. Не вводятся вторые несогласованные pose-массивы; pose world/actor/owner epoch/geometry и CaptureStamp должны совпадать с внешним native capture. Новый command_revision дополняет старые три счётчика, не подменяя их.

Shape guards NumericPoseSample проверяют неизменяемые tuples/конечность/размеры, **не** FK, budgets, геометрию, доступность позы или происхождение numeric result. CompensatedExtension не ограничен сверху 0.9: компенсация допустимого E=0.9 может слегка превысить этот входной предел; это по-прежнему не допустимый redistribution request.

## Требования к будущему native producer/consumer

1. IDs выдаются для конкретного мира/экземпляра/lifetime, не из label и не Python uuid, выданного за engine identity. Переиспользование слота после recreation не сохраняет claim.
2. Epoch/claim revision выпускает арбитр; все native writers проверяют его. Этот Python DTO не приобретает блокировку.
3. command_revision изменяется при каждом принятом изменении цели/режима/владения, способном повлиять на лапу; application_revision — при реально завершённом связанном pose commit. Native implementation должна определить все writer paths, а не лишь новый dogleg setter.
4. Capture читает owner/geometry/revisions **до и после** всех pose/contact данных. Смена owner/subject/geometry или counters внутри чтения означает отказ, не частичный snapshot. DTO сравнивает supplied данные, но не выполняет это чтение.
5. Reported quiescence означает отсутствие конкурентного/ожидающего writer, не paused game или «случайно не двигалось». Goal-match нельзя утверждать по одним positions: producer должен сравнить реальные принятые команды и updater state.
6. Будущее применение одним native действием повторно проверяет identity/epoch/claim/command/application/probe/geometry и live admission, затем коммитит **все** связанные stage/joint значения. Нельзя отделить проверку в Python от серии независимых setter calls.
7. Предлагаемые expected-next command/application=before+1 относятся к **одному** принятому commit, не к каждому из двадцати полей. Это проект протокола, ещё не существующие переменные/семантика Blueprint.
8. Receipt после commit должен содержать transaction/sample IDs, тот же subject/epoch и свежий coherent after capture, включая actual transforms и контакт. Отказ до commit не изменяет позу/цели и не увеличивает application revision. Partial failure нельзя помечать «applied»; обязательны native failure/hold и запрет auto-retry до согласованного recovery.

DTO не содержит transport, call-by-name или validator фактического применения: source-only receipt reviewer выше сверяет лишь metadata. Нет TTL/lease policy, timeout-transfer, auto-reclaim, rollback, multi-leg atomicity или настройки новых физических допусков. Это не обход historical observer gate и не разрешение dogleg motion после успеха 228 numeric cases/24 adapter samples.

## Отдельные отказы, которые потребуется подтвердить позже

Другой actor/world/lifetime/geometry; чужой owner/epoch; изменённый command revision при прежних positions; mixed capture stamps; stale probe; отложенный ordinary updater; goals не совпадают с actual; неверный sample shape; partial commit; repeated transaction и release с оставшимися активными целями. **Это перечень будущих проверок, не выполненные/добавленные тесты.**

Связанные документы: [ownership](BeholderLegOwnershipContract.md), [supplied pose receipt](BeholderDoglegPoseReceipt.md), [текущий статус](BeholderDoglegStatus.md).
