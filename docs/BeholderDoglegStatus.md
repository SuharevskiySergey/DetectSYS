# Dogleg: актуальное состояние и границы готовности

**Последний шаг без запусков:** составлен [native writer inventory](BeholderNativeWriterInventory.md) по исходникам/документам. Есть direct redistribution transform writers и body/watchdog goal writers вне нового API; Release возвращает parent path, не гарантируя stop. Полнота live/inherited графов **не подтверждена**; guards/поля не устанавливались, тесты/Unreal/PIE не запускались.

**Последняя targeted Python-проверка:** native-contract standalone module прошёл **8/8 OK с первого запуска** по отдельному разрешению. DTO/metadata/local-ledger случаи проверены на synthetic данных, не native engine. Unreal/PIE/pose application/движение/общий набор не запускались; actual pose/ownership/actuator и observer gates остаются открытыми. Прежние восемь-unrun статусы ниже — история.

Source-only apply-intent packet теперь сохраняет явную supplied before-pose и command-state flags для будущей root/tip/contact сверки; native recheck обязателен. Подготовлены assertions сериализации без мутации, **восемь native-contract tests и код не запускались**. Transport/application не реализованы.

Source-only native receipt reviewer дополнительно отвергает reused/regressing after capture для reported no-write rejection. Обновлён prepared test, **восемь native-contract методов не запускались**. Новых Unreal/PIE/движения или passing results нет.

Source-only native-boundary теперь содержит LOCAL pending-intent/receipt ledger. Metadata match останавливается на awaiting_actual_pose_review; следующий begin/repeated receipt запрещены, rejected/partial → sticky local hold, без resume/native calls. **Восемь prepared native-contract tests и код не запускались**. Не native owner/actuator, не motion admission.

Native-boundary: подготовлены **шесть незапущенных** `test_beholder_leg_native_contract.py` на artificial identity/capture/receipt metadata. Код контракта также не исполнялся; это не engine tests/actual pose review и не часть прежних 24 adapter samples. Никаких новых запусков.

Source-only native-boundary дополнен reported receipt outcomes и metadata-only reviewer. Partial/unknown требует native recovery; даже совпавший reported complete commit не подтверждает actual pose и оставляет canContinue/autoRetry/motion=false. **Код/тесты/Unreal не запускались**, настоящий consumer/owner/actuator не реализован. Подробности: [BeholderLegNativeBoundary.md](BeholderLegNativeBoundary.md).

**Последний source-only шаг по выбору пользователя:** подготовлен native-boundary contract `beholder_leg_native_contract.py` — identity/owner evidence/coherent capture/command revision и apply intent из прежнего ApplicationProposal. [Граница и будущие требования](BeholderLegNativeBoundary.md). **Код не выполнялся, тесты/Unreal не запускались**, native owner/capture/actuator не реализованы. Numeric успехи не превращены в motion admission.

**Последняя real integration:** по отдельному разрешению оба numeric adapters проверены в editor mode: **24 samples, 36 successful numeric dispatches, 4 корректных close/reject-after-close**. Совпали clock→targets и facade пути (yaw/+1 и pitch/−1, E0.5/half2). После исправления cached constants setup успешно завершён. [Отчёт и ограничения](BeholderDoglegAdapterVerification.md). Это не pose application/native ownership/PIE/ходьба; extreme precision и historical observer gates открыты. Более старые enabled-unverified статусы ниже — история.

**Последняя targeted проверка после named migration:** binding4 + dispatch guards4, **8/8 OK с первого запуска** по отдельному разрешению. Это fake API, не real enabled adapter integration; Unreal/PIE/движение/общий набор не запускались. Новые mapping/guards теперь имеют ограниченное standalone-покрытие; предыдущие source-only/unrun пометки ниже — история до этого прогона.

**Последнее изменение исходников:** оба numeric adapters переведены на подтверждённые named kwargs/world_context=None, общий encoder закрыт тремя specs, а двухфункциональный backend по-прежнему допускает только clock/targets. **Мигрированные классы не выполнялись и не тестировались**; подготовлены четыре незапущенных named-binding tests. Прежние 17/17 — версия до миграции, 228/228 — dedicated runner, не adapter integration. Без отдельного разрешения новых запусков нет.

**Последняя standalone-проверка:** по отдельному разрешению текущие reviewer (13) и dispatch guards (4) прошли **17/17 OK с первого запуска**. В этом прогоне Unreal-вызовов/PIE/движения/общего набора не было. Прежние «13 reviewer tests/4 guards не запускались» ниже — история. Fake-backend успех не подтверждает настоящий enabled-adapter binding: доработка под named kwargs остаётся отдельным шагом.

