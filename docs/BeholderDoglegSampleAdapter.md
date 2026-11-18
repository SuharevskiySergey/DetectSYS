# Исходник адаптера single-call фасада

**Последующая отдельно разрешённая real integration:** facade и двухфункциональный adapters прошли **24 numeric samples/36 dispatches**, 4 close/reject-after-close; оба пути совпали для yaw/+1° и pitch/−1°, E0.5/half2. Использован именно настоящий opt-in constructor/Unreal CDO binding, не fake API. Без PIE/акторов/pose application/движения. Подробности/ограничения/setup-cache failures: [BeholderDoglegAdapterVerification.md](BeholderDoglegAdapterVerification.md). Предыдущие «реальный adapter не запускался» — история.

По отдельному разрешению после named-binding migration выполнены 4 новых binding tests + 4 guards: **8/8 OK**. Facade named kwargs и сохранение sample ID проверены на synthetic output/fake API, не реальном engine adapter. Opt-in constructors не создавались, Unreal/PIE/движение не запускались. Ранее незапущенные статусы далее — история.

**Актуальная source-only правка:** facade вызов переведён на `call_method(SAMPLE_FUNCTION, args=(), kwargs=...)` через общий закрытый encoder с world_context=None и подтверждённым mapping. Внешнего Phase нет. Enabled/request/editor/re-entry guards сохранены. Новый adapter **не запускался**, четыре named-binding tests только подготовлены; прежние 17/17 и 228 editor receipts не являются проверкой изменённого класса. Никакого gameplay/движения не подключено.

**Последующая проверка:** четыре dispatch-guard tests + 13 reviewer tests прошли **17/17** по отдельному разрешению. Facade re-entry при fake load отвергнут без library execution и внешний guard корректно снят. Это synthetic fixture, не реальный enabled facade adapter. Его старый positional binding не исправлялся/не проверялся этим прогоном. Unreal/PIE/движение не запускались.

Source-only: `_dispatching` запрещает вложенный facade dispatch. При отказе pipeline locally held; только установивший guard внешний dispatch снимает его в finally. Таким образом вложенный отказ не открывает окно третьего повторного входа во время внешнего вызова. **Логика не проверена исполнением**, не является thread lock/rollback/engine ownership.

Source-only дополнение: после возврата call_method также повторяются enabled/backend/pending/state predicates, не только pending identity. Ответ от отключённого/переведённого в другое состояние adapter не принимается по предусмотренной логике. **Новый код не запускался**, это не отменяет уже выполненный вызов.

Последующая source-only правка без тестов: отсутствие editor subsystem отвергается явно; edit-mode проверяется также непосредственно до/после вызова. После загрузки library повторно проверяются enabled/backend/pending/state, чтобы не вызывать фасад по уже заменённому request. **Новые enabled-path guards не проверены исполнением**, прежние synthetic/default-off результаты их не покрывают. Это не atomic lock, не engine ownership и не rollback.

**Обновление статуса:** по отдельному разрешению добавлены и запущены standalone contract tests, **15/15 OK** в общем новом модуле. Synthetic pipeline и default-off adapter проверены ограниченно; enabled adapter/Unreal binding не выполнялись. См. `BeholderDoglegContractTests.md`. Ниже source-only описание относится к моменту подготовки исходника.

После выбора **«Продолжать без проверок»** подготовлен `tools/beholder_dogleg_sample_adapter.py`. **Не импортировался и не выполнялся**; Unreal-функции, тесты, PIE, dry-run и компиляция на этом шаге не запускались. Ассеты не менялись.

- `DoglegSamplePipeline` выдаёт один request к установленному `CalculateDoglegSample`, без внешнего Phase.
- Обработка общего ответа использует общие reference validators clock и targets: производные, SegmentComplete, диапазоны, компенсацию, stages и joints. При source-only рефакторинге validators отделены от transitions: обработка ответа больше не создаёт искусственные промежуточные clock/targets requests и не переключает pending между ними. Candidate остаётся локальным до завершения обеих проверок; sample публикуется с исходным facade request ID.
- Отдельные clock/targets receipts фасадный pipeline отвергает. Ошибка очищает локальный sample/pending и фиксирует hold; это не native Cancel или физический stop.
- `NumericSampleAdapter` по умолчанию запрещает исполнение; требует отдельного разрешения и явного opt-in. Один dispatch содержит ровно один вызов фасада. Нет fallback к двум библиотекам или перебора hidden-context аргументов.
- Строго проверяются функция/путь/состояние pending, имена и типы восьми входов, 35 выходов, неизменность request после вызова. Unreal import ленивый, доступ только вне PIE.
- Прежний двухфункциональный adapter и его внешний протокол сохранены. Внутренние validators pipeline выделены в общие helpers; это source-only изменение также **не запускалось и не проверялось**. Новый путь не подключён ни к приложению, ни к движению.

Это **не проверенный рабочий адаптер**: CDO reflection, hidden context, tuple representation, UE float и вся новая логика остаются непроверенными. Reference-сравнения в исходнике не означают, что проверки уже выполнены. Допуски унаследованы от draft pipeline, не являются физическим сертификатом.

MotionAuthorized/runtimeReady/actualPoseConfirmed остаются false в выходном DTO. Нет ownership, pose capture, setters, актуатора, Tick, игровых часов или разрешения dogleg/IK. Исторический observer-блокер сохраняется. Allowlist не удостоверяет неизменность тел Blueprint и не является sandbox.
