# Ограниченная числовая проверка damage Blueprint

По отдельному разрешению **«Проверить числовые функции»** в edit mode на `/Game/ThirdPerson/Lvl_ThirdPerson` проверены только две функции `/Game/BeholderPrototype/Damage/BP_BeholderDamageSnapshot`.

## Результат

**174/174 direct cases OK**, `passed=true`, `running=false`, edit mode подтверждён после завершения:

- 18 cases `EvaluateLegDamageSnapshot`;
- 156 cases `EvaluateDamageSnapshot`.

Отчёт: `Saved/BeholderDamageNumeric_0c06750a432441b99108be51c3615387.json`. Каждый record содержит описанные входы (нефинитные числа представлены строками), expected/actual named outputs и passed. Отчёт создан в новом UUID-файле, прежние JSON не переписывались.

## Binding

Read-only проверка CDO и `call_method.__doc__`, затем инспекция function-entry pins подтвердили скрытый `__WorldContext` первым аргументом. Попытка передать Blueprint-имена через kwargs была отвергнута Python binder до расчёта: требовался `world_context` (pos 1). После уточнения использован **позиционный tuple `(None, *inputs)`**. Helper smoke вернул `(True, False, False, False, False, 0)` для 100 HP/неактивного melee; это отдельный начальный вызов, не один из 174 recorded cases.

Aggregate inputs идут как восемь HP, восемь MeleeActive, NeutralizationLatched, PreviouslyNeutralized после context. Результаты — tuples длины 6/43 в declared output order; exact bool/int types проверены. Эта binding-находка относится к **данным двум функциям** и не объявляет автоматически проверенными dogleg adapters/другие библиотеки.

## Покрытие

- Helper: HP 0/0.5/50/100/−0.5/100.5/NaN/+Inf/−Inf × active false/true.
- Aggregate: failed count 0…8 × active masks none/all/even × latch false/true × final-neutralized false/true: 108 cases.
- Каждый из восьми слотов отдельно: invalid HP −0.5/100.5/NaN/+Inf/−Inf, остальные HP=100, все melee active: 40 cases.
- Каждый слот отдельно как единственный failed при всех active: 8 cases.
- Проверяются все поля, включая abort/retraction/finish masks, integer failed count, числовой отказ с полным zero/false набором, конфликт final Neutralized с surviving melee, threshold/latch и eye intents.
- MotionAuthorized и GameplayNeutralizedConfirmed оставались false. Сравнение bool/int точное, допуски не увеличивались и не использовались.

Reference в `tools/check_beholder_damage_numeric.py` — самостоятельные простые Python predicates/суммирование, не вызовы graph generator, Python policy или ledger. Это не проверка выполнения полного утверждённого gameplay-протокола.

## Что не выполнялось / не подтверждено

PIE/симуляция/движение, actor enumeration/commands, повреждение здоровья, hit-window stop, риг/ретракция, главный глаз и антимагия фактически не управлялись. Скрипт не создавал/компилировал/сохранял assets или графы; запись касалась только нового отчёта. Отсутствие game world проверялось до/после каждого вызова; это не atomic editor lock.

Python policy/ledger, prepared 13 damage tests, 5 structural-plan tests, 13 reviewer tests, 4 dispatch-guard tests и общий набор **этим шагом не запускались**. Сам graph generator/GUID-preparer не исполнялся. Функции dogleg не вызывались. Не проверялись произвольные типы/коэрсия входов, все представимые float values, native identity/ownership, completion history, gameplay recovery или физическая поддержка.

Источник запуска — opt-in `tools/check_beholder_damage_numeric.py`, без import-time Unreal access/auto-run. `allow_numeric_calls=True` не является самостоятельным разрешением на последующие запуски. Beam-charge переход при нейтрализации остаётся нерешённым; historical observer gate также открыт.
