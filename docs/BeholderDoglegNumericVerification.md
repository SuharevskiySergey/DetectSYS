# Dogleg: ограниченная числовая проверка в редакторе

Дополнительная standalone-проверка после source migration adapters: **8/8 OK** (named binding4 + dispatch guards4) по отдельному разрешению, только fake API. Не расширяет 228 engine cases, не является запуском real enabled adapters. В этом прогоне Unreal/PIE/движения не было.

После этого результата source-only обновлены runtime-adapter источники под named kwargs с world_context=None; **изменённые классы не проверялись запуском**. Не переносить 228/228 с dedicated runner на них. Новые четыре fake named-binding tests подготовлены, но не выполнялись.

Последующий отдельный Python-прогон по разрешению «Проверить Python-контракты»: **17/17 OK** — reviewer13 + dispatch guards4. Это обновляет статус незапущенных tests в описании ниже, не расширяет 228 editor cases и не проверяет реальные enabled adapters. В standalone-прогоне Unreal/PIE/движение не использовались.

По отдельным разрешениям **«Проверить dogleg-функции»** и **«Использовать эти допуски»** выполнен ограниченный numeric run трёх установленных Function Libraries в edit mode, без применения targets.

## Результат

**228/228 recorded cases OK**:

| Функция | Cases |
|---|---:|
| `EvaluateDoglegSegment` | 80 |
| `CalculateDoglegTargets` | 80 |
| `CalculateDoglegSample` | 68 |

Сверены **56 companion groups**: facade outputs против clock при тех же входах и targets при canonical reference Phase. Дополнительно facade targets проверены при **реально возвращённой Phase**. Полное покрытие canonical IDs и submitted plan hash проверено текущим reviewer.

Допуски согласованы **до запуска**: absolute **1e−6**, дополнительный relative **1e−5 только для производных**. Bool и refusal zeros — точно. Допуски не менялись; максимальное абсолютное расхождение всех проверенных numeric fields **2.8389015027663334e−08**.

Отчёт: `Saved/BeholderDoglegNumeric_1aaefde320124c11b27cfbc2333055c1.json`, passed=true/running=false. SHA-256 плана, зафиксированный до сбора:

```text
66e428a0ed6e711265cc755f9e1d83d5f34b83341126513f244afdf1bb707c53
```

## Binding и процедура

Read-only инспекция entry pins всех трёх графов подтвердила declared inputs и `__WorldContext`. Его положение в списке пинов этих библиотек отличается от damage helper; позиционную схему damage автоматически не переносили.

Для clock отдельно подтверждён smoke: `CDO.call_method('EvaluateDoglegSegment', args=(), kwargs=...)` с Python snake_case именами и `world_context=None` вернул `(True, False, 0.0, 0.0, 0.0, False)`. Это отдельный вызов до 228 recorded cases. Затем такой же named-binding подход реально прошёл для targets и facade в рамках плана. Tuple lengths/order — 6/31/35, bool exact, numeric outputs finite.

Runner: `tools/check_beholder_dogleg_numeric.py`. Вызывает только три whitelist libraries через CDO; проверяет отсутствие game world до/после каждого call. При первом per-case расхождении предусмотрен fail-fast с failed report; полный reviewer дополнительно сверяет Phase consistency/companions. Отчёт создаётся в отдельном UUID-файле, прежние результаты не перезаписываются. Уровень: `/Game/ThirdPerson/Lvl_ThirdPerson`, режим редактора.

Plan/reviewer и их reference helpers **реально исполнялись в этом numeric run**. Это supersedes прежнее «текущая версия не исполнялась», но **не является запуском 13 standalone reviewer tests** и не подтверждает все их error branches. Общий набор и другие подготовленные тесты не запускались.

## Что покрыто

- Clock: duration=2, forward/return, elapsed 0/0.5/1/1.5/2 на full phase span и 0/1/2 на span 0.25…0.75; фазовые производные/SegmentComplete.
- Targets: BaseExtension=0.5, обе оси, амплитуды −1/0/+1, Phase=0/0.5/1 и canonical companion phases.
- Facade: полный и внутренний phase span, обе оси; internal span также проверяет −1/0/+1 amplitude. Все возвращаемые extension/stages/joints сверены.
- Refusals: negative/overrun elapsed, duration=0/64, equal/reversed/negative/over-unit phase bounds; BaseExtension=0.25/1, amplitude=±1.5; targets Phase=−0.5/1.5. Facade отдельно получает invalid clock либо invalid targets при допустимых остальных параметрах.
- NumericInputsAccepted/MotionAuthorized и нули отказа; MotionAuthorized=false во всех ответах.

## Что НЕ следует из результата

- Accepted E=0.4/0.9, E=0.59999 с clamp root, minimum-duration/очень короткие spans, float32 adjacent boundaries и NaN/Inf для этих трёх библиотек **не проверены**. Numeric-run не закрывает оставшиеся precision gates.
- Python stateful job/pipeline/session/pose receipt и существующие `NumericBlueprintAdapter`/`NumericSampleAdapter` не создавались/не dispatch-ились. Их старый позиционный binding без явного context **не объявляется рабочим**; dedicated runner не является заменой enabled adapter integration.
- Компиляция/graph edits/PIE/симуляция/actor commands/движение не выполнялись. Assets/уровень этим runner не редактировались. Targets не применялись к лапам, real root/tip/contact не измерялись.
- `review.engineExecutionAuthenticated=false` — намеренная граница самого supplied-data reviewer. Внешний runner фиксирует realEditorCallsPerformed=true для этой процедуры; это не native ownership, actual pose receipt или physical safety certificate.
- Runtime actuator, синхронное применение, native ownership/частичный отказ, силы/трение/ходьба и historical observer gate остаются незакрытыми. Beam-transition при нейтрализации также не решён этим run.

Разрешение было только на эту ограниченную числовую проверку. Повтор/расширение/PIE и motion admission требуют отдельных разрешений; `allow_numeric_calls=True` в исходнике сам по себе их не даёт.
