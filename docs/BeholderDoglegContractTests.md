# Целевые standalone-проверки Python-контрактов

## Актуальный результат: 24/24 в двух целевых модулях

По отдельному разрешению **«Запустить 24 теста»** из `tools` выполнено:

```powershell
python -m unittest -v test_beholder_dogleg_contracts test_beholder_observer_terminal_faults
```

**24/24 OK** с первого запуска: 17 contract tests и 7 terminal-fault tests. Теперь проверены также ранние factory guards и полный synthetic session round trip с clamp stops. Предыдущие статусы «два новых не запускались» ниже относятся к истории подготовки, а не текущему результату.

Unreal import/Blueprint-вызовы/PIE/движение/компиляция и общий набор не запускались. Это ограниченная проверка Python с synthetic DTO, fake API и временными файлами, не UE float/native capture/реальное исполнение. Исторический observer gate остаётся открытым.

## Последующее дополнение без запуска

Ещё один source-only шаг: `prepare_job` теперь проверяет finite/range скалярных аргументов до передачи в legacy timing/geometry, чтобы чрезмерно большой int не обходил guards через OverflowError. Диапазоны соответствуют существующему timing-контракту; None остаётся режимом duration fit/отсутствия acceleration limit. Подготовлен `test_factory_rejects_bad_scalars_before_calling_timing` с mock timing и неверными типами/границами. **Изменения не запускались. В модуле теперь 17 методов: 15 ранее прошедших и два новых непроверенных.** Ни полный новый модуль, ни новый factory-код не имеют результата исполнения на этом шаге.

После source-only продолжения добавлен **ещё один, незапущенный** test method `test_full_supplied_evidence_round_trip_with_clamp_stops`: все segments и их начало/середина/конец при E=0.59999, обе оси/знаки; supplied before соответствует предыдущему sample, supplied after — новому; возрастают application/probe/capture revisions, проверяются уникальные IDs, запрет authorization и возврат к исходной позе. В модуле теперь **16 test methods, но подтверждённый результат остаётся только для прежних 15**. Весь изменённый модуль повторно не запускался. Frames и contact в этом сценарии искусственные и постоянные — это не проверка кинематики реального захвата.

По отдельному разрешению **«Добавить и запустить»** добавлен `tools/test_beholder_dogleg_contracts.py` и выполнен из `tools`:

```powershell
python -m unittest -v test_beholder_dogleg_contracts
```

**15/15 OK** с первого запуска и после расширения полного цикла на внутреннюю clamp-границу. 15 — число test methods; дополнительные варианты проверяются через subTest. Другие наборы этим шагом не запускались.

## Покрытие

- Отказ для bool/NaN/Infinity/слишком большого int в `finite`.
- Snapshot tuple для сегментов, frozen job и независимость сериализованного packet.
- Direct-constructor guards типов/параметров/индексов, заниженных maxima, velocity/optional acceleration budgets.
- Отказ при пропущенной внутренней clamp-остановке отдельно на forward и returning половине.
- Полные synthetic facade cycles: pitch/yaw × знак амплитуды × E=0.5/0.59999; начало/середина/конец каждого сегмента, включая обе стороны границ. Сохраняется request ID; обработка ответа не создаёт промежуточные requests.
- Отказ при ошибках flags, производных, phase, completion, stages/joints/extension; missing/extra outputs, неверные bool/float типы, tuple длина, повторный receipt, отдельный clock/targets receipt и пропуск границы. На проверенных ошибках pipeline held, sample/pending очищены.
- Сохранённый двухфункциональный Python-протокол проходит исходный sample.
- Оба адаптера по умолчанию отказывают до Unreal import; enabled-путь не создавался.
- Session: initial sample → supplied before → proposal → supplied after → idle; запрет следующего request до сравнения; отказ по identity/revision/pose/contact/transaction; sticky hold и повторный receipt. Все флаги actualPoseConfirmed/runtimeReady/motionAuthorized остаются false.

## Границы результата

Ответы создаются Python-reference helper, использующим ту же геометрическую модель и quintic, что и validators. Это проверка согласованности протокола и rejection cases, **не независимая числовая валидация Blueprint**.

Pose-evidence — искусственные DTO с произвольными постоянными frame, не engine capture и не подтверждение реального fixed-tip. Полный runtime session round trip, физика, ownership, фактическая поза, I/O/unregister fault branches, UE float и отражённый вызов библиотек не проверены.

Unreal import/Blueprint-вызовы, PIE, движение, компиляция и общий набор не выполнялись. Исторический observer gate остаётся открытым. Прежние надписи «не импортировался/не выполнялся» в хронологии описывают source-only этапы; перечисленные pure Python paths теперь имеют ограниченное standalone-покрытие, но enabled UE adapter остаётся непроверенным.
