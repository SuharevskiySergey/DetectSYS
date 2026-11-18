# Pre-reparent baseline — только структура двух копий

Подготовлена [source-only спецификация binding inspector](BeholderOwnershipBindingInspectorPlan.md): проверенные UE5.6 поля, allowlist, coverage/error schema и запрет скрытых mutation/resolve helpers. Это пока не реализация и не запущенный inspector; protected/private UPROPERTY не считаются автоматически доступными из Python.

Последующая source-проверка getter установила конкретный Python blocker: PropertyAccessUtil требует Edit/BlueprintVisible/BlueprintAssignable, которых нет у проверенных raw reference/BoundGraph/override-record properties. Обычный get_editor_property не закроет полный capture. Нужен альтернативный подтверждённый read API или отдельно согласованный native reader; editor probe не запускался, reparent по-прежнему заблокирован.

Архив read-only MCP responses:

`Saved/BeholderOwnershipPreReparent_8fd78c8fe8d84609816150f9d2bf2948.json`

SHA-256: `BB97E29B36D15E61288826269C9800B56E945372CBC846BB6AF75E110A2F2D16`.

Создан новым UUID-именем без перезаписи; содержит исходные metadata/defaults responses и полный `includePins=true` response каждого собственного function/event graph двух staged копий. Архивированы именно ответы tools, не реконструированные вручную графы. JSON прочитан PowerShell для структурной сводки; Python modules/test scenarios не запускались.

| Копия под /Game/BeholderPrototype/OwnershipIsolation | Variables/defaults | Собственные graphs | Nodes |
|---|---:|---:|---:|
| BP_OwnershipBodyLeg | 164/164 | 15 | 330 |
| BP_OwnershipRedistribution | 201/201 | 17 | 304 |

Все graph responses successful, `hasMore=false`; числа полученных nodes совпали с metadata nodeCount для всех 32 graphs. Сохранены node IDs, pin links/types/default literals, function signatures и имена/типы/declaringBlueprint доступных variables. Compile status прочитан UpToDate/no errors, не запускался заново.

Родители по-прежнему исходные: BodyLeg-copy → original telescope; redistribution-copy → original BodyLeg. В snapshot нет выполненного reparent.

## Файловые fingerprints копий на этом этапе

| Asset basename | SHA-256 .uasset |
|---|---|
| BP_OwnershipBodyLeg | 249B7F19D4E3C13752C8D2B41F5F29708BB7DD2659045D5D5EC53C5CCA8142CC |
| BP_OwnershipRedistribution | FA776FFDE5686CD9699D6FF6EA9361A4D5B6FF2909E8F15EEB5DDBF59364474C |
| BP_OwnershipTelescope | A2B6A85533A5A4C47C901FC09BAA8D2C4B7423FE88E76F41FB582DD6F63DE4BE |

Это fingerprints, **не backup copies** и не разрешение восстанавливать asset из произвольного источника.

## Что снимок НЕ закрывает

### Проверенная граница node details и дальнейший выбор

Дополнительно прочитан точный контракт `blueprint.inspect_graph` и реализация `McpBPGraphDetails.cpp:140–186`: node details возвращает name/title/comment/position, pins, NodeGuid и специальные settings только для animation nodes. Здесь нет экспорта VariableReference/FunctionReference member GUID/owner или MathExpression BoundGraph. **NodeGuid не равен member GUID**. Перечитывание всех 634 узлов через info=node этот конкретный пробел не закрывает; такой повторный массовый read не выполнялся. Это вывод о проверенном handler, не об отсутствии иных возможностей всего engine.

Локально проверен потенциальный engine text-export primitive: `UE_5.6/Engine/Source/Editor/UnrealEd/Private/EdGraphUtilities.cpp:457–480`, `FEdGraphUtilities::ExportNodesToText`. Он снимает глобальные TagExp/TagImp object marks, требует одинаковый Outer у переданных nodes и вызывает UExporter в copy mode. Поэтому не считать его заранее доказанным zero-side-effect инспектором или полной recovery сериализацией. Не вызывался. ImportNodesFromText — отдельная изменяющая операция и не входит в предлагаемое чтение.

Следующий полезный шаг вместо повторных metadata reads — **подготовить source-only план/код ограниченного binding inspector**, без его запуска: allowlist шести staged assets и необходимых original parents; чтение member owner/name/GUID/self-context, MathExpression Expression/BoundGraph и component override key/owner; явные unsupported/truncation поля, без compile/reconstruct/rebind/Modify/save/import. Доступность этих полей из Python сначала проверять по source/API; если не доступны, фиксировать блокер, а не добавлять native plugin/build самовольно. Будущий editor запуск, даже read-intent Python, согласовывать отдельно. Reparent остаётся заблокирован до пригодного snapshot/recovery решения.

### SocketHousing: последующая targeted details проверка

Пять последовательных read-only `inspect.get_component_details` с `propertyNames=[bVisible,bHiddenInGame]` successful, missingProperties пуст, propertiesTruncated=false. Это template reads без spawn/registration; world transforms/bounds незарегистрированных templates не считаются actual pose.

