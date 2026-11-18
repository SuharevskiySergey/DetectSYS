# Native writer inventory — source-карта и частичная read-only инспекция

## Последняя editor-инспекция: наследование и базовый EventGraph

### Component defaults и конечный head rig writer

Read-only property reads `/Game/BeholderPrototype/BP_Lapa5_Head` подтвердили:

| Property | Default |
|---|---|
| HeadRig.ControlRigClass | `/Game/BeholderPrototype/CR_Lapa5_Head.CR_Lapa5_Head_C` |
| HeadRig.bUpdateRigOnTick | true |
| HeadRig.bResetTransformBeforeTick | true |
| HeadRig.bEnableLazyEvaluation | false |
| HeadMesh.AnimClass | None |

У `/Game/BeholderPrototype/Body/BP_BeholderBody_Test` **все восемь** Leg0…Leg7.ChildActorClass defaults указывают на `/Game/BeholderPrototype/Body/BP_BeholderBodyLeg.BP_BeholderBodyLeg_C`, не redistribution test. Следовательно, будущая защита только в redistribution child не охватит обычный default body. Эти reads не проверяют class/component overrides размещённых level instances и не разрешают заменять их.

`animation_physics.get_control_rig` прочитал `/Game/BeholderPrototype/CR_Lapa5_Head`: 19 nodes, 21 links, 11 hierarchy elements; reported compiled=true — **прочитанное состояние, не новая компиляция**.

- Forwards Solve exec напрямую соединяет RotateClaw0 → RotateClaw1 → RotateClaw2. Это три `RigUnit_OffsetTransformForItem` для bones Circle_004/003/005 с Weight=1 и propagate-to-children=true; собственного owner/epoch gate в этой exec цепочке нет.
- Для каждого Claw control: FloatValue × π/2 → quaternion axis-angle → offset rotation. Translation вычисляется `pivot − rotate(quaternion,pivot)` и поступает в тот же OffsetTransform. Это подтверждает существующую sphere-center pivot compensation; не заменять её старым edge-pivot вариантом.
- Rig graph сам не содержит времени/interpolation: их подаёт ранее прочитанный head Blueprint callback. Но component reset-before-tick и mapped output — часть полного actuator path. Просто перестать задавать новые Control Float не доказывает, что rig перестал писать bones; просто пропустить callback не доказывает сохранение pose после component reset. Требуется согласованный native lifecycle/stop/capture design, не случайное выключение галочек.
- AnimClass=None в defaults исключает назначенный AnimBP именно здесь, но не доказывает отсутствие иных runtime writers/instance overrides. Материал века остаётся отдельным writer в head Blueprint, вне трёх rig bone offsets.

## Сводная граница покрытия после read-only этапа

| Область | Подтверждено | Ещё не подтверждено |
|---|---|---|
| Blueprint bodies | Основные telescope/head/body/redistribution admission/update/application/hold/release/probe/footprint/telemetry цепочки | Поиск всех внешних ссылок, property writes, level-instance overrides/lifecycle |
| Head rig | Класс, graph bone writers, update/reset/lazy defaults, отсутствие default AnimBP | Фактический callback/tick ordering, runtime bone pose, остановка/reset при смене владельца |
| Body children | Восемь default BodyLeg classes | Реальные instances и изоляция будущего fixture |
| Native enforcement | Требования к admission, update, actuator и handoff определены | Issuer/epoch/transport/revisions/coherent capture/atomic apply/actual-pose review **не реализованы** |

Этот этап достаточен для source-only проекта следующего изолированного guard-плана, но **не** для установки guards или движения. Не объявлять exhaustive security/runtime audit завершённым. Никаких tests, gameplay calls, rig solve, compilation, PIE, движения или asset edits не выполнялось.

### Footprint, diagnostic telemetry и construction handoff

Полностью получены body ReadExperimentalFootprintPoint (29 узлов), EvaluateExperimentalFourFootprint (26), CalculateOrderedFourFootprint (34), Construction (1); redistribution CaptureRedistributionNativeStep (21), RecordRedistributionNativeStep (18), Construction (2). Все `hasMore=false`. Только structural inspection.

