# EvaluateDamageSnapshot — установлен, только компиляция

> **Обновление после отдельного разрешения:** ограниченная реальная numeric-проверка двух функций прошла **174/174 cases** (18 helper + 156 aggregate), без PIE/gameplay/движения. Подробности binding, отчёт и границы: [BeholderDamageNumericVerification.md](BeholderDamageNumericVerification.md). Заголовок и compilation-only описание ниже фиксируют этап установки; numeric-вызовы теперь выполнены только в указанном объёме. Python generator/preparer и пять prepared structural tests по-прежнему не запускались.

## Актуальный статус установки

По отдельному явному разрешению **«Создать и скомпилировать»** создана и сохранена Function Library `/Game/BeholderPrototype/Damage/BP_BeholderDamageSnapshot`:

- `EvaluateLegDamageSnapshot`: отдельная сигнатура и **31 операция** полного тела; UpToDate, 0 ошибок/0 предупреждений.
- `EvaluateDamageSnapshot`: отдельная сигнатура и **175 операций** полного тела, восемь exec-вызовов helper с forwarded `__WorldContext`; итог UpToDate, **0 ошибок/0 предупреждений**. Редактор вставил int→real conversion для численного threshold expression; это не float/runtime validation.

Первый helper batch был отвергнут **до применения операций**: свободные bool-имена в MathExpression трактовались как numbers, вызвав EXPRESSION_INVALID. Тела и Python source plan исправлены на проверенные по read-only function catalog `BooleanAND`, `BooleanOR`, `Not_PreBool`; MathExpression оставлен для числовых predicates. В aggregate только три literal defaults, остальные accepted outputs подключены проводами; reject содержит полный false/zero набор. Повтор helper batch и установка aggregate успешно скомпилированы.

**Ни одна расчётная функция не исполнялась.** Тесты/PIE/dry-run не запускались; к health writer, hit windows, actor controllers, глазу, Tick или движению библиотека не подключена. Это stateless decision subset, не native арбитр и не Python ledger. Numeric behavior/NaN/границы/UE binding остаются непроверенными; MotionAuthorized/GameplayNeutralizedConfirmed=false.

Python generator и GUID-preparer **не импортировались/не выполнялись**: editor operations формировались непосредственно в инструментальном вызове. Пять prepared structural tests обновлены под Boolean nodes и installed metadata, **но не запускались**. Их возможный будущий результат также не заменит реальные function checks.

План `tools/build_beholder_damage_snapshot_graph.py` теперь описывает **уже установленную неидемпотентную работу — не применять повторно**. Исторические «не установлен/не компилировался» далее относятся к этапам подготовки. Разрешение на эту компиляцию не переносится на function execution или gameplay integration.

Source-only уточнение GUID-binding: preparer нормализует 32-hex GUID к uppercase и отвергает совпадающие entry/return/prior-node GUID, включая различие только в регистре. Так ошибочный supplied mapping не подменяет два разных alias одним native узлом. Подготовлены subcases в существующем тесте; **пять методов/генератор/helper не запускались**. Реальное существование, тип и принадлежность GUID конкретному editor graph всё ещё не удостоверяются pure preparer-ом.

Подготовлен `tools/test_beholder_damage_blueprint_plan.py`: **пять незапущенных structural test methods** для двух signatures/dependencies, ≤200 steps/full-body binding, восьми helper calls/context links, отсутствия writer nodes/literal denial flags и отказов preparer. GUID в fixtures выдуманные, используются только для pure string-resolution. **Модуль и генератор/helper не импортировались/не выполнялись**, passing result отсутствует. Даже будущий успех этих тестов не докажет editor pin types, компиляцию или числовое поведение.

## Актуальная source-only структура: два завершённых тела

План переработан без исполнения: `plans()` теперь возвращает `functions` и `installationOrder`, а не один длинный operations list.

1. `EvaluateLegDamageSnapshot`: HealthPercent/MeleeActive → accepted, Failed/AbortMelee/RequestSafeRetraction/FinishExistingMelee и integer FailedContribution. Только локальные числовые predicates, без памяти или setters.
2. `EvaluateDamageSnapshot`: восемь последовательных вызовов helper с forwarded hidden context, затем проверка всех accepted flags, integer sum, consistency и прежние 43 outputs. При отказе любой лапы общий return — false/нулевые outputs, не частичный успех.

Каждое тело предназначено для **одного полного batch**. В исходник `_function_plan` включён отказ при >200 operations; **guard не исполнялся и количество шагов запуском не измерялось**. Helper должен быть отдельно объявлен/установлен/скомпилирован до установки вызывающего тела; актуальный signature/context contract всё ещё требует разрешённой editor-инспекции.

