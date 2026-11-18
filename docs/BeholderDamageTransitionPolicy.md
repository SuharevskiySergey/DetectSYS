# Правила урона и завершения melee — исходник без исполнения

> Отдельная Blueprint-библиотека stateless subset теперь прошла **174/174 numeric cases** по отдельному разрешению: [BeholderDamageNumericVerification.md](BeholderDamageNumericVerification.md). **Этот Python policy/ledger и его 13 tests не выполнялись** и результат Blueprint на них не переносится.

## Актуальный статус и интерфейс

Source-only provenance уточнение: результат ledger включает `source_snapshot_revision` наряду с subject_identity. Stateless `decide_damage_transition` оставляет revision=None, поскольку не принимает упорядоченную историю. Ledger создаёт новую frozen-копию с принятым revision перед публикацией; прежний decision не мутирует при следующем evaluate. Prepared assertions проверяют это различие; **код и 13 тестов не запускались**. Revision не означает, что решение применено или ещё актуально в native controller: тот должен повторно сверять собственные identity/epoch/revision.

Source-only уточнение missing revision: keyword `snapshot_revision` теперь имеет **невалидный sentinel None**, чтобы его пропуск попадал внутрь guarded evaluate и очищал прежний last_decision через local hold. Раньше signature-level TypeError происходил до hold. Это не optional revision и не автоматическая нумерация: без явного корректного revision решения нет. Подготовлен дополнительный subcase существующего теста; **13 методов и production policy по-прежнему не запускались**. Неизвестные keyword/отсутствие обязательного snapshot остаются Python API errors до входа в метод; тотальной защиты от произвольного ошибочного вызова это изменение не заявляет.

**Вся damage policy и её 13 test methods не импортировались и не выполнялись.** Старые passing counts других подсистем сюда не относятся. Числа 7/9/11/12 далее — история подготовки, не результаты прогонов и не текущий размер модуля.

- `DamageSnapshot(health_percent, active_melee_ids, subject_identity)` требует по восемь значений здоровья/action IDs и тройку world/actor/lifetime.
- `decide_damage_transition` — stateless оценка; caller вручную переносит `drain_commitments` и новые `completed_melee_ids`.
- `DamagePolicyLedger.evaluate(snapshot, snapshot_revision=..., completed_melee_ids=...)` — локальное сохранение completion set/latch и порядка snapshot, без reset/auto-recovery.
- `assess_recovery_eligibility` — отдельная advisory оценка health/combat, не смена состояния ledger/актора.

Указанные методы **не подключены** к Blueprint/health writer/hit windows. Статический просмотр найденных call sites в `tools` не выявил старого constructor без identity или ledger evaluate без revision; это чтение исходников, **не синтаксическая/исполнительная проверка**.

## Описательный сценарий, не выполненный тест

Один supplied subject, revision растёт; IDs `A`/`B` — различные melee actions.

| Снимок/событие | Ожидаемое решение по исходнику |
|---|---|
| rev 10: четыре лапы 0 HP, лапы 4/5 выполняют A/B | Neutralization ещё не запрошена; работоспособные A/B не отбираются для опоры |
| rev 11: лапа 4 получает 0 HP, B остаётся активным | Abort A и safe-retraction intent лапы 4; новых атак нет; B входит в completion set; глаз/антимагия сохраняют текущее состояние |
| rev 12: B отсутствует, completion не передан | Sticky local hold; нельзя считать B завершённым или публиковать final Neutralized |
| Альтернатива rev 12 без предыдущего отказа: B отсутствует, completion B передан | `awaiting_neutralization_effects`; запросы закрыть глаз/отключить антимагию, confirmed flags false |
| rev 13: HP повысились после корректного completion | Empty latch сохраняет запрет новых атак; здоровье не вызывает auto-exit |
| Новый/заменённый active melee после threshold | Отказ и local hold, не автоматическое добавление в drain |
| Другой world/actor/lifetime или повторный revision | Отказ без продвижения ledger cursor |

Альтернативные ветви нельзя выполнять последовательно через один held ledger: подтверждение после ошибки не снимает sticky hold. Вариант, где лапа B сама получает 0 HP, исключает B из ожидания завершения, но **не доказывает фактический stop её hit window**. Во всех случаях beam-charge transition остаётся нерешённым, а final gameplay Neutralized требует остальных native подтверждений.

## Source-only хранение completion set