- **ReadFootprintPoint не просто getter:** validity/cast → ClassifyBodySurfaceCandidate на cached probe flags/geometry → дополнительный complex trace Z±2 около cached ProbePlanePoint → hit/no-overlap/XYZ agreement≤0.05/normalZ>0.99999 → Ready=true и **cached ProbePlanePoint**, а не новый hit point. Нет собственного MeasureSurfaceProbe или variable setters; trace лишь перепроверяет terrain около сохранённой точки. Это не actual-pose capture всех компонентов.
- **EvaluateFourFootprint — measurement writer через вложенный вызов:** первым делом UpdateBodySurfaceProbes (новый reset и восемь измерений), затем settings-valid/count8/**candidate count ровно4**, четыре ReadFootprintPoint, согласованность Z≤0.05 и calculator с порядком0/2/6/4. Поэтому watch/retraction, уже обновившие probes перед CheckApproach, при последующем EvaluateFootprint **измеряют снова**. Проверки approach и footprint используют последовательные обновления, не один stamped immutable capture. Это уточнение предыдущего описания wrappers, а не доказательство runtime race.
- **CalculateOrderedFourFootprint:** только вычисления/ветвления/returns, pose/goal/measurement setters отсутствуют. Проверяет диапазоны входных координат/margin, Vector Is NAN, невырожденность рёбер/площади и одинаковый знак четырёх поворотов (ordered convex polygon). Возвращает XY area и signed minimum edge margin относительно ReferenceWorld; Inside означает margin≥0, PassesMargin — строго margin>required. Это геометрическая XY-проверка supplied четырёх точек, не COM/load/friction или general support controller. Float/edge correctness здесь не исполнялась.
- **CaptureNativeStep:** копирует десять StagePosition в Before0…9; component transforms/bones не читает. **RecordNativeStep:** max abs stage-variable delta → Last, lifetime Maximum/MaximumExcess, sticky Violation при превышении cap+2e-6, sticky Invalid при выходе before/after за диапазон −1e-6…1.000001; сохраняет текущие Updates/Direction и увеличивает Samples. В этих телах нет actuator/goal writes, abort/rollback или owner admission. Слово Native в telemetry name не превращает stage-variable bookkeeping в authenticated native receipt/actual-pose proof. Lifetime maxima/flags не сбрасываются этими функциями.
- **Construction:** body graph пуст, redistribution construction вызывает Parent: Construction Script; это ещё один путь к ранее прочитанному base Snap/Apply через наследование. Component/rig initialization вне пустого body construction этим не исключается. Собственный BodyLeg construction в этом шаге не перечитывался.

На этом основные собственные body function bodies, base telescope и head Blueprint bodies, а также собственные redistribution functions просмотрены структурно. Это **не** exhaustive runtime writer/ownership audit: остаются rig internals/settings, overrides реальных instances/components, внешние property writers и lifecycle/transport/native implementation. Установка guards и новые запуски требуют отдельного согласования.

Новых tests/trace executions/compilation/PIE/движения/asset edits нет. Следующий безопасный шаг — read-only component/rig configuration inventory и сводная матрица coverage, не подключение dogleg к motion.

### Measurement internals: reset, mesh sampling, plane и straight-plan

Read-only получены ResetBodySurfaceProbes (29 узлов), ClassifyBodySurfaceCandidate (6); BodyLeg ResetSurfaceProbe (10), MeasureSurfaceProbe (78), ResetSurfacePlane (7), EvaluateSurfacePlane (69), ResetStraightSurfacePlan (7), PlanStraightSurfaceContact (26), SolveStraightPlaneTarget (16), ConsiderSurfacePoint (7), ConsiderSurfacePlanePoint (11), IsSurfacePointCoherent (10), IsSurfacePoseCoherent (59). Все ответы `hasMore=false`; это чтение installed wiring, не запуск trace/вычисления.

- **ResetBody:** обнуляет counters/settings-valid, Clear→Resize(8) для восьми measurement/candidate arrays. Старые entries не сохраняются при штатном входе через UpdateBodySurfaceProbes. Это диагностическая мутация, не command/application commit.
- **ClassifyBodySurfaceCandidate:** predicate без setters: Valid/Hit/PlaneValid AND диапазоны settings/normal/clearance/verticalGap. Candidate остаётся лишь кандидатом опоры, без нагрузки/friction/ownership.
- **Reset цепочка лапы:** ResetSurfaceProbe инвалидирует valid/hit/overlap, обнуляет lowest/impact/normal/gap → ResetSurfacePlane инвалидирует plane и обнуляет его данные → ResetStraightSurfacePlan инвалидирует plan/reachability и обнуляет outputs. Значит, неуспех после reset не должен интерпретироваться как прошлый успешный sample; consumers обязаны учитывать flags, не только zero outputs.
- **Measure:** первым делом reset, затем IsSurfacePoseCoherent, head/mesh/parent validity, trace settings/scale/socket prerequisites. Собирает геометрический минимум Z из сферического head bound (радиус27 с max abs scale) и двенадцати преобразованных локальных точек трёх claw sockets. ConsiderSurfacePoint обновляет ProbeLowest при меньшем candidate Z. Ignore actors формируется из child actors parent и самого parent. Затем **bProbeValid=true ставится до line trace**. Initial overlap → valid=false/overlap=true; miss оставляет valid=true, hit=false; hit сохраняет impact/normal/gap и вызывает plane evaluation. Поэтому Valid не равно Hit/PlaneValid/Reachable.
- **PoseCoherent:** проверяет наличие HeadMesh и sockets Circle_004/003/005, двенадцать преобразованных точек в ограничивающей сфере вокруг head actor (`81*maxAbsScale`, helper допускает radius+0.01). Point helper содержит Vector Is NAN и radius/distance checks. Это spatial sanity bound, **не** общий временно согласованный snapshot всех stages/root/joints/head и не гарантия native ownership. Поведение NaN/Inf/границ этим чтением не проверялось.
- **EvaluatePlane:** снова reset plane/plan; probe valid/hit/no-overlap → normal length/head/mesh/socket/scale gates → нормализованный impact normal → head sphere support point и signed clearance → двенадцать claw points через ConsiderSurfacePlanePoint (обновляет clearance/point при меньшем signed distance) → plane-valid=true → PlanStraightSurfaceContact. Это оценка относительно плоскости одного trace hit, не полная terrain/manifold или swept collision certification.
- **PlanStraight:** reset → probe flags, settled scalar goal/current, stage-average consistency и нулевые JointMagnitude → cast head/нулевые ClawPosition → uniform positive scale gate → SolveStraightPlaneTarget с projection `1040*scale*dot(forward,planeNormal)`. Собственных leg goal/component transform writes нет, но plan fields меняются.
- **SolveStraightPlaneTarget — public state writer:** снова reset, проверяет current0…1, clearance0…1e7 и |projected| в (1e-6,1e8]; пишет folded/extended clearance, projected stroke, **plan-valid=true до reachability check**. Только если `current-clearance/projected` попадает в0…1, сохраняет target и reachable=true. PlanValid без Reachable не разрешает выдачу цели. Вызов может перезаписать derived plan из supplied numeric аргументов; это не fresh measurement producer и не actuator.

В прочитанных measurement/plan цепочках нет SetLegExtension/Apply/SetRelativeTransform calls: они пишут measurement/plan state, а не явно запускают перемещение. Однако такие writes должны учитываться future probe revision и provenance, особенно public Solve/Plan/Measure inputs: не присваивать им command/application revisions автоматически и не считать flags authenticated captures.

Остаются footprint readers/calculator, rig internals/settings, instance class overrides, telemetry bodies и внешние property/component writers. Native owner/capture/actuator по-прежнему не реализованы. Никаких функций, trace, тестов, compilation, PIE, движения или asset edits.

### Body probes и значения Valid/Folded

Read-only получены полные графы UpdateBodySurfaceProbes (22 узла), SampleBodySurfaceLeg (45), CheckExperimentalApproach (34), CheckExperimentalRetraction (34), InspectExperimentalRetractionLeg (7), IsExperimentalLegFolded (11), InspectExperimentalContactLeg (24), BodyLeg.CheckExperimentalRetractionPose (11); `hasMore=false`. Измерения/trace не запускались.

- **UpdateBodySurfaceProbes:** ResetBodySurfaceProbes → проверка диапазонов body support settings → bBodyProbeSettingsValid → последовательные SampleBodySurfaceLeg для Leg0…7. Невалидные настройки завершают цепочку после reset/settings write. Это public mutation вход для measurement state, не read-only snapshot.
- **SampleBodySurfaceLeg:** Index range/settings → validity Component → cast BodyLeg → **MeasureSurfaceProbe на дочерней лапе** → ClassifyBodySurfaceCandidate → восемь array element writes в body (valid/hit/plane valid/impact point/normal/clearance/gap/candidate) → counters measured/hit/candidate. MeasuredCount растёт при достижении этой цепочки, а не только при bProbeValid=true. Поэтому count8 подтверждает восемь завершённых sampling paths, не восемь валидных контактов. Нет общего capture sequence, owner epoch и pose/application revision для восьми последовательных измерений; существующие counters не заменяют native coherent capture. Reset/Classify/Measure внутренние тела пока не прочитаны здесь полностью.
- **CheckApproach/CheckRetraction:** последовательно проверяют folded верхних 1/3/5/7, затем нижние 0/2/4/6 с сохранёнными targets/planeZ; AND-агрегируют Valid и AtTarget/Folded. Сами эти wrappers не вызывают новое Measure: читают результаты уже вызванных probe paths через helpers.
- **IsExperimentalLegFolded (верхние):** component validity/cast, reject при bAutoDemo=true, затем только |ExtensionPosition| и |ExtensionAmount|≤1e-6. Не читает десять stages, суставы, head pose или actual component transforms. Нельзя переносить этот слабый folded predicate на native stop/retraction acceptance.
- **InspectContactLeg (нижние):** validity/cast → IsExperimentalContactPoseSafe → cached probe valid/hit/plane valid → проверка goal≈target, current в 0…target+epsilon, target 0.05…0.95, clearance≥−0.05 и ≤100000, normalZ>0.99999, impact planeZ≈saved. AtTarget отдельно требует current≈target и |clearance|≤0.05. Собственных setters/Measure нет. Valid допускает незавершённое приближение и не равен наличию опоры непосредственно у лапы.
- **InspectRetractionLeg** только проверяет объект/cast и вызывает BodyLeg.CheckExperimentalRetractionPose с UpperLimit/ExpectedPlaneZ; failure возвращает оба false.
- **CheckRetractionPose (нижние):** Valid объединяет Safe с cached probe flags, goal≈0, current в диапазоне, normal/plane/clearance, stage range0…1 и среднее десяти stages≈ExtensionPosition. Folded отдельно означает ExtensionPosition и все десять StagePosition≈0; **не AND с Valid** внутри helper. Вызывающий watchdog сначала проверяет Valid и лишь затем Folded; при новом consumer нужно сохранить оба условия. Проверка не читает фактические sleeve transforms/mesh bones и не аутентифицирует stop.

Так установлено важное различие: верхний Folded — два scalar поля; нижний Folded — десять stage variables плюс scalar, а Valid — отдельная геометрическая допустимость. Ни одно из них не является authenticated actual pose evidence. Guards не устанавливались; runtime correctness и float/edge cases этим просмотром не проверялись.

Следующие пробелы: Reset/Classify/Measure/plane/straight-plan internals, footprint readers, rig internals/settings, component class overrides, telemetry bodies и внешние writers. Более ранние непокрытые checker lists ниже — история.

### Body multi-leg admission, watch startup и retraction

Read-only полностью прочитаны TryExperimentalFourContact (63 узла), PrepareExperimentalContactLeg (65), StartExperimentalContactWatch (26), BeginExperimentalContactMonitoring (9), TryExperimentalFourRetraction (28), UpdateExperimentalRetractionWatch (28); `hasMore=false`. Traces и функции **не выполнялись**.

- **FourContact entry пишет до admission:** bLastFourContactRequestAccepted=false и LastFourContactTarget0/2/4/6=0 ставятся до enable-check. Затем идут UpdateBodySurfaceProbes, folded checks верхних 1/3/5/7, prepare нижних 0/2/4/6, общий readiness/geometry gate и predicted footprint Valid/Inside/PassesMargin (порядок точек 0/2/6/4). Только после всех gates сохраняются Last targets, последовательно вызываются четыре SetBodyLegExtension, ставится accepted=true и запускается watch. Общего WatchState/owner/epoch gate в самом entry нет; geometry helpers не являются claim. Отказ не означает no-write body/probe receipt.
- **PrepareContactLeg:** validity/cast BodyLeg → bAutoDemo=false, cached straight-plan valid/reachable, нулевые extension current/goal, target 0.05…0.95, направленный вниз projected stroke, straight bend/live requests/socket claw requests → trace в предсказанной точке. Требует hit/no-initial-overlap, XYZ impact difference≤0.05 и normal Z>0.99999. Возвращает Ready/Target/Point; собственных variable setters и вызова leg goal setter в этом helper нет. Это проверка cached plan + endpoint trace, не swept trajectory certification и не owner admission; внутренности первоначального UpdateBodySurfaceProbes ещё не прочитаны.
- **StartWatch после четырёх команд:** обнуляет elapsed/updates/reason, копирует Last targets и margin, сохраняет root transform, ставит WatchState=1; затем проверяет Leg0/cast и сохраняет plane Z. При неуспехе вызывает Abort(reason3), который уже повторно выдаёт четыре Hold goals. Accepted flag перед StartWatch уже true и этот helper его не сбрасывает. Поэтому accepted — факт прохождения request branch/отправки команд, не подтверждение успешного startup watch или принятия всеми детьми. Source wiring не доказывает, что конкретный runtime failure воспроизводится.
- **BeginMonitoring:** разрешает state2/4, ставит state4 → UpdateExperimentalContactWatch(dt=0) → Started по конечному state4. Вызов с нулевым временем всё равно может измерять, менять counters/state и через Abort писать leg goals.
- **FourRetraction:** state2/4+enable+timeout → root check → UpdateBodySurfaceProbes → approach Valid/AtTarget → footprint gate → reset retraction elapsed/updates/reason → четыре **SetBodyLegExtension(0)** → state5 → Accepted=true. Не использует RetractBodyLeg/RetractLeg(Emergency), не меняет sequential mode явно и не получает child receipts. Возврат false после измерений не удостоверяет отсутствие probe writes. До согласованного claim всех лап не считать это atomic safe retraction.
- **RetractionWatch:** только state5; увеличивает updates до enable/time checks, пишет elapsed, сверяет root, обновляет probes и требует settings valid/count8, затем CheckExperimentalRetraction. Valid=false → Abort; Folded=true → state6. Эта completion-метка не native actual-pose/owner receipt, сама функция не останавливает head rig и не делает new-owner handoff.

**Планируемая граница:** отделить диагностические writes, multi-leg claim/admission, выдачу goals, startup watch и completion receipts. Сейчас один accepted bool не кодирует частичный отказ/состояние каждой лапы; подмена silent setters на guarded reject потребует переработки body orchestration, а не только leaf guard. Здесь никакой такой код/граф не устанавливался.

Открыты body check/probe internals, component class overrides, rig settings/internals, lifetime telemetry bodies и внешние writers. Более ранние «body admission/retraction не прочитаны» ниже — история.

### Корпус: live forwarding и watchdog → goal writes

Metadata `/Game/BeholderPrototype/Body/BP_BeholderBody_Test` подтвердили parent Actor и public `SetBodyLegExtension`, `RetractBodyLeg`, `UpdateExperimentalContactWatch`. Полностью прочитаны EventGraph (5 узлов), два forwarding graph (по 34), HoldExperimentalContactLeg (9), AbortExperimentalFourContact (14), CancelExperimentalFourContact (3), ReleaseExperimentalFourContact (4), UpdateExperimentalContactWatch (44); `hasMore=false`.

- **Forwarding:** Switch Index 0…7 → соответствующий LegN.ChildActor → cast к **базовому BP_BeholderTelescopic_Test**, не только BodyLeg/redistribution → SetLegExtension(Amount) либо RetractLeg(Emergency). Default/cast-failed ветви заканчиваются без success/error output. Нет body owner/epoch admission и нет подтверждения принятия дочерней командой. Совместимый descendant тоже проходит этот base cast; изолировать новый leaf класс без защиты inherited setter недостаточно. Фактические ChildActorClass/instance overrides всех LegN здесь не проверены.
- **Hold:** читает ExtensionPosition у переданного Component.ChildActor после BodyLeg cast, проверяет диапазон 0…1, но команду отправляет через **отдельный Index → SetBodyLegExtension**. Соответствие Component/Index в helper не проверяется. Текущий Abort wiring передаёт согласованные пары Leg0/0, Leg2/2, Leg4/4, Leg6/6; это не доказательство защиты helper от будущего неверного call site. Hold переустанавливает ordinary goal/demo/timing через уже прочитанный SetLegExtension, не фиксирует десять stages/joints/head actual pose.
- **Abort:** только FourContactWatchState 1/2/4/5 → сначала body state=3 и Reason → последовательно четыре Hold(0,2,4,6). Не собирает receipts и не удостоверяет, что все четыре leg calls прошли: invalid component/cast/range в Hold молча завершает отдельную попытку. State=3 не является four-leg atomic stop, rollback или native pose confirmation.
- **Cancel:** Abort(Reason=5), поэтому имеет те же state gates и goal side effects. В отличие от leg-level Cancel он пытается переписать четыре ordinary goals, что может конфликтовать с другим владельцем.
- **Release:** без state/pose/contact guard ставит body WatchState=0, Reason=0, Elapsed=0. Не вызывает Hold/child stop, не очищает цели/overrides и не проверяет принадлежность лап. Поэтому body Release нельзя отождествлять с ограниченным leg Release, допускающим только состояния 2/4.
- **Body Tick:** напрямую вызывает public UpdateExperimentalContactWatch с Tick dt. Сам updater сначала dispatch state5 → UpdateExperimentalRetractionWatch; иначе обрабатывает только state1/4. В этих состояниях увеличивает Updates, проверяет enable/dt/elapsed/timeout, обновляет elapsed (только state1), сверяет root transform, вызывает UpdateBodySurfaceProbes, требует valid settings + measured count8, затем CheckExperimentalApproach и при AtTarget — footprint Valid/Inside/PassesMargin. State1 переходит в 2; state4 остаётся monitored, при потере AtTarget идёт Abort. Прочие состояния не выполняют эту ветвь. Ошибки через Abort могут писать leg goals **из Tick корпуса**, независимо от Tick экспериментальной лапы.

Практический вывод: future native guard должен охватывать body-origin commands и их failure/hold policy. Простая замена child setter на reject недостаточна для multi-leg Abort: корпус уже пометит себя aborted и может частично сменить цели, не получив результата. Это проектное требование, не установленное поведение нового guard.

Без gameplay calls, измерений, тестов, compilation, PIE, motion и asset edits. Непокрыты остальные body admission/retraction/probe/checker bodies, rig internals/settings, telemetry и внешние property/component writers. Source-карта ниже теперь частично подтверждена live, но exhaustive audit не завершён.

### Installed admission и Apply-группы

Полностью прочитаны TryExperimentalStageRedistribution (22 узла), TryExperimentalContactRedistribution (18), TryExperimentalUniformRedistribution (23), ApplyRedistribution0/5 (по 26), а также BodyLeg.IsExperimentalContactPoseSafe (11); `hasMore=false`. Только inspection, не выполнение запросов/проб/движения.

- **Обычный start:** enable/state0/uniform mode, extension 0.1…0.9, совпадение цели/положения/десяти stage variables, duration/speed/step-cap/timeout settings → IsExperimentalContactPoseSafe → contact flag=false → direction=+1 → GameStart → extension/duration/root snapshot → elapsed/updates/progress/reason reset → state1 → Accepted=true. Никаких Apply calls в start нет. Прочитанные reject paths до принятия не пишут собственное motion state; это не доказательство native no-write receipt/полной фактической геометрии.
- **Contact start:** state0+enable → **SampleRedistributionContact(false)** → ordinary start → при Accepted сохраняет contact point/normal из probe plane и plane Z из ProbeImpactPoint → contact flag=true. Поэтому запрос с Accepted=false может уже увеличить ContactSamples и обновить probe state (например, sample прошёл, duration отвергнут вложенным start). Не путать отсутствие принятой motion command с отсутствием любых записей. State1 устанавливается вложенным start до записи anchors/flag во внешнем входе; это последовательное wiring, не доказательство callback-interleaving или race во время исполнения.
- **Uniform reverse:** допускает state2/4 (для 4 нужен contact flag), direction+1, packed stages/mode/progress/extension и параметры времени; затем root snapshot comparison, safe pose, optional owned-contact check. Лишь после этого пишет duration/elapsed/updates/progress/reason/direction−1/GameStart/state1. Сохраняет прежние root/contact anchors и contact flag. При отказе contact checker может уже менять probe/counters; restart из aborted state3 здесь не разрешён.
- **ApplyRedistribution0/5:** в каждой группе пять последовательных пар StagePosition → SetRelativeLocation соответствующего Sleeve. Используют текущие Extension/Direction/Progress, location=`(104*s,0,0)`, sweep=false/teleport=true. Нет собственного state/owner guard, rotation write, rollback или completion receipt. В отличие от обычного ApplyExtension эти функции не используют joint rotation для location: они остаются writer прямой позы, а не готовым actuator для dogleg. Вызовы private по ранее прочитанным metadata; это не публичный API, но общий future enforcement не должен зависеть только от внешнего start guard.
- **IsExperimentalContactPoseSafe:** validity HeadModule → cast head → bool из telescope bAutoDemo, socket requests, Bend/LiveBend, девяти JointMagnitude/PitchRequest/YawRequest и трёх head ClawPosition; invalid/cast failure → false. Setter/trace calls в этом теле отсутствуют. Проверка использует cached state, не component-transform/bone capture. В частности, она не читает собственные head bAutoDemo/TargetOpening/ClawOverride/EyelidOverride: нулевые позиции в момент чтения не удостоверяют отсутствие будущего head writer. Само имя Safe не закрывает lifetime quiescence, collision/support и native ownership.

Этот шаг подтверждает live wiring ранее source-only admission/direct-writer строк. Никаких guards не устанавливалось. Остаются body-controller forwarding/watchdog, probe internals, rig internals/settings, telemetry bodies и внешние component/property writes; полный native audit пока не объявляется завершённым.

### Contact ownership flag, monitoring и Cancel/Release — live bodies

Последовательно прочитаны CheckOwnedRedistributionContact (7 узлов), SampleRedistributionContact (35), UpdateRedistributionContactMonitoring (26), BeginRedistributionContactMonitoring (12), AbortStageRedistribution (5), CancelStageRedistribution (3), ReleaseStageRedistribution (7); все `hasMore=false`. Это чтение, не выполнение trace/probe/monitor.

- **CheckOwnedRedistributionContact:** при bRedistributionContactOwned=true вызывает SampleRedistributionContact(EnforceAnchor=true); при false сразу возвращает **Valid=true без измерения**. Таким образом, Valid здесь означает допустимость optional-contact режима, а не наличие контакта/эксклюзивного владельца. Нельзя принимать этот bool как native owner evidence.
- **SampleRedistributionContact — не чистый predicate:** первым действием увеличивает ContactSamples, затем вызывает MeasureSurfaceProbe. Проверяет valid/hit/plane/no-overlap, |clearance|/|gap|≤0.05 и normal Z≈1; делает дополнительный complex line trace от plane point Z+2 до Z−2 с ignore actors/self. Проверяет расстояние hit до plane point≤0.05, normal Z и отсутствие initial overlap. При EnforceAnchor дополнительно требует drift≤0.01, normal difference≤0.0001 и plane Z difference≤0.05. Это ограниченный геометрический контактный predicate, не friction/support certification и не authenticated coherent capture. Внутренние probe writes пока не разобраны полностью.
- **Monitoring:** только state==4 → MonitoringUpdates++ → enable/dt 0…10/root transform/safe pose/final stages/mode/contact flag checks → CheckOwnedRedistributionContact. Нет ApplyRedistribution calls и нет owner issuer/epoch/revision проверки; ошибки идут в Abort. В state==1 этот monitor ничего не делает, поэтому его отсутствие при прямом active updater call само по себе не означает пропуск active-state monitoring checks: они находятся в UpdateStageRedistribution. Это уточняет прежнее общее замечание о различии Tick/direct-call chains.
- **BeginMonitoring:** принимает state 2 или 4 только с contact flag; при 2 сбрасывает MonitoringUpdates, ставит state=4, вызывает monitor с dt=0 и возвращает результат state==4. Даже dt=0 здесь вызывает измерения и изменения counters/state; Started не является no-write receipt или motion grant.
- **Abort:** только state 1/4 → Reason=input → State=3. Не очищает contact flag, ordinary targets, head requests и не вызывает actuator hold/rollback. State=3 отсекает parent Tick в экспериментальном dispatch, но независимый HeadRig callback этим не закрыт.
- **Cancel:** вызывает Abort(Reason=5). В state 2 и 3 это no-op по прочитанному wiring; публичный Cancel не является универсальным stop.
- **Release:** только state 2/4 → State=0 → bRedistributionContactOwned=false → Released=true; остальные состояния, включая aborted state=3, возвращают false. Нет свежей contact/root/actual-pose проверки, синхронизации старых goals, очистки joint overrides, head stop или передачи owner epoch. После state=0 следующий Tick получает parent chain. Release из monitoring прекращает мониторинг без доказательства native safe handoff.

**Вывод для guard-плана:** контактный flag — локальный режим проверки, а не общий owner token; Cancel/Abort/Release надо классифицировать по конкретному состоянию и побочным записям, не по названию. Ни checked Valid, ни State=3, ни Released=true не закрывают stop/ownership/actual-pose gates. Установка guards не выполнялась.

Остаются: installed start/admission и ApplyRedistribution bodies, body-level forwarding/watchdog, rig internals/settings и фактическая coherent pose/owner реализация. Более ранние списки непрочитанных contact/Cancel/Release ниже — история.

### Головка: отдельный rig callback; installed redistribution updater

Property-read `HeadModule.ChildActorClass` **базового** telescope подтвердил `/Game/BeholderPrototype/BP_Lapa5_Head.BP_Lapa5_Head_C`. Это class default базы, не проверка overrides каждого экземпляра/потомка. Head Blueprint наследуется от Actor; полностью прочитаны EventGraph (37 узлов), SetEyeOpening (4), SetClawOpening (6), SetDemoMode (11), SetEyelidOpening (3), Construction (1), во всех `hasMore=false`.

- **Не Actor Tick:** On Pre Initialize(HeadRig) → Add Mapped Skeletal Mesh с HeadMesh и InDirection=Output. On Pre Forwards Solve(HeadRig) → Elapsed → Opening → EyelidPosition → material scalar `Opening` → Claw0Position/control `Claw0` → Claw1Position/control `Claw1` → Claw2Position/control `Claw2`. Позиции интерполируются с **Get World Delta Seconds** и собственными transition durations. Actor Tick лапы не является единственным scheduler. Отключение/перехват родительского Tick не доказывает quiescent head writers.
- Opening выбирается между auto-demo cosine и TargetOpening. Eyelid/claws выбирают собственный override при >=0, иначе Opening. Значение −1 означает возврат к общей цели, а не hold. Rig float и material writes — отдельные actuator surfaces; состояние ClawPosition не заменяет свежую проверку фактических mesh bones.
- SetEyeOpening: clamp → TargetOpening → bAutoDemo=false. Не очищает claw/eyelid overrides. SetClawOpening: Switch 0/1/2 → соответствующий override (negative→−1, иначе clamp); default без exec continuation. SetEyelidOpening аналогично пишет override.
- SetDemoMode всегда пишет CycleSeconds(max 0.1), DemoStartTime и bAutoDemo; только при Enabled=true сбрасывает три claw overrides и eyelid override в −1. Enabled=false **не** фиксирует текущую позу: interpolation к сохранённым целям остаётся. Public head setters не имеют общего owner admission в прочитанных телах.
- Construction головки содержит лишь entry без исходящего exec. Это не означает отсутствия component initialization/rig execution вне construction.

**Граница head-аудита:** callback wiring/setter bodies прочитаны; сам Control Rig graph, component tick/update settings, фактические bone transforms и порядок callbacks между лапой и головкой ещё не проверены. Поэтому ни совместная atomic pose, ни native physical stop здесь не подтверждены.

Полностью прочитан установленный `UpdateStageRedistribution` (42 узла, `hasMore=false`):

1. Entry → state==1; иначе никаких исходящих действий этой функции. При active state **сначала увеличивается RedistributionUpdates**, затем проверяются enable, dt/elapsed/duration/step cap/game timeout, Actor Transform относительно сохранённого RedistributionPose, IsExperimentalContactPoseSafe и ожидаемые mode/extension/progress/stage positions.
2. CheckOwnedRedistributionContact → elapsed/progress writes → CaptureRedistributionNativeStep → ApplyRedistribution0 → ApplyRedistribution5 → RecordRedistributionNativeStep → повторный CheckOwnedRedistributionContact → completion mode/state. Невалидные ветви вызывают Abort с reason; post-check находится уже **после применения**, не является rollback.
3. Внутри public updater присутствуют собственные state/time/geometry guards, то есть прямой вызов не обходит их все. Однако вызов не требует owner identity/epoch/transaction/revision. Update counter меняется до остальных admission checks; его нельзя объявлять command/application revision или доказательством successful commit.
4. Tick перед updater вызывает UpdateRedistributionContactMonitoring, но в самом updater такого вызова нет. Прямой public вызов не воспроизводит всю Tick-цепочку; наличие CheckOwnedRedistributionContact не доказывает тождественность monitoring side effects. Тело contact checker/monitor ещё требует чтения; слово Owned не означает реализованный общий native owner protocol.

Никаких gameplay function calls, тестов, compilation, PIE, движения или правок ассетов. Следующий незакрытый участок: Control Rig/settings, contact-check/monitor/Cancel/Release bodies и внешние body-level writers. Более ранние замечания «головка/updater не прочитаны» ниже относятся к предыдущим этапам.

### Public setter bodies: admission до первой записи

Прочитаны полностью девять дополнительных графов telescope: SetMotionMode (2), RetractLeg (6), SetLegBend (5), SetJointBend (29), ClearJointBend (11), SetMotionDurations (7), SetHeadOpening (7), SetHeadClawOpening (15), SetHeadEyelidOpening (5); `hasMore=false`. Первый параллельный read batch упёрся в MCP `TOO_MANY_PENDING_TOOL_CALLS`; результаты для выводов затем получены последовательным чтением. Никаких gameplay calls/asset mutations при этом не выполнялось.

| Public вход | Подтверждённое wiring / влияние |
|---|---|
| SetMotionMode | Прямо назначает bSequentialMotion; не вызывает Snap/Apply и не очищает requests |
| RetractLeg | **Сначала** bSequentialMotion=NOT Emergency, **затем** SetLegExtension(0), затем TransitionSeconds из normal/emergency duration с минимумом 0.01. Это изменение режима+цели+тайминга, не мгновенный stop и не доказательство safe recovery |
| SetLegBend | Последовательно пишет BendPitchDegrees/BendYawDegrees с общей L1-нормировкой до 2; не снимает индивидуальные overrides |
| SetJointBend | Switch(Index): 1…9 → raw PitchRequest → raw YawRequest → Override=true. Index=0/default exec не подключены. Нормировка происходит позднее в updater, не здесь; NaN/Inf validation этим просмотром не подтверждена |
| ClearJointBend | Switch 1…9 → только Override=false. Requests не обнуляются, Bend не ставится в ноль: ResolveJointCommands снова выбирает общий LiveBend. Поэтому Clear — не hold и не straight/neutral command |
| SetMotionDurations | Три последовательных записи max(input,0.01) в ExtensionSeconds/RetractionSeconds/EmergencyRetractionSeconds. Текущий TransitionSeconds здесь не пересчитывается; не считать это немедленной сменой скорости уже принятой цели |
| SetHeadOpening | **До cast** сохраняет raw Amount в SocketRequestedOpening; при успешном cast HeadModule.ChildActor → SetEyeOpening(Amount) → UpdateSocketSafety. Следовательно, вызов меняет не только eye goal: safety повторно выдаёт три claw goals. При cast failure requested state уже записан |
| SetHeadClawOpening | До cast последовательно пишет все три SocketRequestedClaw containers: соответствующий индексу получает clamp либо sentinel −1 при отрицательном Amount, остальные сохраняются. Затем cast → SetClawOpening(input index, вычисленный Amount с socket lock/лимитом). Отдельного exec rejection индекса перед этими setter nodes нет; обработка invalid index внутри головки ещё не прочитана |
| SetHeadEyelidOpening | Cast ChildActor → SetEyelidOpening(Amount); при cast failure exec заканчивается. В теле telescope прямого transform write нет, но поведение вызываемой функции головки пока не подтверждено |

Во всех этих прочитанных входах отсутствует owner/epoch admission. **Guard только внутри SetLegExtension оставит раннюю запись режима в RetractLeg; guard только после cast оставит ранние head request writes.** Отказ должен предшествовать первой записи внешнего входа, а вложенные вызовы должны сохранять контекст принятой операции. Guard не установлен; это требование к будущему изолированному плану, не подтверждение enforcement.

Теперь тела всех перечисленных собственных functions базового telescope просмотрены структурно (не исполнены). Это не закрывает весь writer audit: остаются собственные head/body-controller graphs, installed redistribution bodies и внешние property/component writers. Старые «public setters ещё не прочитаны» ниже — история предыдущих шагов.

### Внутренние stage/joint updaters и Snap-пути

Следующим read-only чтением полностью получены графы базы: UpdateStages (58 узлов), UpdateJointBends (67), ResolveJointCommands (37), CaptureStageFrame (69), UpdateBend (10), SnapBend (5), SnapStages (21), SnapJointBends (48); `hasMore=false`. Это просмотр структуры/формул, **не численная проверка их корректности**.

1. **UpdateStages exec order:** UpdateBend → UpdateJointBends → CaptureStageFrame → Set Stage0Position…Stage9Position → Set ExtensionPosition (среднее десяти positions). Component transforms применяются позднее отдельным ApplyExtension, не в этих setter-цепочках.
2. **Socket readiness не global hold:** UpdateBend и UpdateJointBends получают исходный DeltaSeconds. В UpdateStages только stage interpolation dt питается выражением `dt * SelectFloat(1,0,bSocketMotionReady)`. Поэтому запрет stage progress сам по себе не доказывает остановку joint/live-bend state и последующего применения rotations. Это структурный вывод об отдельных путях, не утверждение, что сустав обязательно движется при любом false.
3. **Stage интерполяция:** десять FInterp to Constant получают sequential/uniform targets и скорость `SelectFloat(10,1,bSequentialMotion)/max(TransitionSeconds,0.01)`. Их DeltaTime учитывает PreviousStage positions, FrameStage goals/retract readiness и остаток времени после соседних секций. Эти локальные geometry/time gates не являются owner/epoch admission.
4. **UpdateJointBends:** сначала ResolveJointCommands, затем LastJointDeltaSeconds и последовательные PreviousJoint/Bend/Magnitude writes для 1…9. Каждый Bend получает отдельный VInterp to Constant с исходным dt и скоростью `max(JointAngularSpeedDegrees,0.01)/1.414214`. Цели содержат adjacent-stage smoothstep в диапазоне 0.98…1, подавление при retract target и L1-нормировку pitch/yaw до 2°. Независимые интерполяции не устанавливают согласованный dogleg phase или отношение 1:−2:1.
5. **ResolveJointCommands:** последовательно пишет 18 Pitch/YawCommand, выбирая индивидуальный Request при bJointOverride либо LiveBend. Никакого owner-check в прочитанной exec цепочке нет. Сохранённые requests/overrides — отдельная latent command surface: после handoff их нельзя считать очищенными только из-за нового режима/владельца.
6. **CaptureStageFrame:** сохраняет sequential/readiness/transition/target/dt, десять PreviousStagePosition, десять FrameStageGoal и десять FrameStageRetractReady. Readiness определяется JointMagnitude соседних суставов с порогом 1e-5 (на концах один сустав). Вызов стоит **после обновления суставов, но до обновления секций**. Это внутренний frame cache из переменных, не fresh native actual-component capture/receipt; нельзя подставлять его вместо NativeCoherentCapture и приписывать ему authentication/revisions.
7. **UpdateBend/SnapBend:** LiveBendPitch/Yaw либо отдельно интерполируются со скоростью `2/max(BendTransitionSeconds,0.01)`, либо напрямую назначаются; целевые pitch/yaw совместно L1-нормированы до 2°. Owner admission отсутствует в прочитанных цепочках.
8. **SnapStages/SnapJointBends:** SnapStages напрямую пишет десять sequential/uniform stage positions из ExtensionAmount. SnapJointBends вызывает ResolveJointCommands, ставит LastJointDeltaSeconds=0, напрямую назначает девять Bend, затем копирует их в PreviousJoint и вычисляет Magnitude. У SnapJoint нет runtime retract-target suppression из UpdateJointBends; adjacent-stage smoothstep/нормировка присутствуют. Нулевой dt здесь **не** означает no-write: это snap assignment, за которым construction вызывает ApplyExtension.

Практическая граница future guard: защищать admission и весь согласованный update **до** первого LiveBend/command/frame/position write, затем отдельно конечный actuator. Запрет только stage dt или ApplyExtension оставит внутреннее состояние изменённым и допускает позднее применение после handoff. Установка/проверка такого guard не выполнялась.

Остаются непрочитанными public setter bodies (кроме SetLegExtension), head controller и внутренние guards public redistribution updater; прежние списки непокрытых Update/Snap ниже являются историей предыдущего шага.

### Продолжение: конечный writer, construction и handoff

Read-only `inspect_graph` полностью вернул `ApplyExtension` (76 узлов), `UserConstructionScript` (7), `SetLegExtension` (6), `UpdateSocketSafety` (26), BodyLeg EventGraph (6), redistribution EventGraph (11); во всех `hasMore=false`. Функции не вызывались — читались узлы и pin links.

- **ApplyExtension:** entry сразу связан с Set Relative Location Sleeve00; далее последовательная цепочка из десяти location и девяти rotation writes (Sleeve01…09). Location строится из `104 * Stage{i}Position`, для 1…9 поворачивается соответствующим rotator. У прочитанных transform calls sweep=false, teleport=true. Перед первым write нет exec guard; цепочка не является подтверждённым atomic actuator/rollback и не проверяет ownership. Это общий конечный writer обычного telescope, отдельный от ApplyRedistribution0/5.
- **Construction:** clamp(ExtensionAmount,0,1) → Set ExtensionPosition → SnapStages → SnapBend → SnapJointBends → ApplyExtension. Следовательно, Tick guard не покрывает editor/construction применение позы. Future claim должен учитывать lifecycle/reconstruction и инвалидировать прежние captures/identity; нельзя запрещать construction вслепую и считать проблему решённой.
- **SetLegExtension:** clamp входа → Set ExtensionAmount → bAutoDemo=false → Set TransitionSeconds (выбор extension/retraction duration, минимум 0.01). Здесь нет owner admission перед изменением цели; команда также меняет demo/timing, а не только Amount.
- **UpdateSocketSafety:** измеряет head center относительно SocketHousing, записывает SocketHeadCenterX/bSocketHeadOutside/bSocketClawsLocked; сбрасывает bSocketMotionReady=false, затем при успешном cast ChildActor к BP_Lapa5_Head читает три ClawPosition и определяет readiness. После этого последовательно вызывает **SetClawOpening(0/1/2)** с вычисленными Amount. Таким образом, это не read-only safety check: он пишет claw goals ещё **до UpdateStages/ApplyExtension**. При cast failure readiness остаётся false. Внутреннее исполнение BP_Lapa5_Head пока не инспектировано; полное asset path головки данным cast title не установлено.
- **BodyLeg EventGraph:** BeginPlay/Overlap/Tick непосредственно передаются соответствующим Parent events.
- **Redistribution EventGraph:** Tick → Branch(`RedistributionState != 0`); true → UpdateRedistributionContactMonitoring → UpdateStageRedistribution; false → Parent Tick. Значит, state=0 действительно открывает базовую цепочку через BodyLeg, включая claw goal writes. BeginPlay/Overlap также передаются родителю. Это structural wiring, не доказательство поведения во время исполнения.

Следующий непокрытый участок: внутренние UpdateStages/UpdateJointBends/ResolveJointCommands/Snap-графы, setters head и собственный updater головки, а также guards внутри public UpdateStageRedistribution. Guards/поля не устанавливались; тестов, compilation, PIE и движения не было.

Read-only `blueprint.get_blueprint` подтвердил цепочку `BP_BeholderStageRedistribution_Test` → `BP_BeholderBodyLeg` → `BP_BeholderTelescopic_Test` → Engine.Actor. Список functions относится к собственным графам: отсутствие inherited setter в списке дочернего Blueprint не доказывает отсутствие этого входа.

В базовом telescope подтверждены public команды: `SetLegExtension(Amount)`, `SetMotionMode(Sequential)`, `RetractLeg(Emergency)`, `SetLegBend(PitchDegrees,YawDegrees)`, `SetJointBend(Index,PitchDegrees,YawDegrees)`, `ClearJointBend(Index)`, `SetMotionDurations(ExtendSeconds,RetractSeconds,EmergencySeconds)`, `SetHeadOpening(Amount)`, `SetHeadClawOpening(ClawIndex,Amount)`, `SetHeadEyelidOpening(Amount)`.

Подтверждены private графы `ApplyExtension`, `UpdateStages`, `SnapStages`, `UpdateBend`, `SnapBend`, `UpdateJointBends`, `SnapJointBends`, `UpdateSocketSafety`, `CaptureStageFrame`, `ResolveJointCommands`. Их наличие — ещё не проверка внутренних writers/guards.

Полностью прочитаны 13 узлов базового EventGraph с pin links (`hasMore=false`):

- Tick → **Set SocketTarget → UpdateSocketSafety → UpdateStages(Target,DeltaSeconds) → ApplyExtension**. Target питается MathExpression с выбором между auto-demo cosine и clamp(ExtensionAmount,0,1). Следовательно, guard только непосредственно у ApplyExtension оставляет предыдущие state/goal mutations вне защиты; нужен разбор внутренних safety/stage calls.
- BeginPlay → SetHeadOpening(InitialHeadOpening) → SetHeadEyelidOpening(InitialHeadEyelidOpening).
- ActorBeginOverlap в этом графе не имеет исходящего exec connection.

Компоненты базы: цепочка Sleeve00…Sleeve09, HeadModule (ChildActorComponent) под Sleeve09, SocketHousing под корнем. Конкретный class головки и его внутренние writers ещё не проверены.

Redistribution metadata дополнительно подтверждает **public** `UpdateStageRedistribution(DeltaSeconds)` и `BeginRedistributionContactMonitoring()`, наряду со start/contact-start/uniform/Cancel/Release. Поэтому Tick — не единственный потенциальный вход в updater; guards нужно проверять внутри него, не только в Tick dispatch. В metadata BodyLeg имеются probe/plane/planning/coherence функции; их runtime bodies здесь не выполнялись и не классифицированы как pose writers.

**Граница:** это частичный live structural audit, не runtime verification. Тела остальных функций, construction и inherited Tick handoff пока не прочитаны полностью. Никаких вызовов gameplay-функций, компиляции, asset edits, тестов, PIE или движения. Ниже сохранена историческая source-карта; её первоначальные «Blueprint не инспектировались» относятся к моменту подготовки.

Подготовлено чтением существующих Python graph plans, harness call sites и документации. **Генераторы не выполнялись; Blueprint не инспектировались/не менялись, тесты/Unreal/PIE не запускались.** Таблица — список подтверждённых source путей и кандидатов для будущей read-only проверки, не доказательство полноты native enforcement.

## Главный вывод

Нельзя добавить owner-check только к новому dogleg API и считать лапу эксклюзивно управляемой. Уже есть прямые transform writers, обычные public commands, body-level goal writers и смена dispatch-state, которая возвращает старый updater. Владение должно охватывать **всю цепочку экземпляра**, включая inherited implementation и внешние команды корпуса.

## Карта путей

| Путь | Что установлено из источников | Доказательство / ограничение |
|---|---|---|
| `ApplyRedistribution0`, `ApplyRedistribution5` | Записывают `Stage{i}Position`, затем `K2_SetRelativeLocation` на `Sleeve{i:02d}` с sweep=false/teleport=true | `tools/build_beholder_redistribution_graph.py`, `apply_group`; прямой writer, не только setter цели. Параметр teleport **не** доказывает непрерывную безопасность траектории |
| `UpdateStageRedistribution` | После guards меняет elapsed/progress, вызывает обе Apply-группы, затем меняет mode/state | Тот же файл, `update`; позднейшие uniform/cap/contact/timeout/audit расширения меняют итоговую цепочку |
| `TryExperimentalStageRedistribution` | Принимает motion request и сохраняет extension/duration/root snapshot/state | Тот же файл, `request`; отказ не должен трогать старое состояние. Claim должен предшествовать принятию, а не появляться после state=1 |
| `TryExperimentalUniformRedistribution` | Запускает обратное перераспределение из 2/4, меняет direction/duration/elapsed/progress/state | `tools/build_beholder_uniform_return_graph.py`, `request`/`integration`; это другой вход в тот же writer, не новый свободный owner |
| Tick dispatch экспериментальной лапы | `RedistributionState != 0` выбирает собственную ветвь, иначе parent Tick; monitoring extension вставляет свой update в эту ветвь | `build_beholder_redistribution_graph.py::tick`, `build_beholder_redistribution_monitor_graph.py::integration`; итоговый live dispatch надо инспектировать, базовый plan не отражает все upgrades |
| `CancelStageRedistribution`, `AbortStageRedistribution` | Меняют экспериментальное state/reason, прекращая его активный путь | Base plan + monitor upgrade; не глобальный stop других controllers/лап |
| `ReleaseStageRedistribution` | Возвращает state=0 в допустимых состояниях и тем самым доступ parent path | Base plan + monitor upgrade; не очищает автоматически все старые обычные цели и не является pose hold |
| `TryExperimentalFourContact` | После общей подготовки/footprint gate выдаёт четыре `SetBodyLegExtension` для 0/2/4/6 | `tools/build_beholder_contact_request_graph.py::request`; precheck четырёх targets не является ownership claim четырёх лап |
| `HoldExperimentalContactLeg` | Читает ExtensionPosition и передаёт его в `SetBodyLegExtension` как цель | `tools/build_beholder_contact_watch_graph.py::hold_leg`; это goal mutation, даже при названии Hold, не exact ten-stage pose lock |
| `AbortExperimentalFourContact`, `CancelExperimentalFourContact` | Watchdog/Cancel вызывают Hold для нижних четырёх лап и меняют body-controller state/reason | `build_beholder_contact_watch_graph.py::abort/controls`; будущий owner-check должен различать legitimate current-owner stop и чужой writer, а не просто запрещать всё слово Cancel |
| `ReleaseExperimentalFourContact` | Обнуляет watch state/reason/elapsed без очистки текущих целей лап | `build_beholder_contact_watch_graph.py::controls`; последующее обычное движение может сохраниться |
| `TryExperimentalFourRetraction` | После guards выдаёт четыре цели 0 через `SetBodyLegExtension`, включает state=5 | `tools/build_beholder_retraction_graph.py::request`; не emergency recovery из произвольного отказа |
| `SetBodyLegExtension`, `RetractBodyLeg` | Публичные body-команды адресуют выбранную ветвь 0…7 | `docs/BeholderBodyPrototype.md`, раздел тела; определение текущего live graph не инспектировано в этом шаге |
| `SetLegExtension`, `SetJointBend`, `SetMotionMode`, `SetMotionDurations` | Существующие public calls могут менять goal/request/mode/timing вне нового dogleg-входа | Вызовы в `exercise_beholder_redistribution.py`, `exercise_beholder_joint_commands.py`, `exercise_beholder_motion_profiles.py`; это доказательство call sites, **не полное описание реализации** |
| Head/claw/eyelid и обычные stage/joint updaters | Нужна отдельная инвентаризация inherited leg/head implementations, demo/construction/tick/rig writers | В этом шаге полный установленный граф и все имена методов не установлены. Не выдумывать missing Blueprint method names и не считать эту строку покрытой |

`build_beholder_telescope_assets.py` — importer mesh assets, не исходник runtime telescope-controller. Успешное чтение этого файла не закрывает аудит обычных setters/update graphs.

## Где будущие owner/revision проверки должны быть различны

1. **Admission команд:** public leg/body commands, experimental start/reverse/retraction и будущий dogleg intent. Сверить subject/lifetime/epoch и допустимость режима **до изменения целей/state**. Rejected чужой запрос не должен уничтожать действующую команду.
2. **Применение позы:** непосредственно перед конечными stage/joint/component writes. Одной проверки на входе request недостаточно, если последующие Tick продолжаются после смены owner.
3. **Dispatch и handoff:** state=0/Release/parent Tick, auto/demo/rig paths. Передача не должна позволить старым goals незаметно ожить под новым epoch. Release не заменяет подтверждённый native hold и admission нового владельца.
4. **Body multi-leg action:** четыре prechecks и четыре последовательных goals — не atomic multi-leg ownership transaction. До полного claim нельзя начинать половину манёвра; policy отката claims не должна переписывать чужие targets.
5. **Диагностика:** `RedistributionNativeStep*` — lifetime telemetry отдельных применённых шагов. Её samples/maxima не являются command/application/claim revisions, не предоставляют владение и не должны переименовываться ради прохождения нового DTO.

## Предлагаемая семантика counters — не установленные поля

- command_revision: принятое изменение цели/режима/тайминга/ownership, способное повлиять на управление. Отказ до приёма не увеличивает его. Повторная идентичная команда требует явно согласованной idempotency policy, а не выдуманного commit.
- application_revision: фактическое связанное изменение actual pose, в том числе старым permitted updater. Нельзя считать только новые dogleg commits и игнорировать старые writers: тогда stale capture останется незамеченным.
- Один future atomic dogleg commit может изменять goals+actual pose и получать +1 обоих counters, как в draft intent. Это не правило начислять application revision на каждую команду цели без actual application.
- probe_revision/capture_sequence отражают свежие измерения/согласованные снимки, не команды и не время Python callbacks.

Все counters/producer/consumer пока отсутствуют как подтверждённый общий native протокол. Схема DTO сама по себе их не устанавливает.

## Безопасная граница следующего implementation-плана

Только **изолированная копия** leg/controller/fixture после полной read-only инспекции собственных и inherited graphs. Исходные ЛАПА5, shared `BP_BeholderBodyLeg` и текущий body/level не переписывать ради обхода interlocks. Копирование одной функции не изолирует вызовы parent/body, которые всё ещё адресуют старый class/child actor.

Сначала нужно подтвердить полный список writers/связей и правила счётчиков, затем отдельно согласовать установку guards. Не переустанавливать уже применённые graph plans. Никакая строка этой карты не разрешает включить dogleg movement: остаются historical observer gate, precision cases, actual-pose/partial-failure recovery и физическая поддержка.

Связанные документы: [native boundary](BeholderLegNativeBoundary.md), [ownership](BeholderLegOwnershipContract.md), [статус](BeholderDoglegStatus.md).