`prepare_complete_function` в `beholder_damage_graph_batches.py` — предпочтительный подготовительный путь: только полный граф ≤200, с actual entry/return GUID. Он ничего не устанавливает. Общий `prepare_next_batch` сохранён как непроверенная utility, но разбивка тела на частично установленные графы **не является рекомендуемым планом установки**. Старый top-level plan interface изменён; старые consumers одного `operations` несовместимы.

**Ни генератор, ни helper подготовки, ни тесты не импортировались/не выполнялись.** Ассет не создан, компиляции/Unreal/PIE/движения не было. Последующие разделы содержат исходный контекст и ограничения; советы о partitioning относятся к прежнему монолитному варианту.

По явному выбору **«Подготовить Blueprint-план»** добавлен `tools/build_beholder_damage_snapshot_graph.py` для будущей isolated Function Library `/Game/BeholderPrototype/Damage/BP_BeholderDamageSnapshot`.

**Генератор не импортировался/не выполнялся. Ассет не создавался, граф не устанавливался/не компилировался; функции/тесты/Unreal/PIE не запускались.**

## Граница первого калькулятора

- 18 входов: восемь HP 0…100, восемь MeleeActive, supplied NeutralizationLatched и PreviouslyNeutralized.
- 43 выхода: accepted/authorization/count/summary и для каждой лапы Failed/AbortMelee/RequestSafeRetraction/FinishExistingMelee.
- Ordered health range predicates, число 0-HP лап и threshold ≥5; supplied latch/final neutralized удерживают запрет новых атак.
- 0 HP исключает active melee этой лапы из surviving finish set и выдаёт abort/retraction intents.
- Surviving melee при required neutralization сохраняет eye/antimagic state; отсутствие surviving melee выдаёт close/disable intents.
- PreviouslyNeutralized вместе с surviving active melee отвергается как противоречивый snapshot.
- При отказе accepted=false и все outputs false/zero. **Отказные нули не являются командой или разрешением атаки.** MotionAuthorized и GameplayNeutralizedConfirmed всегда false. BeamTransitionUnresolved отмечает required neutralization, но не решает судьбу идущих зарядок.

Это **безусловно stateless subset**, не перенос всего Python ledger: нет action IDs, subject identity, revisions, completion receipts, recovery, actor references, damage/hit-window writes, движения, native ownership или восстановления истории. MeleeActive флаги нельзя принимать за удостоверенные события. При утрате supplied latch калькулятор сам прошлое не восстановит; его выходы нельзя подключать к gameplay до native-арбитра.

## Ограничения плана установки

Для новой Function Library потребуется отдельно создать сигнатуру, затем привязать фактические entry/return GUID вместо `$entry`/`$entry_return`. В operations намеренно нет повторного add_function. Внутренние `$id` также требуют корректного сохранения/resolution при нескольких batches.

Source-only подготовлен `tools/beholder_damage_graph_batches.py` / `prepare_next_batch`: возвращает только один список ≤200 операций с entry/return GUID и bindings узлов из ранее подтверждённых операций. Локальные `$id` остаются только для созданных ранее в том же batch узлов; внешние ссылки переводятся в actual GUID/explicit pin fields. Missing bindings, duplicate/reserved aliases, чужой graph и неподдержанные edits отвергаются по исходнику. Original operations копируются, не редактируются.

**Преобразователь не импортировался/не выполнялся и не проверялся**, размер исходного плана не вычислялся запуском генератора. Это не installer: `nextIndexAfterConfirmedSuccess` не означает, что что-либо применено; caller может продвинуть cursor только после подтверждённого успеха editor и сохранить returned nodeIds. После compiler failure/частичного изменения нельзя автоматически повторять batch без read-only инспекции. Между batches возможны временно незавершённые графы; их фактическое сохранение/компиляция требуют отдельной проработки с editor contract.

Перед установкой всё ещё нужен разбор актуального editor contract и MathExpression types/pins/SelectInt/Add_IntInt; сохранённые GUID/bindings сами supplied и не удостоверяются helper-ом. Нельзя применять план к существующей реализации, переносить временные IDs или считать caller cursor историей Unreal. Подготовка исходника не разрешает установку/компиляцию/function execution.

Данный шаг не меняет исходные ЛАПА5, body/leg assets, карту или существующие dogleg-библиотеки. Требования: `Task.md` §§6/8/10; source policy: [BeholderDamageTransitionPolicy.md](BeholderDamageTransitionPolicy.md).