Snapshot теперь требует immutable тройку `subject_identity=(world_id, actor_instance_id, lifetime_id)`. Ledger связывает её с первым успешно принятым snapshot; смена любого компонента даёт sticky hold до продвижения revision или публикации decision. Передавать один и тот же label вместо instance/lifetime IDs недостаточно: правило формирования/подтверждения identity остаётся задачей будущего native producer. Ручная строковая identity не authentication и не ownership.

Identity также включена в damage decision и recovery assessment для явной привязки выходных данных к supplied subject; это не команда или удостоверение реального актора.

Подготовлен дополнительный test world/actor/lifetime mismatch, обновлены snapshot fixtures и assertions immutable/invalid identity. **Теперь 13 незапущенных damage-test methods; код и тесты не импортировались/не выполнялись.** Старые signatures без subject identity больше не подходят текущему constructor.

Ledger теперь требует keyword `snapshot_revision`: неотрицательный int (не bool), строго больше последнего принятого. Revision должен относиться к сформированному producer-ом snapshot, а не просто увеличиваться на каждый read старых данных. Stale/duplicate/invalid revision даёт sticky local hold без продвижения cursor и без опубликованного decision. Начальный revision может быть любым неотрицательным; пропуски разрешены, но **не являются свидетельством полноты событий в пропущенном окне**. Actor/world identity и authentic native sequence этим не установлены; смена producer требует отдельного согласованного lifetime/handoff, не сброса счётчика на том же ledger.

Prepared tests обновлены под обязательный аргумент и дополнены stale/invalid/gap cases. **Теперь 12 незапущенных test methods; ни ledger/policy, ни тесты не импортировались/не выполнялись.** Встречающиеся ниже counts 11/9/7 описывают предшествующие версии.

Последующий статический разбор: строка/bytes/bytearray/dict вместо коллекции `completed_melee_ids` или `drain_commitments` теперь явно отвергается. Иначе `"x"` мог стать tuple из одного символьного ID и случайно подтвердить действие `x`. Добавлены subcases в существующий prepared test, **число методов остаётся 11; ничего не запускалось**. Это валидация формы входа, не удостоверение completion.

`DamagePolicyLedger` сохраняет предыдущий remaining set внутри одного локального экземпляра, включая пустой tuple после завершения melee. Caller больше не обязан вручную переносить drain commitments между каждым snapshot, если использует ledger. Threshold latch не снимается от повышения HP, исчезновения ID или нового evaluate. Ошибка даёт sticky local hold и очищает last_decision; commitments остаются внутри только для диагностики, решения дальше не публикуются. Reset/recovery transition метода нет.

Ledger **не удостоверяет actor/world/action IDs**, не защищает от создания второго экземпляра или вмешательства в private Python-поля, не является thread lock/native owner. Потеря процесса/пересоздание ledger не восстанавливает историю — будущий gameplay controller обязан владеть lifetime/session. `previously_neutralized` остаётся supplied исходным состоянием; ledger не превращает `awaiting_neutralization_effects` в final Neutralized без engine evidence.

Подготовлены ещё два tests: перенос latch без ручных commitments и отказ пропавшего completion со sticky hold. **В модуле теперь 11 незапущенных методов; production policy/ledger также не импортировались/не выполнялись.** Нет Unreal/PIE/движения, существующие passing counts не применимы.

`tools/beholder_damage_transition_policy.py` — **не импортировавшийся/не выполнявшийся** draft согласованных приоритетов. Он принимает восемь процентов здоровья и восемь supplied IDs активных melee-действий, возвращает только immutable decision DTO. Ни обработчик урона, ни native арбитр, ни остановка поражающих объёмов этим не реализованы.

## Предусмотренная логика

- 0 HP: action этой лапы перечисляется в abort_melee, лапа — в request_safe_retraction; её удар не входит в finish_existing_melee.
- Работоспособный начатый melee сохраняется: locomotion/support preemption эта функция не реализует и не разрешает.
- При пяти отказавших лапах новые атаки запрещаются. Surviving active melee фиксируются как completion set; если они есть, decision содержит `finishing_existing_melee`, иначе `awaiting_neutralization_effects`. Это имена draft policy-результата, не созданные gameplay states. `neutralized` выдаётся только при входном `previously_neutralized=True`, то есть повторяет supplied внешний статус, а не подтверждает его.
- После threshold caller обязан передавать **remaining_melee предыдущего decision**, включая пустой tuple. Новый/заменённый ID работающей лапы отвергается. Исчезновение surviving action из active snapshot **не считается завершением**: требуется явный supplied `completed_melee_ids`. Лапа, упавшая до 0 HP, исключается из ожидания завершения по утверждённому правилу abort; это не подтверждает фактическое выключение её hit window.
- Переданный completion set удерживает neutralization latch даже при последующем повышении HP. `previously_neutralized=True` не позволяет выход по одному здоровью и отвергает surviving active melee. Recovery отделена от этой функции: advisory assessment описан ниже, фактический выход не реализован.

