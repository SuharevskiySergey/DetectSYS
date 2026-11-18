# OwnershipIsolation: шесть сохранённых заготовок

## Разрешённый scope и результат

После согласования путей пользователь отдельно выбрал **«Создать 6 заготовок»**, затем **«Разрешить автокомпиляцию»** внутри duplicate. Первоначальное условие no-compilation было уточнено **до первой записи**: EngineWire `asset.duplicate` вызывает подготовку MathExpression, которая может компилировать копию (`McpBPGraphMathExprCopy.cpp:58`); сама engine duplication также может компилировать Blueprint.

Созданы только следующие копии через editor `asset.duplicate`, все ответы `saved=true`, warnings не возвращены. Предварительный asset.list папки назначения вернул count0/hasMore=false; taken destination инструмент отказывает, overwrite не применялся.

| Исходник относительно /Game/BeholderPrototype | Копия относительно /Game/BeholderPrototype/OwnershipIsolation |
|---|---|
| Telescopic/BP_BeholderTelescopic_Test | BP_OwnershipTelescope |
| Body/BP_BeholderBodyLeg | BP_OwnershipBodyLeg |
| Telescopic/BP_BeholderStageRedistribution_Test | BP_OwnershipRedistribution |
| BP_Lapa5_Head | BP_OwnershipHead |
| CR_Lapa5_Head | CR_OwnershipHead |
| Body/BP_BeholderBody_Test | BP_OwnershipBodyFixture |

Read-only metadata пяти Blueprint после копирования: **BS_UpToDate / hasCompileErrors=false**. Это не отдельный compile run, не числовая/runtime проверка и не утверждение 0 compiler warnings по отдельному compiler report. Для новой CR-копии отдельная compilation/status verification не выполнялась; подтверждено создание/сохранение ControlRigBlueprint.

## Это ещё не изоляция и не guard

Read-only baseline двух planned reparent copies сохранён отдельно: [BeholderOwnershipPreReparentBaseline.md](BeholderOwnershipPreReparentBaseline.md) — 32 собственных graphs/634 nodes с pins/links, metadata/defaults и file fingerprints. **Не rollback backup, не полный inherited-component/member-binding export**; наличие архива не снимает оставшиеся pre-reparent gates.

### Найден engine reparent API — пока не вызван

После дополнительного read-only поиска найден штатный UE5.6 Python API:

`unreal.BlueprintEditorLibrary.reparent_blueprint(blueprint, new_parent_class) -> None`.

Источник API: https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/BlueprintEditorLibrary?application_version=5.6 . Подтверждена **локальная реализация** установленного engine: `C:/Program Files/Epic Games/UE_5.6/Engine/Source/Editor/BlueprintEditorLibrary/Private/BlueprintEditorLibrary.cpp:700–745` (installation directory прочитан из реестра).

- Null input/same parent → warning и early return, а не typed success/error. Возврат None нельзя считать receipt успешного reparent.
- Проверка old-parent ancestry может залогировать **possible data loss**; смена на независимую копию прежнего parent как раз требует отдельного разбора этой границы, а не подавления warning.
- Далее API назначает ParentClass, валидирует scene roots, вызывает RefreshAllNodes и MarkBlueprintAsModified.
- **Сразу компилирует** с `SkipSave | UseDeltaSerializationDuringReinstancing | SkipNewVariableDefaultsDetection`. Следовательно, операция не разделяется на безопасный «только parent write без compile» и отдельную будущую компиляцию. Успех функции не означает, что файл сохранён.
- API не обещает замены всех старых class references на копии или сохранения всех inherited defaults. MathExpression GUIDs/member owners/cast/parent-call и component-template overrides требуют snapshot/diff и явной проверки; нельзя считать RefreshAllNodes полным dependency remap.

EngineWire search обнаружил доступный transport `system_control.execute_python` с explicit consent, но **он не вызывался**, Python API не импортировался/не проверялся в editor. Отсутствие dedicated MCP actor reparent capability не означает отсутствия engine API. Никакие tools/plugin исходники не менялись.

#### Необходимая граница будущего разрешения

Перед mutation сохранить scoped before evidence копий: parent path, inherited field names/types/defaults, SCS hierarchy/component defaults, graph nodes/pins/links и MathExpression bindings. Отдельно исходные hashes и перечень изменяемых copied packages. Снимок должен позволять обнаружить потерю данных, а не только факт назначения нового parent.

Proposed initial reparent scope — **только** BP_OwnershipBodyLeg → BP_OwnershipTelescope и BP_OwnershipRedistribution → BP_OwnershipBodyLeg, с неизбежной engine compilation, остановкой при проблемах и сохранением только после проверки. Это предложение не включает разрешение заменять casts/heads/body slots, «чинить до зелёного» произвольными graph edits или делать rollback присваиванием старого parent: такой rollback сам снова компилирует и не восстанавливает потерянные defaults. Любой repair/restore требует заранее согласованного ограниченного плана.