**Актуальный результат dogleg:** по отдельным разрешениям на numeric calls и допуски реально проверены clock **80**, targets **80**, facade **68** cases: **228/228 OK**, включая 56 companion groups. Максимальное абсолютное расхождение **2.8389015027663334e−08** при absolute 1e−6/derivative relative 1e−5. [Отчёт, binding и ограничения](BeholderDoglegNumericVerification.md). Current plan/reviewer исполнялись на этих receipts; **13 standalone reviewer tests не запускались**, enabled adapters/stateful execution не проверены. Targets не применялись, PIE/движения/graph edits не было. Предыдущие compilation-only/no-real-receipts записи ниже — история до этого run; extreme precision/geometry/native-ownership/actuator/historical-observer gates по-прежнему открыты.

**Последнее обновление damage:** по отдельному разрешению две damage Blueprint-функции прошли **174/174 реальных numeric cases** в edit mode, без PIE/actor commands/gameplay/движения. [Отчёт и границы](BeholderDamageNumericVerification.md). Это не проверка dogleg-функций, Python damage ledger или native owner; compilation-only/no-calls записи далее — история установки до этого numeric run.

Эта сводка отделяет текущее состояние от хронологических записей в `Task.md` и остальных документах. Она не является разрешением запускать проверки или движение.

## Что установлено в Unreal

Отдельно от dogleg установлена `/Game/BeholderPrototype/Damage/BP_BeholderDamageSnapshot`: `EvaluateLegDamageSnapshot` (31 операция) и `EvaluateDamageSnapshot` (175), обе компилируются, итог **0 ошибок/предупреждений** по отдельному разрешению. **Функции не вызывались**, тесты/PIE не запускались; к gameplay/движению не подключены. Damage graph source plan неидемпотентен, повторно не применять. Пять structural Python tests и сам generator/preparer остаются незапущенными. Подробнее: [BeholderDamageBlueprintPlan.md](BeholderDamageBlueprintPlan.md). Прежние source-only статусы ниже — история подготовки, не актуальный статус ассета.

Папка: `/Game/BeholderPrototype/Telescopic/`.

| Библиотека / функция | Подтверждено | Не подтверждено |
|---|---|---|
| `BP_BeholderDoglegTargets.CalculateDoglegTargets` | Создание, сохранение, компиляция: 0 ошибок/предупреждений | Числовые ответы и UE precision |
| `BP_BeholderDoglegClock.EvaluateDoglegSegment` | Создание, сохранение, компиляция: 0 ошибок/предупреждений | Фаза, производные, границы и отказы при реальных вызовах |
| `BP_BeholderDoglegSample.CalculateDoglegSample` | Создание, сохранение, компиляция: 0 ошибок/предупреждений; граф clock → targets и hidden context links | Фактическое исполнение, отражённый Python binding и ответы |

Все три graph-плана уже установлены и **неидемпотентны**: не применять повторно. Facade связан с двумя числовыми библиотеками внутри своего графа, но не с акторами, Tick или движением. Clock/targets сами не подключены к игровым часам/актуатору.

## Что проверялось в Python

Damage Blueprint plan: `test_beholder_damage_blueprint_plan.py` — **пять подготовленных незапущенных** structural methods, не часть ранее прошедших наборов. Ни генерация плана, ни подготовка batch, ни Unreal compilation этим шагом не выполнялись.

Source-only damage decision от ledger теперь несёт `source_snapshot_revision`; stateless helper оставляет None. Это traceability к supplied snapshot, не подтверждение актуальной native позы/команд. Подготовлены assertions неизменности старого decision; **13 damage tests остаются незапущенными**.

Последующее source-only исправление damage-ledger: missing `snapshot_revision` отвергается внутри evaluate и очищает last_decision через local hold; None не является допустимым revision. Подготовлен subcase в существующем тесте, **13 damage tests не запускались**, нового результата проверки нет.

Текущий damage-policy API и описательный (не выполненный) сценарий 4→5 отказавших лап сведены в начале [BeholderDamageTransitionPolicy.md](BeholderDamageTransitionPolicy.md). В найденных source call sites identity/revision переданы; **это статическое наблюдение, не passing test result**. Текущий размер damage-test модуля — 13 незапущенных методов; меньшие числа в последующих исторических заметках не актуальны.

Актуальная damage-policy source-only версия также требует supplied world/actor/lifetime identity и связывает ledger с первым принятым экземпляром. **Damage-test модуль теперь содержит 13 незапущенных методов**; это отдельные 13, не reviewer-модуль. Никакого нового passing result нет, native identity enforcement не реализован.

Актуальная source-only версия damage-ledger требует strictly increasing `snapshot_revision`; **damage-test модуль теперь содержит 12 незапущенных методов**, не 11. Это только supplied ordering, не подтверждение полноты пропущенных событий/native provenance. Код и тесты не запускались.

