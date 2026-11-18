# План будущей числовой проверки — без исполнения

> **Последующая отдельная standalone-проверка:** по разрешению «Проверить Python-контракты» выполнены текущие `test_beholder_dogleg_numeric_result_review` (13) и `test_beholder_dogleg_dispatch_guards` (4): **17/17 OK с первого запуска**. Проверены также refusal/fingerprint/companion cases reviewer и fake-backend re-entry/stale-request/finally guards. В этом прогоне Unreal/PIE/движение/общий набор не запускались. Старые пометки «13 тестов не запускались» ниже — история до этого результата. Это не enabled-adapter binding validation.

> **Актуальное обновление:** текущие plan/reviewer реально исполнялись в отдельно разрешённом editor numeric run: **228/228 cases**, **56 companion groups**, заранее согласованные допуски. [Полный результат и ограничения](BeholderDoglegNumericVerification.md). Три dogleg-функции вызывались, но targets не применялись, PIE/движение не запускались. **13 standalone reviewer tests всё ещё не запускались**; ветви их отказов не считаются покрытыми одним успешным numeric run. Прежние непроверенные статусы ниже — история подготовки.

> **Текущая версия не проверена:** после исторического 10/10 изменены plan/reviewer; подготовлены 13 методов, они не запускались. Актуальная сводка: [BeholderDoglegStatus.md](BeholderDoglegStatus.md). Разделы ниже — история последовательных изменений.

Последующий статический разбор исправил fingerprint projection: case-level `executionPerformed` теперь исключён, как уже были исключены top-level status/execution поля. Ранее SHA-256 вопреки описанию зависел от case status. В существующий тест подготовлен status-invariance assertion и проверка отсутствия мутации плана. Изменение hash для той же source-only версии ожидаемо: старые fingerprints больше не должны приниматься текущим reviewer. **Код и 13 тестов не запускались**, исправление не объявляется проверенным. Входы/ожидания/links по-прежнему включаются в fingerprint; это не удостоверение выполнения.

## Source-only precondition для версии submitted данных

Reviewer теперь требует keyword `submitted_plan_sha256` и сравнивает его с canonical plan **до итерации по records**. Будущий сборщик обязан сохранить этот hash до получения ответов, а не подставлять текущий hash задним числом для старых данных. Подготовлен тест отказа до чтения iterable и обязательности аргумента. **Теперь 13 test methods; новая версия кода и тестов не запускалась.**

Это обнаружение случайного смешивания версий при честном caller, не криптографическое удостоверение происхождения: caller всё ещё может предоставить выдуманные ответы/hash. `engineExecutionAuthenticated=false` сохраняется. Fingerprint также не фиксирует точность UE или неизменность Blueprint assets; разрешение на вызовы не выдано.

## Source-only идентификация версии плана

После явного **«Без запуска»** добавлены `schemaVersion=1` и `plan_fingerprint`: SHA-256 canonical JSON cases/comparisons, включая bindings/inputs/expectations/companion links. Итог reviewer содержит `planSchemaVersion`/`planSha256`, чтобы различать результаты для разных наборов одинакового размера. Подготовлены assertions воспроизводимости и чувствительности к изменению inputs/links в существующих тестах; новых test methods не добавлено.

Hash — не подпись, не provenance engine results и не фиксация версии Blueprint assets/алгоритма reference. Нельзя использовать его как admission. Он вычисляется только при явном вызове helper/reviewer, не при импорте. **Код и обновлённые 12 тестов не запускались**; прежний 10/10 результат всё ещё относится к старой версии.

## Последующее расширение только исходников: companion comparisons

После выбора **«Только исходники»** для каждого accepted facade case добавлены два companion cases: clock с теми же входами и targets с той же геометрией и **canonical Python reference Phase**. `comparisons` явно связывает IDs. Reviewer после полной независимой проверки records дополнительно сравнивает поля facade/clock и facade/targets с теми же явно заданными допусками, без их удвоения; packet сообщает число companion groups. Поэтому два individually-close ответа всё равно могут быть отвергнуты как взаимно несогласованные.

Важно: target companion использует reference Phase, не фактически возвращённый engine float. Это контролируемое reference-input сопоставление, не доказательство идентичного отражённого вызова с returned Phase; отдельная проверка facade targets при supplied Phase сохранена. Происхождение ответов не удостоверяется, engineExecutionAuthenticated и остальные разрешающие флаги остаются false.

Подготовлены два новых test methods для companion inputs/coverage и inter-library mismatch. **Изменённые plan/reviewer и модуль из 12 тестов не запускались**; прежние 10/10 относятся к версии до companion comparisons. Unreal/PIE/движение/ассеты не затронуты.

## Историческая Python-проверка версии до companion comparisons