Входы фиксируются как tuple; health/bool/NaN/Inf/oversized int, дубли leg/action commitments и некорректные IDs отвергаются по исходнику. IDs/health не аутентифицированы; caller может ошибиться или сбросить историю, поэтому это не запрет новых ударов в движке. Настоящий owner/epoch и единственный native damage/action writer остаются обязательными.

Source-only уточнение completion: неизвестные/повторённые IDs, completion без существующего commitment set, одновременные active+completed и пропажа работоспособного committed action без receipt отвергаются. Caller должен передавать только новые completion IDs из предыдущего remaining set. Строка completion по-прежнему supplied, не native/authenticated event; отсутствие тайм-аута или recovery здесь намеренно не заменено автоуспехом. **Новая логика не исполнялась/не проверялась**.

## Чего decision не подтверждает

Abort/retraction перечислены как **запросы**, не реальные события. Без подтверждённой отмены атакующий hit window может остаться активным; нулевое HP не доказывает втянутую позу. Не следует применять отказные или отсутствующие данные как команду reset transform. Повторные retraction intents должны обрабатываться будущим controller с собственным ID/revision, а не сбрасывать таймер движения при каждом snapshot.

Decision не выбирает лучи, cooldown, опорную физику или траекторию. Согласованное поведение главного глаза теперь представлено как **source-only intents**: `preserve_current_main_eye_state` во время melee drain; после него `request_close_main_eye` и `request_disable_antimagic`. При отсутствии запроса neutralization все три false, это не команда открыть глаз. Нет таймеров, открытия, смены направления или реального shutdown. Судьба уже идущей beam-зарядки явно оставлена нерешённой, `beamTransitionPolicy='unresolved'` при required neutralization; соответствующий переход не подключён.

`awaiting_neutralization_effects` означает отсутствие ожидаемых supplied melee, **не завершённую стабилизацию тела/закрытие глаза** и не разрешение проигнорировать незаданный beam-переход. Общий gameplay state требует исполнения всех остальных требований. Поля commandsApplied/attacksActuallyStopped/retractionConfirmed/nativeOwnershipConfirmed/mainEyeClosedConfirmed/antimagicDisabledConfirmed/gameplayNeutralizedConfirmed/runtimeReady/motionAuthorized=false даже при supplied previously_neutralized. Повторные eye/retraction intents — не подтверждение повторного исполнения; native controller должен применять их идемпотентно с собственными revisions.

Впоследствии подготовлен `tools/test_beholder_damage_transition_policy.py`: **семь незапущенных test methods** на synthetic snapshots. Предусмотрены 0 HP abort, threshold/drain/latch, missing/new action IDs, повторные/unknown/active completion, новый отказ ранее работоспособной лапы, final Neutralized без auto-recovery и immutable/invalid inputs. Тесты описывают ожидаемую policy, не реальные damage/action events.

**Ни production-модуль, ни тестовый модуль не импортировались/не запускались**; Unreal/PIE/движение не использовались, ассеты не менялись. Прежние passing counts не покрывают новую policy. См. [ownership contract](BeholderLegOwnershipContract.md) и `Task.md` §§6/10.

## Source-only assessment выхода из нейтрализации

`assess_recovery_eligibility` отдельно оценивает утверждённые условия: вне боя и минимум четыре лапы с HP>0. Использует supplied `in_combat`, не придумывает пороги расстояния/потери контакта и не включает регенерацию. HP>0 — критерий ненулевого здоровья, **не подтверждение силовой опоры или полной функциональности повреждённой лапы**.

`healthAndCombatCriteriaMet` обозначает только эти два условия. `eligibleForNativeRecoveryAssessment` дополнительно требует supplied final Neutralized и отсутствия active melee; оно лишь приглашает будущую native-проверку, не является командой выхода. Pending melee drain не становится completed recovery по одному повышению HP. neutralizationExitApplied/nativeStateConfirmed/supportConfirmed/runtimeReady/motionAuthorized=false всегда.

Подготовлены ещё два test methods: 0…8 ненулевых лап × InCombat, отсутствие final Neutralized, противоречивое active melee и неверные bool. **Итого девять методов, ни один не запускался**. Код также не выполнялся. Действительный exit/handoff, открытие глаза, возобновление атак/движения, геометрия/опора и регенерация остаются вне реализации.
