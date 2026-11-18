# Статический разбор сохранённых observer-отчётов

## Актуальная разрешённая проверка terminal faults

По отдельному разрешению **«Запустить 24 теста»** выполнены `test_beholder_dogleg_contracts` и `test_beholder_observer_terminal_faults`: **24/24 OK**, в том числе все **семь** ранее незапущенных terminal-fault tests. Подтверждены на fake API/временных файлах проверенные ветви archive collision/create failure/rolling failure, сохранение primary error при persistence/unregister failure, inert retained tick и отказ running/NaN report. Production observer не запускался, настоящие сбои Unreal/диска не моделируют всю среду; native stop и освобождение callback не сертифицированы. Исходные JSON и ассеты не менялись. Прежние «не запускались» ниже описывают хронологию.

## Подготовленные, но не запущенные terminal-fault тесты

После следующего явного выбора **«Без запуска»** модуль расширен ещё двумя test methods: archive creation PermissionError с сохранением прежнего rolling report и primary observer error вместе с secondary unregister failure (проверка отдельного traceback, единственного Cancel и одинакового terminal archive). Итого подготовлено **семь**, но **ни один из семи не запускался**. Production observer не менялся. Прежние пять ниже — исходный этап подготовки, не результат исполнения.

После выбора **«Продолжать только исходники»** добавлен `tools/test_beholder_observer_terminal_faults.py`: пять новых test methods для archive collision, rolling-write failure после архива, исходной ошибки вместе с persistence error, unregister failure/inert retained tick и отказа от running/NaN report. Функции извлекаются через AST; используются fake actor/API и временные файлы. **Новый модуль не импортировался и не запускался**. Эти сценарии не входят в прежние 41/41 и 15/15; изменение общего числа обнаруживаемых тестов не означает новый passing result. Разрешения на Unreal-вызовы/PIE/движение нет.

## Последующая разрешённая standalone-проверка

После отдельного выбора **«Запустить целевые тесты»** выполнено:

```powershell
python -m unittest -v test_beholder_dogleg_timing test_exercise_beholder_redistribution test_beholder_observer_failure_cleanup test_beholder_stage_observation test_beholder_tick_observation
```

Рабочая директория: `tools`. Первый прогон: 38 успешных, 2 failures и 1 error — cleanup-test извлекал только `finish`, не включив новый `write_terminal_report`. Исправлена именно тестовая обвязка: она исполняет оба AST-извлечённых определения без Unreal import и проверяет настоящий rolling/UUID archive во временной директории. Повтор того же набора: **41/41 OK**. Новых test methods не добавлено.

Этот результат покрывает существующие timing/observer cases и запись архивов на fake-actor cleanup paths, но **не** новые job/session/adapter, UE reflection/float, I/O failure/collision/unregister-failure branches или живой native controller. Общий набор, PIE, редакторные функции и движение не запускались. Исторический assertion остаётся необъяснённым. Ниже source-only статусы описывают предшествующие этапы, не отменяя этой ограниченной проверки.

Новых прогонов не выполнялось. Прочитаны существующие документы и JSON; observer, тесты, PIE и Unreal-функции не запускались.

## Что позволяют утверждать имеющиеся данные

- `docs/BeholderBodyPrototype.md`, раздел диагностики единичного assertion, фиксирует потерю первоначального failed report после повторного прогона. Его traceback и снимки нельзя восстановить из успешных повторов.
- `Saved/BeholderObserverGapBeforeNativeTelemetry_20261114.json` относится к **другому, контролируемому** сценарию: requestedSkippedReturnObservations=2, пропущены updates 7/8; return timing содержит nativeUpdates=9, skippedNativeUpdates=2, maximumObservedWindowSeconds≈0.045, maximumStageDelta≈0.03 при cap=0.01. Исходный результат passed=false.
- `Saved/BeholderObserverSkippedReturn_verified_20261114.json` сохраняет sourceReportPassed=false, nativeUpdateSpan=3, singleUpdateCapObservable=false и held state=3/reason=5. Его passed=true относится к проверке отмены/удержания, а не к успешности исходного движения.

Следовательно, ошибку сравнения многотикового окна с однотиковым cap удалось воспроизвести исторически, но причинная связь с первоначальным потерянным assertion **не установлена**. Закрывать historical gate нельзя.

## Source-only предотвращение дальнейшей потери terminal evidence

В `tools/exercise_beholder_redistribution.py` добавлен `write_terminal_report`: после running=false записывает отдельный файл `<stem>_Archive_<uuid>.json` через exclusive create (`x`), затем обновляет прежний rolling report. Путь архива включён в оба снимка. Сохраняются и успешные, и failed terminal reports, включая setup failure; у setup failure теперь сохраняется traceback. Ошибки JSON/archive I/O не подавляются. Callback unregister теперь предпринимается **до записи** и его результат включается в terminal report; прежняя native cleanup-логика до записи сохранена.

Это **неисполненное/непроверенное изменение**. Оно не восстанавливает потерянный отчёт, не защищает от внешнего удаления/редактирования, аварийного обрыва записи или падения процесса до finish. При archive I/O error прежний rolling report может остаться running=true; это не успех. Существующие JSON не переписывались и не архивировались этим шагом. Native guards, telemetry, допуски и движение не изменялись. Любой будущий прогон по-прежнему требует отдельного разрешения.

## Последующий статический разбор ошибок завершения

В исходнике обнаружен путь повторного `finish`: исключение его записи возвращалось во внешний callback handler, который снова вызывал `finish(exc)`. Добавлен sticky `finishing` до cleanup; внешний handler теперь не повторяет завершение, если оно уже началось. Это предотвращение повторных cleanup/archive попыток по структуре кода, **не подтверждённый прогоном результат**.

При совпадении основной ошибки и ошибки записи setup/terminal report основная ошибка повторно выбрасывается с её traceback, а persistence error остаётся в exception chain. Native cleanup traceback и ошибки restore_pause/restore_fault_input/restore_time_dilation сохраняются отдельно, не подменяя исходный отказ. Для traceback используется сам exception object, а не только текущий except-контекст. Если ошибка возникла уже на finish, она тоже получает traceback; программно созданный AssertionError может не иметь stack frames.

I/O failure всё ещё может оставить незавершённый/неполный файл; устойчивость к сбоям файловой системы/движка не доказана. Observer, тесты, fault injection, PIE и функции не запускались; существующие отчёты и ассеты не менялись.

## Source-only учёт unregister failure

В следующей правке снятие callback перенесено перед записью terminal report. Исключение unregister сохраняется в `finishErrors` с traceback и `callbackUnregistered=false`; оно делает результат failed, даже если основная последовательность завершилась без ошибки. Исходный отказ не заменяется вторичной ошибкой unregister. При успешном возврате API записывается `callbackUnregistered=true` — это не независимая проверка состояния движка.

Если движок сохранил callback после ошибки unregister, его дальнейшие вызовы немедленно возвращаются по sticky `finishing`, без чтения акторов и повторных cleanup/archive. Это не освобождение callback и не физическая остановка; удержанный engine handle может потребовать отдельной очистки. Native cleanup выполняется по прежнему условию ошибки наблюдателя; эти правки не расширяют полномочия Cancel. Новый код также **не запускался/не проверялся**.