По отдельному разрешению **«Запустить 10 тестов»** из `tools` выполнено `python -m unittest -v test_beholder_dogleg_numeric_result_review`: **10/10 OK с первого запуска**. Проверены canonical coverage/schema, flags/числа/отказы/допуски, свежесть плана/отсутствие мутации и дополнительная согласованность facade targets с returned Phase на synthetic данных. Предыдущие «не запускались» ниже описывают хронологию подготовки.

Это не исполнение самого плана в редакторе: ни один ответ не получен от Blueprint. Reference fixtures используют тот же Python helper и не являются независимой валидацией математики. Unreal/PIE/движение/компиляция и общий набор не запускались; actual binding/UE float/native pose остаются непроверенными, historical observer gate открыт.

Следующая source-only правка reviewer добавляет **второе** сравнение facade targets с Python dogleg_pose именно при supplied `outputs.Phase`, после исходного сравнения всех полей с reference clock phase. Returned Phase дополнительно обязана находиться в границах сегмента независимо от абсолютного допуска. Это проверка согласованности supplied данных, не доказательство фактической exec-цепочки Blueprint. Подготовлены два теста: independently-close, но взаимно несогласованные phase/joint и выход phase за сегмент при большом допуске. **Всего десять незапущенных test methods** в result-review модуле; reviewer/план/тесты не выполнялись. Между отдельными реальными clock/targets ответами сопоставление пока не реализовано.

Последующий source-only разбор расширил accepted cases: clock/facade с внутренним phase span 0.25…0.75, forward/return, elapsed 0/1/2; facade — обе оси и amplitudes −1/0/+1. Добавлен тест уникальных IDs, полного input layout и покрытия этих combinations. **Теперь подготовлено восемь незапущенных test methods** в result-review модуле, а не семь; ни план, ни тесты не импортировались/не выполнялись. Нулевой amplitude здесь не отменяет clock derivatives: это производные phase, а не суставного угла.

## Подготовленный обработчик supplied results

Подготовлен, **но не импортировался и не запускался**, модуль `tools/test_beholder_dogleg_numeric_result_review.py`: семь test methods для полного synthetic coverage, missing/duplicate/unknown/schema, strict bool/numeric, nonfinite/mismatch, буквальных отказных нулей, explicit tolerances и отсутствия мутации records/плана. Fixtures намеренно используют `_expected` самого обработчика: это проверка протокола, не независимый oracle математики. Прежние 24/24 эти семь новых тестов не покрывают; нового passing result нет.

Добавлен **не импортировавшийся/не запускавшийся** `tools/beholder_dogleg_numeric_result_review.py`. Он сам получает canonical cases из плана и принимает только records `{caseId, outputs}`: ровно один ответ на каждый case, без unknown/duplicate/missing cases, с точным named layout. Reference вычисляется через Python quintic/dogleg_pose, flags сравниваются как bool, отказные числа — с буквальным нулём, принятые числа — с явно переданными finite/nonnegative допусками. Дефолтных допусков и автоподстройки нет.

Это только сверка supplied данных: результирующий packet оставляет engineExecutionAuthenticated/blueprintNumericValidationConfirmed/runtimeReady/motionAuthorized=false. Происхождение ответа и соответствие реальным binding/input этим модулем не подтверждаются; tuple conversion и отдельное межбиблиотечное сопоставление остаются будущей работой. Полное покрытие cases не означает покрытие deferred float32/NaN/physics сценариев. Новый код и тесты не запускались; прежние 24/24 его не покрывают.

По выбору **«Только исходники»** добавлен `tools/beholder_dogleg_numeric_validation_plan.py`. Он подготавливает только plain-data cases для clock, targets и facade; нет Unreal import, adapter, CLI, записи файлов или генерации при импорте. **Модуль не импортировался/не выполнялся; тесты не запускались.**

Покрытие плана: начало/середина/конец clock и обе стороны середины quintic, forward/return, обе оси facade; targets с отрицательной/нулевой/положительной амплитудой и unit phase; конечные некорректные duration/phase/base/amplitude. Clock rejection отдельно проводится через facade; target rejection — через facade с допустимым clock. Фасад не принимает внешний Phase.

План явно ожидает MotionAuthorized=false всегда, а при отказе — NumericInputsAccepted=false и нулевые остальные outputs. Успешные результаты предстоит сравнивать с quintic/dogleg_pose и между тремя реальными библиотеками. Допуски не назначены автоматически: их нужно согласовать до исполнения, с учётом UE precision. Сами reference helpers не независимы от прежней Python-модели.

Это не runner: ни одного результата нет, reflection/hidden __WorldContext не считается решённым. Будущий исполнитель обязан подтвердить signature/context до вызовов, edit-mode без game world и согласованные state-free тела библиотек; при несовпадении — отказ, не перебор binding-догадок. Разрешение на создание исходника не разрешает numeric calls.

NaN/Infinity, float32 соседние значения у границ, минимальные duration, clamp roots и физика оставлены отдельными этапами, не объявлены покрытыми. Существующие passing counts 24/24 к этому плану не относятся. Нет PIE, движения, изменений графов или ассетов; historical observer gate открыт.