Сначала нужно согласовать snapshot/repair scope и способ проверки bindings/defaults; затем отдельно сам reparent. Copy-only consent и согласование его автокомпиляции не распространяются на этот новый API. На текущем шаге были только web/local-source/catalog reads, без asset mutation, Python execution, compile/tests/PIE/motion.

### Последующая read-only проверка фактических copy references

Property reads **самих копий** подтвердили BP_OwnershipTelescope.HeadModule.ChildActorClass → исходный BP_Lapa5_Head, BP_OwnershipHead.HeadRig.ControlRigClass → исходный CR_Lapa5_Head и все восемь BP_OwnershipBodyFixture.LegN.ChildActorClass → исходный BodyLeg. Это теперь наблюдаемые зависимости, не только предположение о duplicate semantics.

В трёх sample graphs копий подтверждены старые cast nodes: telescope.SetHeadOpening и BodyLeg.IsExperimentalContactPoseSafe → BP_Lapa5_Head; body.SetBodyLegExtension → восемь cast BP_BeholderTelescopic_Test. Поэтому одной смены component-class недостаточно: после подстановки независимой copied head старый cast к original head может перестать проходить. Нужна согласованная замена cast/target/member references **до runtime использования**, с последующей отдельной компиляцией. Эти три чтения не являются полным reference scan всех copied graphs.

Предлагаемая очередность future remap: head rig dependency → head references в telescope → BodyLeg parent/member/head references → redistribution parent/member references → body casts/slots. Body slots пока не выбраны; не заменять автоматически все восемь на redistribution.

Поиск `reparent blueprint`, `set parent class` и просмотр Blueprint lifecycle catalog **не обнаружили dedicated actor-Blueprint parent-class setter**: найденный `blueprint.edit_scs/reparent` меняет parent компонента, а widget setter относится к UserWidget. Не использовать их для actor inheritance и не выдумывать action. Перед future reparent требуется найти поддерживаемый editor API/точный контракт и отдельно согласовать изменение/компиляцию; наличие альтернативного подхода пока не подтверждено. Generic asset property mutation не считается корректной заменой engine reparent lifecycle.

На этом дополнительном шаге были только property/graph/catalog reads: ни reparent, ни component/graph writes, compilation, тесты, функции, акторы, PIE или движение не выполнялись. Созданные ранее шесть заготовок сохранены без новых правок.

- BP_OwnershipBodyLeg всё ещё parented к исходному BP_BeholderTelescopic_Test.
- BP_OwnershipRedistribution всё ещё parented к исходному BP_BeholderBodyLeg.
- Component/cast/member/rig references **не перепривязывались** между копиями. Duplicate сохраняет внешние ссылки на исходники; это не ошибка, которую разрешено самовольно исправить в copy-only scope.
- Guard fields/graphs, issuer, transport, revisions и actuator не добавлялись. Копии не размещены в level, не подключены к body/PIE/motion и не удостоверяют native ownership.
- Следующий этап — отдельное согласование перепривязки и проверки references; текущего разрешения недостаточно для reparent/graph edits/ручной компиляции/тестов/вызовов функций.

## Исходные файлы

SHA-256 перед первой копией и после последней совпали для всех шести source .uasset. Это подтверждает неизменность **файлов на диске**, не общий аудит памяти редактора/всего проекта.

| Source basename | SHA-256 до = после |
|---|---|
| BP_BeholderTelescopic_Test | 242234E15491BC1C3EB5E7F831C614CC5D6CA657D3C63EDB83076B6EB61F955B |
| BP_BeholderBodyLeg | 3C8855B38FD6EC356723DA63270636F5E3C8F3AB800208C5F63A491CED52DFA2 |
| BP_BeholderStageRedistribution_Test | 45F243257C9E7F52F9FF92D51B6E1F9146ECF7780AD0112E1750C3DD8C012F06 |
| BP_Lapa5_Head | 5D31A249B6D2AE9517A2AF7FD332886689341E86F344E03BFD4C978ADB328306 |
| CR_Lapa5_Head | A85278C3B9B820C92440E50DF773861F2A8208CA562EAE25807B48CF7FE07D9B |
| BP_BeholderBody_Test | 1EEAAAF4D00D95197CFA66A3213AD8A5945E62FAB75DC4FE6AEAD7BE6C85924C |

Targeted git status показывает только новую OwnershipIsolation папку среди проверенных source/destination paths. Не выполнялись cleanup/reset/commit или изменение level. Tests/gameplay calls/rig solve/actors/PIE/motion/full suite не запускались. Автоматическая компиляция — только согласованный внутренний эффект duplicate.

## Planning manifest

`BeholderGuardIsolationManifest.json` оставлен **исходным planning snapshot** с destinations=null для воспроизводимости отдельно проверенных восьми reviewer tests. Он не актуальная карта существующих копий и не разрешение повторять duplicate. Актуальные destinations и граница copy-only work записаны выше. Будущая миграция manifest/его fixtures требует отдельного source шага; новый test run этим документом не разрешён.