Source-only `DamagePolicyLedger` теперь хранит completion set/latch внутри локального lifetime и не публикует решения после ошибки. Добавлены два prepared tests; **damage module содержит 11 незапущенных методов**. Это не native owner и не подтверждённый gameplay state.

Дополнение source-only damage policy: advisory `assess_recovery_eligibility` проверяет вне боя + ≥4 лап с HP>0, не меняя gameplay state. Подготовлены ещё два tests, **damage-test модуль теперь содержит девять незапущенных методов**. Native функциональность/контакт и реальный выход из Neutralized не подтверждаются.

Damage policy: `tools/test_beholder_damage_transition_policy.py` — **семь подготовленных, но незапущенных** methods; production policy также не исполнялась. Это отдельная группа, не часть прежних 24/24, исторических 10/10 или текущих 13 reviewer tests.

**Новые незапущенные проверки адаптеров:** `tools/test_beholder_dogleg_dispatch_guards.py` содержит четыре prepared methods с fake backend/API (re-entry, changed request, exception/finally). Они не запускают opt-in constructors, а вручную создают изолированные fake fixtures через `__new__`. Модуль **не импортировался/не выполнялся**; прежние passing counts его не покрывают, реальный enabled UE binding всё ещё не проверен.

Это отдельные целевые прогоны, **не один общий regression run**:

| Набор | Последний выполненный результат | Границы |
|---|---|---|
| Timing, redistribution harness/cleanup, stage/tick observation: пять модулей | 41/41 OK после исправления AST test harness | Fake actor cleanup и существующие reference/структурные cases, не PIE |
| `test_beholder_dogleg_contracts` + `test_beholder_observer_terminal_faults` | 24/24 OK: 17+7 | Synthetic job/pipeline/session/evidence; fake terminal I/O/teardown. Не native pose или enabled adapter |
| `test_beholder_dogleg_numeric_result_review` | **Исторический 10/10 OK** | До companion comparisons и fingerprint precondition. **Текущие 13 методов не запускались** |

План/reviewer менялись после 10/10: companion cases, межбиблиотечные comparisons, schema/hash, обязательный submitted hash и исключение execution status из fingerprint. Их текущая версия **не имеет результата исполнения**. Нельзя суммировать приведённые passing counts в сертификацию текущего проекта или переносить их на Blueprint.

## Исходники: где находится каждый слой

Damage Blueprint source plan переработан на два тела — общий helper одной лапы и aggregate восьми лап — с source guard ≤200 operations для каждого и подготовкой только полного тела через `prepare_complete_function`. **Ничего не генерировалось/не устанавливалось/не компилировалось**; utility и графы непроверены. Текущий plan interface — `functions`/`installationOrder`, не прежний монолитный `operations`.

Отдельно по выбору **«Подготовить Blueprint-план»** добавлен stateless damage snapshot calculator plan: [BeholderDamageBlueprintPlan.md](BeholderDamageBlueprintPlan.md). **Не установлен, не скомпилирован, не запускался**. Он не переносит ledger/ownership и не подключён к существующим Blueprint.

Последующая source-only защита обоих adapters: `_dispatching` отвергает вложенный `dispatch_pending` и переводит pipeline в sticky local hold. Сброс выполняется в finally только тем dispatch, который установил guard; отклонённый вложенный вызов не снимает guard внешнего. Это не thread lock и не подтверждение отсутствия engine re-entrancy. **Код и проверки не запускались**, прежние default-off результаты не покрывают новые ветви.

Дальнейшее source-only выравнивание guards: двухфункциональный backend требует callback-precondition, который проверяет enabled/backend/pending/state после загрузки CDO непосредственно перед вызовом и после ответа. Facade после ответа теперь также проверяет все эти поля, а не только identity pending. Новые ветви **не выполнялись/не тестировались**. Даже при успешном predicate это не защита от всех re-entrant/thread races и не rollback.

**Последующая source-only правка адаптеров:** edit-mode predicate повторяется непосредственно до/после числового вызова, отсутствие editor subsystem явно отвергается. Facade adapter также повторно проверяет enabled/backend/pending/state после загрузки класса. Эти новые ветви **не запускались и не проверялись**; прежний default-off тест не покрывает enabled-путь. Проверки не являются атомарным lock, не предотвращают абсолютно все re-entrant/state races и не отменяют уже выполненный вызов.

