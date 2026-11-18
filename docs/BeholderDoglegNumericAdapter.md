# Draft-адаптер числовых Blueprint-вызовов

**Актуальная real-adapter проверка:** по отдельному разрешению оба настоящих adapters созданы и dispatch-ились в редакторе: **24 samples/36 successful dispatches/4 closed adapters**, два полных числовых цикла yaw/+1 и pitch/−1 на E0.5/half2 по обоим путям. Clock→targets/facade samples совпали, close/hold и отказ dispatch после close прошли. После устранения stale constant-module cache прогон завершился passed=true/running=false. **Не было PIE/акторов/применения поз/движения.** Отчёт и setup failures: [BeholderDoglegAdapterVerification.md](BeholderDoglegAdapterVerification.md). Старые enabled-unverified статусы далее — история; extreme precision/native actuator не проверены.

**Актуальная проверка после миграции:** по отдельному разрешению запущены `test_beholder_dogleg_named_binding` (4) и `test_beholder_dogleg_dispatch_guards` (4): **8/8 OK с первого запуска**. Подтверждены на fake API mapping/layout/whitelist, named backend/facade dispatch, sample ID и существующие re-entry/stale/finally guards. **Реальные enabled adapters в Unreal не запускались**, PIE/движения/общего набора не было. Прежние «четыре новых не запускались» ниже относятся к этапу подготовки.

## Текущая source-only миграция на подтверждённый binding

`NumericBlueprintAdapter`/private backend теперь формируют `call_method(name, args=(), kwargs=...)` с explicit `world_context=None` и подтверждёнными snake_case именами. Общая pure функция `named_numeric_kwargs` принимает только точные whitelisted specs/layouts и tuple нужной длины, повторяет strict scalar checks; mapping хранится в `beholder_dogleg_job_contract.REFLECTED_INPUT_NAMES`. Произвольные kwargs/context caller передать не может.

Encoder знает три сигнатуры, но двухфункциональный backend/dispatcher по-прежнему допускает **только clock и targets**. Facade использует encoder отдельно; никакого авто-переключения протокола не произошло. Pre/post edit-mode/request guards и re-entry/finally сохраняются.

**Изменённые адаптеры не импортировались/не выполнялись; тесты повторно не запускались.** Исторические 17/17 относятся к версии до binding migration; 228 editor cases подтверждают сам подход вызова в отдельном runner, не эти adapter classes. Подготовлены **четыре незапущенных** `test_beholder_dogleg_named_binding.py`: kwargs/layout/whitelist, fake backend preconditions и fake facade dispatch/ID. Fake fixtures не импортируют Unreal и не дают разрешения обходить opt-in в реальном использовании.

**Обновление проверки guards:** по отдельному разрешению выполнены четыре fake-backend dispatch tests вместе с 13 reviewer tests: **17/17 OK**. Re-entry, changed request, backend exception/finally и facade fake-load re-entry подтверждены в этих ограниченных случаях. Настоящий enabled UE adapter/binding, editor mode-change races и физическое применение не проверены; constructor opt-in обходился только в fake fixtures. Подробности: `docs/BeholderDoglegNumericValidationPlan.md`.

Подготовлены, но **не запускались**, четыре fake-backend guard tests в `tools/test_beholder_dogleg_dispatch_guards.py`: nested dispatch сохраняет внешний guard, held/changed request не достигает вызова, backend exception снимает guard с сохранением hold, facade re-entry при fake load не вызывает библиотеку. Fixtures обходят constructor через `__new__` только для подстановки fake API; это не разрешение обходить opt-in в реальном использовании. Нет Unreal import или engine execution.

Source-only: обоим adapters добавлен `_dispatching` guard. Вложенный dispatch отвергается до второго library call и вызывает local pipeline hold; внешний call при возврате должен отказать по request/state predicate. Guard снимает только установивший его dispatch в finally, включая исключения. Это не native Cancel, не thread-safe lock и не отмена уже начатого вызова. **Новые guards не выполнялись/не тестировались**.

