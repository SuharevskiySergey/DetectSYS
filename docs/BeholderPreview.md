# Просмотр макета и быстрые проверки

## Свободная камера по умолчанию

Для `/Game/ThirdPerson/Lvl_ThirdPerson` назначен отдельный level override `/Game/BeholderPrototype/BP_BeholderPreviewGameMode` с native `SpectatorPawn`. Общий project default `BP_ThirdPersonGameMode` не изменён.

`PlayerStart` и editor viewport расположены над центром `BeholderBody_Demo`: **(-1100, 1600, 1250)**, начальный взгляд вниз. Центр корпуса — (-1100,1600,600); высота камеры выбрана так, чтобы не попасть внутрь оболочки. У существующего level instance `BP_Beh_ShemaTry_Fly` отключён `Auto Possess Player 0`; сам Blueprint и его положение не менялись. Намеренное положение этого летающего прототипа отмечено `mcp.placement.ok`.

Управление стандартного SpectatorPawn: **WASD** — перемещение, **Q/E** — вниз/вверх, мышь — обзор. Для захвата ввода нужно щёлкнуть по окну PIE; Shift+F1 освобождает мышь.

Новый GameMode скомпилирован и сохранён; после повторного запуска PIE проверены фактический SpectatorPawn, стартовая позиция, активный SpectatorPawnMovement и отсутствие блокировки move/look input. Ручная проверка клавиатурного полёта не выполнялась. PIE оставлен запущенным. Исходные настройки для справки записаны в `Saved/BeholderPreviewCamera_before.json`. Изменения карты включают её World Partition external actors; сохранять их вместе с `.umap`.

Дополнительно `tools/verify_beholder_preview_flight.py` проверил **реальное native движение** в PIE через `Pawn.add_movement_input`, без force и без телепорта вместо движения: ±X, ±Y, ±Z. Все шесть направлений прошли; перемещение за короткий probe 67.53…104.70 см, поперечный уход 0. Камера после каждой фазы возвращена к исходной позе, в конце скорость обнулена; исходная позиция (-1100,1600,1250) восстановлена. Отчёт `Saved/BeholderPreviewFlight.json`: passed=true, running=false, poseRestored=true. Это проверка movement input API, **не эмуляция клавиш и не ручная проверка мыши/клавиатуры**. Активы/макет/пауза/time dilation не менялись. Утилита требует уже запущенный unpaused PIE, SpectatorPawn у Player 0 и неподвижную камеру; во время probe нужно отпустить управление. Запуск в editor Python после добавления `tools` в sys.path: `import verify_beholder_preview_flight; verify_beholder_preview_flight.run()`. Повторный быстрый набор: 213/426 успешно; новых standalone-тестов не добавлено.

## Тесты

- `python tools/run_tests.py` — быстрый набор: **213 из 426**, проверен успешно.
- `python tools/run_tests.py --full` — все **426**, сохранены без удаления.
- `python tools/run_tests.py --list` — список выбранных тестов без запуска; совместим с `--full`.

Быстрый набор берёт каждый второй test ID из отсортированного полного discovery. Выбор воспроизводим для неизменного набора, но меняется при добавлении/переименовании тестов и не гарантирует критическое покрытие. Ошибка импорта любого test-модуля завершает runner с ошибкой до фильтрации. Быстрый набор — не замена полной регрессии. Прежняя команда `python -m unittest discover -s tools -p "test_*.py"` продолжает запускать всё.