| Слой | Файлы | Назначение |
|---|---|---|
| Job | `tools/beholder_dogleg_job.py`, `tools/beholder_dogleg_job_contract.py` | Immutable segments, reference budgets, clamp-stop guards и layouts |
| Два числовых запроса | `tools/beholder_dogleg_pipeline.py`, `tools/beholder_dogleg_numeric_adapter.py` | Clock → targets; enabled UE adapter не проверен |
| Facade request | `tools/beholder_dogleg_sample_adapter.py` | Отдельный pipeline и default-off adapter; не заменяет старый путь автоматически |
| Supplied evidence | `tools/beholder_dogleg_pose_receipt.py`, `tools/beholder_dogleg_sample_session.py` | Локальный порядок proposal/receipt, не native capture/ownership/application |
| Будущая проверка | `tools/beholder_dogleg_numeric_validation_plan.py`, `tools/beholder_dogleg_numeric_result_review.py` | Plain-data cases и сверка supplied outputs; не runner |

## Что остаётся закрытым для движения

Последующая source-only damage policy выдаёт согласованные eye/antimagic intents, но новый threshold без pending melee теперь обозначен `awaiting_neutralization_effects`, не final Neutralized. Eye/antimagic/gameplay completion flags остаются false, beam-transition policy unresolved. Подготовленные семь damage tests обновлены, **не запускались**; native integration отсутствует.

Source-only damage policy не считает исчезновение активного melee ID завершением: surviving commitment требует явного supplied completion receipt. Это пока только проверка данных, не engine event; фактическое прекращение ударов и реакция 0 HP требуют native подтверждения. Код не запускался.

Согласованные damage/melee precedence отдельно представлены source-only функцией `tools/beholder_damage_transition_policy.py`; [описание](BeholderDamageTransitionPolicy.md). Она **не выполнялась/не тестировалась**, не подключена к actor/controller и не закрывает native ownership/actual cancellation gates.

Контракт недостающего native ownership: [BeholderLegOwnershipContract.md](BeholderLegOwnershipContract.md). По отдельным решениям пользователя 0 HP прерывает удар отказавшей лапы с безопасным втягиванием; порог Neutralized запрещает новые атаки, но позволяет работоспособным лапам завершить уже начатые удары. Текущее состояние главного глаза/антимагии сохраняется до завершения этих ударов, затем требуется закрытие/отключение. Судьба уже идущей beam-зарядки при этом пороге явно **оставлена нерешённой**; beam-переход не подключён. Это требования, **не реализованный арбитр**. Supplied owner_epoch и adapter re-entry guard не заменяют native enforcement.

1. **Текущий reviewer не проверен:** 13 подготовленных standalone-тестов ждут отдельного разрешения. Их успех также не проверит Unreal.
2. **Нет реальных numeric receipts:** binding, hidden context convention, bool/tuple layout и ответы трёх библиотек не проверены вызовами. Компиляция этого не доказывает.
3. **Не определена числовая пригодность UE:** нужны отдельно согласованные допуски, float32 boundary/clamp-root и minimum-duration cases. Нельзя повышать допуски постфактум ради pass.
4. **Исторический observer assertion не объяснён:** исходный failed report был перезаписан. Воспроизведённый multi-Tick/window-cap дефект — отдельное свидетельство, не доказанная причина потерянного отказа. Новое архивирование не восстанавливает потерянные данные.
5. **Нет проверенного актуатора:** отсутствуют удостоверенные native captures, эксклюзивное владение, синхронное применение/подтверждение actual pose и проверенная стратегия частичного отказа.
6. **Нет физической ходьбы:** geometry/reference certificates не заменяют силы, трение, физическую опору, arbitrary terrain или все межлапные коллизии.

Отказные числовые нули — **не команда втягивания**. `MotionAuthorized=false` сохраняется. Local hold не является native Cancel или физическим stop. Hash связывает версию данных при честном caller, но не удостоверяет их происхождение или версию Blueprint assets.

## Порядок дальнейшей работы — не разрешение на запуск

1. Отдельно разрешённая проверка текущего pure-Python reviewer.
2. Отдельно разрешённая инспекция binding и числовые вызовы библиотек в edit mode, без PIE/движения; при несовпадении signature — остановка, не перебор догадок.
3. Сверка реальных ответов по зафиксированному до сбора плану, с согласованными допусками и отдельным рассмотрением deferred precision cases.
4. Только после независимого решения observer/native-application gates обсуждать изолированный актуатор. Числовой успех сам по себе не разрешает его запуск.

При текущем указании **«без тестов»** ни один из этих проверочных этапов не выполняется. Можно продолжать документацию и статический разбор, но не объявлять интеграцию или движение готовыми.

Подробности: [executor plan](BeholderDoglegExecutorPlan.md), [numeric validation plan](BeholderDoglegNumericValidationPlan.md), [contract tests](BeholderDoglegContractTests.md), [observer evidence](BeholderObserverArchiveReview.md).