| Inspected BP | Возвращённый componentPath (относительно /Game/BeholderPrototype/) | bVisible / bHiddenInGame |
|---|---|---|
| original telescope | Telescopic/BP_BeholderTelescopic_Test.BP_BeholderTelescopic_Test_C:SocketHousing_GEN_VARIABLE | True / False |
| original BodyLeg | Body/BP_BeholderBodyLeg.BP_BeholderBodyLeg_C:SocketHousing_GEN_VARIABLE | False / True |
| telescope-copy | OwnershipIsolation/BP_OwnershipTelescope.BP_OwnershipTelescope_C:SocketHousing_GEN_VARIABLE | True / False |
| BodyLeg-copy | OwnershipIsolation/BP_OwnershipBodyLeg.BP_OwnershipBodyLeg_C:SocketHousing_GEN_VARIABLE | False / True |
| redistribution-copy | **Body/BP_BeholderBodyLeg.BP_BeholderBodyLeg_C:SocketHousing_GEN_VARIABLE** | False / True |

Теперь наблюдаемое происхождение выбранного template уточнено: redistribution-copy читает SocketHousing из **original BodyLeg**, не из собственного package. BodyLeg-copy возвращает template собственного generated class. Это свидетельство пути выбранного объекта, не export FComponentKey/GUID или полный список override records. Для будущего reparent redistribution нужно сохранить обе hidden flags через новую copied-parent цепочку; запрещено автоматически создавать локальный override лишь ради совпадения флага `overridden`.

Все пять reads: same mesh SM_BeholderSocketBody, NoCollision/Movable, relative location x=-134.7878403 (округление данного details response), zero rotation/unit scale. Отдельного сырого JSON-архива этих пяти ответов не создано; таблица — документированная сводка, не дополнение к прежнему baseline hash. Новых asset writes/editor Python/compile/tests/PIE не было. Внутренние bindings/GUID и recovery policy остаются открыты.

### Дополнительные component reads и семантика override

Последующее read-only перечисление компонентов трёх staged BP показало по 13 компонентов: DefaultSceneRoot, Sleeve00…09, HeadModule, SocketHousing. У descendants source=SCS_Inherited, у telescope-copy source=SCS. Эти ответы **не включены в указанный выше JSON-архив**.

Существенное различие: у BodyLeg-copy и redistribution-copy SocketHousing `visible=false, overridden=true`, у telescope-copy `visible=true`. Общий relative location `[-134.78784028338913,0,0]`, scale `[1,1,1]`; наблюдаемые mesh/material совпадают. HeadModule attached к Sleeve09: location `[56,0,0]`, rotation `[-90,0,0]`, scale `[2.2222222222222223,2.2222222222222223,2.2222222222222223]`. Sleeve components: location `[104,0,0]`, zero rotation/unit scale. Это выбранные наблюдаемые поля, **не полный export templates**.

Source review уточнил границу `overridden`: `McpPropCdoComponents.h:41–65` ищет ближайший override по цепочке Blueprint→parents через `GetInheritableComponentHandler(false)` и `GetOverridenComponentTemplate(FComponentKey(Node))`, иначе возвращает собственный template узла. Чтение не создаёт handler. Флаг означает найденный override **где-то до владельца SCS node**, а не обязательно запись в самом inspected descendant. `McpPropCdoInspection.cpp:201–221` и `McpBPScsGet.cpp:43–55` используют этот helper и не возвращают владельца найденного override/его key GUID.

Следствие для будущего сравнения: требовать сохранения effective SocketHousing visibility=false у обоих descendants, но не приписывать каждому локальный override без отдельного evidence. Совпадение display names не доказывает сохранение FComponentKey при переходе к независимой копии parent. После reparent недопустимо объявлять успех лишь по component count или новому ParentClass.

Следующий ограниченный read scope: получить архивируемые component details и происхождение override/key, затем установить доступность read-only member owner/GUID/MathExpression bound-graph export. Поиск GetMemberGuid/GetMemberParentClass в просмотренной BlueprintGraph реализации не дал совпадений; это **не доказательство отсутствия всех путей экспорта**. Editor Python, новый exporter, reparent/repair и тесты этим source review не разрешены и не запускались.

- Metadata/details не экспортируют все inherited component templates и их overrides: собственный SCS у двух descendants пуст; не объявлять component-default capture полным.
- Inspect graph показывает readable node/pin descriptors, но не полную сериализацию UBlueprint/UK2Node internal member GUIDs, MathExpression bound subgraphs, всех editor-only свойств/объектов. Нельзя восстановить утерянные bindings только из отображаемого текста формулы.
- Snapshot охватывает собственные graphs двух копий. Тела inherited telescope и base BodyLeg/rig не экспортировались этим архивом; их предыдущий writer audit не равен побайтовому recovery backup.
- Reads выполнены последовательно без фиксации engine package revisions. Counts согласованы, но это не атомарный native snapshot и не доказательство отсутствия внешнего редактирования между reads.
- Архив не содержит runtime state/world identity/claims/actual-pose evidence, не удостоверяет rollback и не разрешает риск потери inherited defaults.

**До разрешённого reparent всё ещё нужны** полная ограниченная recovery/snapshot policy и capture inherited component overrides/member bindings, затем явный scope mutation+неизбежной compile+save. Этот baseline — материал для сравнения, не зелёный admission gate.

На этом шаге: только editor metadata/graph reads, архивирование их ответов и file hashes. Blueprint/rig functions, trace, tests, reparent, compilation, actors, PIE и motion не запускались; .uasset/.umap не менялись.
