# Изолированный guard-план после writer inventory

## Последующее создание заготовок

По отдельным разрешениям **«Создать 6 заготовок»** и **«Разрешить автокомпиляцию»** шесть копий созданы/сохранены в `/Game/BeholderPrototype/OwnershipIsolation/`. См. [copy staging receipt](BeholderOwnershipCopyStaging.md). **References/наследование не перепривязаны, guards не установлены**. Пять BP metadata UpToDate/no compile errors; source file hashes совпали до/после. Автокомпиляция была внутренним эффектом duplicate, не отдельным compile/test run. Первоначальные source-only/no-assets статусы ниже — история; planning JSON пока сохраняет прежний snapshot и не служит актуальной картой созданных копий.

## Последняя ограниченная проверка reviewer

По отдельному разрешению **«Запустить 8 тестов»** выполнен только `python -m unittest -v test_beholder_guard_isolation_review` из `tools`: **8/8 OK с первого запуска**. Проверены synthetic malformed/modified manifest cases и текущий JSON draft; в покрытых случаях подтверждены unresolved paths/slots/gates, source/destination protection, required references/boundaries, exact bool flags и отсутствие input mutation. Прежние «не запускались» ниже — история подготовки.

Manifest остаётся **заблокированным планом**: шесть destinations не заданы, slot selection и семь installation gates не решены. Успех тестов не подтверждает engine dependency closure, installed guards, native ownership/stop или готовность установки. Unreal/asset changes/compilation/PIE/motion/full suite не выполнялись. Разрешение относилось только к этому запуску, не к будущим проверкам.

**Source-only проект, не installer и не разрешение на создание/компиляцию/запуск ассетов.** Основание: [live writer inventory](BeholderNativeWriterInventory.md), [ownership](BeholderLegOwnershipContract.md), [native boundary](BeholderLegNativeBoundary.md). Существующие numeric/DTO результаты не подтверждают этот план. Здесь нет новых методов, токенов или motion grants.

## 1. Что изолировать

Source-only усиление reviewer: обязательные parent/component/member/cast reference signatures и guard-boundary labels теперь сверяются с фиксированным минимумом аудита, а не только с непустотой списков. Удаление parent/HeadModule/HeadRig edge, подмена guard на произвольное слово, потеря sphere-center preservation или повторное объявление body slots дают issues. Это проверка полноты **заявленного плана**, не разрешение и не engine proof фактических ссылок. Подготовлены ещё три test methods; **теперь восемь незапущенных tests, reviewer не импортировался/не выполнялся**. Ни JSON validation, ни Unreal не запускались.

Source-only reviewer `tools/beholder_guard_isolation_review.py` принимает уже декодированный dict и возвращает локальные issues, не batch/команды. Проверяет фиксированные source/role, package path syntax, case-insensitive destination collisions с исходниками/другими копиями, missing references/slots и попытку заявить authorization/readiness (включая integer0 вместо false). Все unresolvedInstallationGates остаются issues. `installationReady/Authorized`, execution/motion и native authentication всегда false. **Это не UE dependency/reference validator:** ненулевые списки referenceReview/guardBoundaries сами по себе не подтверждают полноту ссылок или установленные guards; неизвестные существующие destination assets без engine reads выявить нельзя. Prototype v1 допускает только единый targetRole для всех восьми slots; смешанный fixture требует явной версии формата, не скрытой интерпретации.

Подготовлены пять standalone test methods для draft blockers/отсутствия input mutation, protected/duplicate destinations, exact bool, malformed/missing roles и slots/unknown fields. **Код не импортировался/не выполнялся, JSON не валидировался, пять tests не запускались.** Никаких Unreal calls или новых прав на установку.

Машиночитаемый companion: [BeholderGuardIsolationManifest.json](BeholderGuardIsolationManifest.json). Это **planning data only**, не batch tool operations. Source paths записаны явно, destinations=null, полный dependency closure не заявлен, installation/execution/motion=false. Никакой consumer/installer не создан, JSON парсером на этом шаге не запускался.

Перечень разделяет parent-class, component-class, inherited-member и graph-class references: замены одного ChildActorClass недостаточно. Для каждого из восьми body slots выбор isolated BodyLeg/redistribution намеренно **не задан**. Установка должна блокироваться до явного решения, а не автоматически делать все восемь redistribution или оставлять shared defaults. Список referenceReview — требования к проверке ссылок, не доказательство, что скопированный граф уже перепривязан. Не выводить destination names из source и не использовать null как разрешение писать в исходник.