Последующее source-only изменение: private backend `call` принимает обязательный `require_current_request`; dispatch передаёт precondition, связанный с конкретными request/spec/backend. Backend повторяет его непосредственно до вызова и после ответа; он отвергает disabled adapter, заменённый backend/pending и иной pipeline state. Это закрывает по исходнику окно загрузки класса без передачи произвольного метода/актора в backend. Callback-precondition — локальная проверка, не permission grant/lock. **Изменение не запускалось и не тестировалось**; enabled UE binding всё ещё не подтверждён.

Source-only усиление после указания **«без тестов»**: backend явно отвергает отсутствие editor subsystem и повторяет edit-mode check непосредственно до/после call_method, а не только до загрузки класса. **Новые проверки не запускались**, enabled binding остаётся непроверенным. Это не атомарный editor lock и не отмена уже выполненного вызова; изменившийся режим означает отказ от принятия ответа.

`tools/beholder_dogleg_numeric_adapter.py` подготовлен после выбора пользователя **«Продолжать без проверок»**. **Исходник не импортировался/не выполнялся**, функцию через него не вызывали. Проверки/PIE/dry-run/компиляция не выполнялись, ассеты не менялись.

## Что предусмотрено в исходнике

- Ленивый Unreal import и явный `allow_numeric_calls=False` по умолчанию. Без отдельного разрешения пользователя передавать true нельзя; сам параметр не является разрешением.
- Привязка к одному `DoglegCalculationPipeline`; вызов только его текущего pending request.
- Allowlist ровно двух library/function пар: `EvaluateDoglegSegment` и `CalculateDoglegTargets`. Запросы не могут выбирать произвольный Blueprint, актор или метод.
- Имена, типы и порядок всех входов/выходов вынесены в `beholder_dogleg_job_contract.py`; исходники уже установленных graph-планов используют тот же layout. **Планы повторно не применялись**, это изменение только Python-источников.
- Ровно один числовой вызов на `dispatch_pending`; нет автоцепочки, Tick, таймеров, игрового времени, применения targets или тестового цикла.
- Проверка отсутствия PIE/game world до обращения к библиотеке; загрузка только её generated class/CDO и отказ от не-Function-Library объекта.
- Строгие имена входов без лишних/повторных полей, bool без coercion, конечные float32-представимые числа без подстановок/зажима. Precision conversion UE bridge пока не проверена.
- Точный tuple требуемой длины либо dict с полным набором именованных выходов; невалидный формат/флаги/числа не заменяются удачным reference-ответом.
- Результат поступает обратно в pipeline с тем же request ID; если pending изменился, ответ отвергается. Исключение сохраняется и вызывает только **local pipeline hold**, не native Cancel.
- `close()` отключает дальнейшие вызовы этого адаптера и очищает локальный расчёт через hold; это не физический stop.

## Что ещё не установлено

Способ отражённого вызова Blueprint Function Library через `get_default_object(...).call_method(...)`, порядок tuple, bool/float representation и возможный hidden world-context parameter **не проверены на этих функциях**. При несовпадении контракт предусматривает отказ, а не перебор догадок о скрытых аргументах. До разрешённой числовой проверки этот код нельзя считать рабочим UE adapter.

Allowlist не является sandbox движка: вызов доверяет, что тела двух библиотек остались согласованными числовыми графами без побочных эффектов. Адаптер не удостоверяет версии ассетов, live geometry, контакт, ownership, physical support, синхронное применение или actual pose.

Возвращаются только новый `CalculationRequest` либо draft `NumericPoseSample`, которые сохраняют motionAuthorized/runtimeReady=false. Адаптер не вызывает PoseReceiptLedger, не пишет stage/joint/transform поля, не запускает Blueprint updater и не разрешает dogleg/IK.

Следующая необходимая проверка — отдельно разрешённое сопоставление binding/signature/числовых результатов двух библиотек без PIE и движения. Общее разрешение «продолжай» и прежнее разрешение только на компиляцию не дают права её запускать. Новые тесты не добавлены и не запускались.
