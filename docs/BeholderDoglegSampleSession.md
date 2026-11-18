# Локальная последовательность расчёта и supplied pose evidence

**Обновление статуса:** после отдельного разрешения session paths проверены на synthetic DTO в новом standalone contract module, **15/15 OK** суммарно. Реальные captures/actuation/Unreal не проверялись; детали: `BeholderDoglegContractTests.md`. Дальнейшее source-only описание фиксирует исходный этап подготовки.

`tools/beholder_dogleg_sample_session.py` — **не выполненный и не проверенный исходник**. Он связывает facade pipeline и PoseReceiptLedger, не создавая Unreal adapter и не выполняя запросы.

Планируемая последовательность:

1. `begin_sample` возвращает числовой request как данные.
2. `accept_numeric` принимает supplied facade response и использует существующие reference comparisons.
3. `propose` принимает supplied before-evidence и возвращает proposal как данные, **не команду применения**.
4. `compare_after` сравнивает supplied after-evidence через ledger. Только после этого локальная сессия разрешает следующий request.

Пропуск этапа, повторный ответ, изменённый pending или ошибка ведут в sticky local hold и очищают pending/sample через ledger/pipeline. Это не native Cancel, не остановка физики и не thread lock. Отдельно продвигать внутренние pipeline/ledger нельзя; Python private-поля не являются защитой от вмешательства.

Сессия не получает реальные captures и не удостоверяет их происхождение. Успешное сравнение caller-supplied данных оставляет **actualPoseConfirmed/runtimeReady/motionAuthorized=false**. Нет актуатора, ownership, игрового времени, автоматического dispatch, Tick, setters или подключения к акторам. Исторический observer-блокер и необходимость проверенного синхронного исполнения сохраняются.

Новый исходник не импортировался/не выполнялся. Тесты, PIE, dry-run, расчётные функции и компиляция не запускались; ассеты не менялись. Это подготовка протокола, а не доказательство его корректности или готовое движение.