Предлагаемая область — новый отдельный fixture вне текущего level/body. Точные имена ассетов согласовать перед созданием; перечисление ниже — роли, не существующие paths.

| Роль копии | Почему нужна |
|---|---|
| Telescope base | Public setters, private Update/Snap и ApplyExtension принадлежат базе; leaf guard не перехватывает все inherited writers |
| BodyLeg descendant | Probe/checker функции должны адресовать изолированную базу и головку, а не возвращаться cast/call references к shared assets |
| Redistribution descendant | Start/reverse/update/Apply/Cancel/Release и construction/parent Tick должны использовать новую цепочку |
| Head Blueprint + Control Rig | PreForwardsSolve и bone offset writers независимы от leg Tick; shared rig/head не редактировать |
| Body fixture | Восемь default children сейчас BodyLeg. Одна замена redistribution leaf не защищает корпус; любой multi-leg fixture требует собственных child references и orchestration |

Нельзя просто duplicate leaf, добавить guard и объявить shared parent защищённым. Private parent functions и construction продолжают работать в прежней цепочке. Будущая установка должна явно скопировать/перепривязать зависимости и повторно проверить owner class каждого call/variable/cast/parent reference. Фактические reparent semantics и возможность такой операции инструментами ещё не проверены. Не перепривязывать текущий level, не трогать оригинальные ЛАПА5, shared BodyLeg/telescope/head/rig.

Mesh/material data можно оставить read-only shared, если не меняются assets и контролируются runtime component/material writes. Изоляция контроллеров не равна разрешению перегенерировать геометрию.

## 2. Граница доверия

Blueprint bool, supplied owner string, доступ к CDO и совпавшие Python DTO не являются аутентифицированным grant. Нужен движковый арбитр для world/actor-lifetime/slot/geometry и owner generation; механизм хранения/выдачи и транспорт пока **не выбраны/не реализованы**. Этот content-only проект не получает C++ issuer автоматически из слова native. Не добавлять plugin/C++ модуль как скрытую часть данного плана.

До реализации issuer любое новое guard поле лишь prototype interlock. Не называть его secure lock, native authentication или разрешением движения. Все неизвестные/неполные identity/revision данные — отказ до motion writes; нет fallback к parent updater.

## 3. Четыре рубежа enforcement

| Рубеж | Конкретные места из аудита | Требование |
|---|---|---|
| Admission | Все public leg/head setters; Retract до записи mode; head setters до request writes; start/reverse и body batch входы | Проверка конкретного subject/owner/epoch/режима до первого изменения принятой команды; вложенные вызовы сохраняют контекст операции |
| State update | Socket safety, UpdateBend/Joint/Stages, Resolve, Snap, rig callback | Защитить не только конечный transform: запрещённый updater не меняет latent goals/live state и не готовит позднюю запись после handoff |
| Actuator | ApplyExtension, ApplyRedistribution0/5, head rig offsets, eyelid material | Один согласованный owner-контекст и commit boundary для полного набора; никаких успешных receipts между половинами Apply |
| Lifecycle/handoff | Construction/reset-before-tick, Release/state0/parent Tick, recreation, body abort | Старые callbacks/claims/goals не оживают после смены поколения; возврат к ordinary mode только через подтверждённую передачу |

Установка только actuator guard не обеспечивает no-write rejection (раньше меняются goals/state). Только Tick guard пропускает public updater, construction и head rig. Только callback guard не доказывает hold после reset-before-tick. Требуется единый stop/capture design для всех этих путей; не выключать reset/rig Tick вслепую ради прохождения флагов.

## 4. Проект последовательности одного owner-перехода

Ниже смысловые стадии, **не новые Blueprint method names**:

1. Предварительно проверить identity/lifetime/geometry и допустимость перехода по утверждённой action policy. До принятия не уничтожать старую команду и не очищать чужие targets.
2. Сериализовать переход на engine side так, чтобы старый writer не мог примениться между quiescence/capture и выдачей нового grant. Подтвердить остановку/согласование действующих updates и pending callbacks. Просто поставить Python hold или paused game недостаточно.
3. Согласовать цели и actual pose по разрешённой policy без teleport. Сохранённые joint/head overrides и demo state должны получить явное решение; ClearJointBend и SetDemoMode(false) не являются hold. Если нельзя подтвердить безопасное состояние — отказ/blocked recovery, не автоматический Release.
4. Прочитать свежий before capture с revisions до/после: root, десять actual sleeve transforms, joint state, tip, реальные head bones/claws/eyelid, accepted command state и probe/contact provenance. Stage arrays/ClawPosition не заменяют actual transforms.
5. Только после подтверждения перехода выдать новое поколение owner; при revoke/recreate инвалидировать предыдущие pending intents. Не выполнять смену owner полусерией Python setters. Failure в середине перехода — unknown/partial, не fabricated no-write.

Точная engine critical-section/scheduler реализация и восстановление после partial ещё открыты. Эти пункты не утверждают существующую atomicity.

## 5. Commands, applications и измерения — раздельно

- command revision относится к принятому изменению целей/режима/владения. Старые leaf/head/body команды тоже должны учитываться, не только dogleg.
- application revision относится к согласованному фактическому применению позы. Запись goal, update counter или завершённый numeric call не increment successful pose commit.
- probe revision учитывает measurement/derived-plan mutations и их происхождение. Public SolveStraightPlaneTarget с supplied числами не получает статус свежего trace.
- capture sequence обозначает согласованный свежий снимок, не число вызовов helper. Повторный probe внутри EvaluateFootprint не становится тем же immutable capture, что предыдущий CheckApproach.
- Legacy diagnostics могут меняться при rejected motion request. Это должно отражаться отдельно; не выдавать «no writes anywhere» по одному Accepted=false. Обычные motion goals/current owner при admission rejection не меняются.
- Один complete dogleg intent ожидает +1 command/application согласно текущему DTO. Если будущая engine семантика другая, требуется явная версия контракта и миграция, не подгонка counters/telemetry под reviewer.

## 6. Multi-leg корпус: нельзя обойти leaf rejection

Перед четырьмя goals сначала claim всех нужных subjects в фиксированном порядке с безопасным освобождением только собственных предварительных claims при отказе. До полного admission не выдавать ни одного goal. Затем фиксировать результат каждой команды; silent void setters и общий accepted flag этого не обеспечивают.

Body Abort сейчас ставит state3 до четырёх Hold. Новый orchestrator не должен объявлять four-leg stop, если часть guards отказала/часть targets изменилась. Hold должен читать и писать один bound subject, а не независимые Component/Index без сверки. Failure требует per-leg outcome и запрета автоматического retry/handoff; физическая остановка подтверждается отдельно.

Watch startup сейчас идёт после accepted=true, Release лишь выключает watch. В новом fixture необходимо различать request admitted, batch submitted, watch established, pose applied, actual pose reviewed и physical support. Нельзя переименовать существующий accepted/state6 в подтверждение этих стадий.

## 7. Что не менять в policy

0 HP прерывает melee этой лапы и запрашивает безопасное втягивание без teleport. Neutralization запрещает новые атаки, но даёт работоспособным лапам закончить уже начатое melee; main eye/antimagic сохраняются до окончания drain. Обычный support request не прерывает начатое melee. Не добавлять числовой priority, отменяющий эти правила.

Beam-charge policy при neutralization остаётся неопределённой: не выбирать last shot/cancel/cooldown. Claim/stop-архитектура не даёт права реализовать gameplay policy за пользователя.

## 8. Этапы и отдельные разрешения

1. **Сейчас:** только этот source-only план и документация. Не создан installer; нет imports/tests/Unreal calls на этом шаге.
2. Перед asset work: согласовать engine issuer/transport boundary, exact isolated assets/dependency closure и перечень разрешённых операций. Создание/перепривязка/компиляция не означают разрешение исполнять функции.
3. После отдельного разрешения подготовить/установить только agreed non-motion interlocks; проверить ссылки и compilation отдельно, не переустанавливать существующие non-idempotent graph plans.
4. Synthetic contract tests, editor no-motion scenarios, pose application, PIE/motion — отдельные scopes разрешений. Список требований не является командой запускать их.
5. Dogleg movement остаётся закрытым: native ownership/capture/actual-pose/recovery, observer gate, precision gaps и физическая поддержка не закрыты этим документом.

**Итог:** определена область изоляции и enforcement, но runtime guard/issuer/actuator отсутствуют. Никаких заявлений о canContinue/runtimeReady/motionAuthorized=true.
