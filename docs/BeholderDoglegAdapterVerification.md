# Ограниченная интеграционная проверка двух реальных numeric adapters

По отдельному разрешению **«Проверить оба адаптера»** в редакторе UE выполнен `tools/check_beholder_dogleg_adapters.py` с явным opt-in. Это **числовая интеграция**, не native актуатор и не движение.

## Результат

Отчёт: `Saved/BeholderDoglegAdapters_bc45ec6fd9714cadac8f67ecfc1e9dd2.json`.

- passed=true, running=false, editModeConfirmedAfter=true.
- **24 completed numeric samples**, **36 successful direct adapter dispatches**.
- **4 реальных экземпляра adapter** созданы с opt-in и закрыты; dispatch после close отвергнут во всех четырёх случаях.
- Два пути — `NumericBlueprintAdapter` (clock→targets) и `NumericSampleAdapter` (facade) — совпали по sampled numerical fields для каждой из двух конфигураций.
- E=0.5, half-duration=2, два сегмента forward/return. Конфигурации: yaw/+1° и pitch/−1°. На каждом сегменте sample в elapsed=0/duration÷2/duration; обе стороны разворота проверены. Это расписание расчёта, **не двухсекундное проигрывание позы в мире**.

Обычные проверки pipeline использовали прежние abs1e−6/derivative-rel1e−5; они не ослаблялись. Проверены request→targets ordering, отсутствие преждевременного sample после clock, sample ID, idle/pending и возврат phase/stages к исходным значениям. Все result DTO сохраняли actualPoseConfirmed/runtimeReady/motionAuthorized=false.

`close()` отключал adapter, очищал pending/sample и переводил pipeline в sticky local hold. Отвергнутый dispatch после close сохранял исходную hold reason. **Это не физический stop/Cancel**, native pose не существовала в этом тесте.

## Подготовительные ошибки среды

Первая попытка остановилась при импорте **до создания adapters/числовых вызовов**: редактор держал старый `beholder_dogleg_job_contract` без `REFLECTED_INPUT_NAMES`. MCP execution ID: `86E363FE49C80E8AA9D64AA2C36ACC3B`.

Первая явная попытка reload только этого модуля также остановилась до numeric calls: `tools` отсутствовал в текущем sys.path, и importlib не нашёл spec. MCP execution ID: `29A9EC094DF1CF90EFC389AB7118FD54`.

Затем tools path временно добавлен только на время reload **модуля констант**, после чего удалён; actor/gameplay модули не перезагружались. Повтор того же разрешённого сценария завершился успешно, MCP execution ID: `F191F753409F41C7D4E78CBDDA874B40`. Две setup ошибки сохранены в tool diagnostics/`Saved/Temp/MCP_Python`, не выдаются за успешные проверки. Main UUID report создаётся после imports; отдельного numeric-report файла для этих setup failures нет.

Runner сам не подменяет adapter реализацию, не делает автоматический reload/ретраи: обнаруженный cached pre-migration backend отвергается. В успешном run использованы текущие named kwargs и world_context=None.

## Границы

Не было PIE/симуляции, actor enumeration/commands, setters, pose proposal/application/actual capture, native ownership, физики, сохранения/компиляции/редактирования графов. Скрипт записал только отдельный JSON; assets и уровень не редактировались.

Это не запуск общего standalone набора. Damage policy/ledger, Python supplied-pose session/ledger и их подготовленные тесты не выполнялись. Re-entry/state races на настоящем engine здесь не инъецировались; соответствующие fake cases проверялись раньше отдельными тестами.

E=0.4/0.9, clamp roots, малые duration/phase spans, NaN/Inf и все прочие precision cases не добавлялись. Native actuator, actual pose confirmation, physical support и historical observer gate по-прежнему открыты. Создавать или подключать движение на основании числового успеха нельзя. Повтор/расширение проверок требуют нового разрешения.
