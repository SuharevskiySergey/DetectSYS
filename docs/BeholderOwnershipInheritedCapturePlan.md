# Inherited override capture — source-only continuation after12/12

Latest separately authorized raw-link fix build + exact17 **17/17 Success**, zero per-test warnings/errors/exit0. Record-bearing ParentChain теперь проверен для two-layer synthetic handlers/records/templates→chain→DTO-review provenance/candidate и native/null/cycle/refusal/raw-wrapper/dirty checks. См. [receipt](BeholderOwnershipReaderVerificationPlan.md). Supersedes failed16/17 и unbuilt correction статусы только этой версии. НЕ реальный SCS/effective template/live key identity/full capture/recovery. Live binaries unchanged; новых исполнений этим результатом не разрешено.

Latest revised fixture verification: build successful, exact17 **16 Success/1 Fail (ParentChain raw-link assertion)**, не17/17; см. [receipt/diagnosis](BeholderOwnershipReaderVerificationPlan.md). Get-based assertion использовала TSubclassOf runtime IsChildOf на intentionally unlinked metadata class. Source-only заменена pre/post stored-wrapper проверкой; исправление не собрано/не запущено, повтор не разрешён. Record-bearing capture→review пока не считать подтверждённым целиком. Live reader/assets/binaries unchanged.

Source-review correction: отдельная ChainRecords заготовка имела неallowlisted paths. Без расширения reader allowlist она интегрирована в ParentChain с прежними paths; source-набор снова17, но ParentChain изменён и НЕ собран/НЕ запущен. Прежний17/17 receipt текущий fixture не удостоверяет. Null/cycle checks сохранены, reviewer для refused chains должен отказать. Следующий scope — отдельно разрешённая staging build + exact17 с record-bearing transient fixture, не18. Исторические18-case планы ниже superseded.

После17/17 source-only подготовлен отдельный ChainRecords fixture: два metadata-only BP слоя с own override records → chain reader → path-key reviewer, exact provenance и разные visibility/name payloads. **НЕ собран/НЕ запущен**; см. verification plan. Это bridge между ранее раздельными synthetic checks, не real SCS/effective template/native identity evidence. Следующий execution scope не разрешён generic continuation; live reader sources не изменены.

Latest verification: separately authorized staging build + exact17 isolated Automation **17/17 Success**, включая четыре pure DTO reviewer cases. Receipt и hashes: [verification plan](BeholderOwnershipReaderVerificationPlan.md). Historical unbuilt reviewer статусы ниже superseded для tested version. Подтверждены path-key grouping/provenance/duplicate conflict/unknown-key suppression/DTO budgets, НЕ live identity или effective selection. Следующий содержательный пробел — capture override records через несколько реальных слоёв synthetic chain с проверкой provenance; текущий ParentChain fixture records не содержит. SCS fallback, coherent lifetime/revision evidence и backup/restore остаются отдельными незакрытыми требованиями. Live install/capture/reparent не выполнялись; дальнейшие исполнения требуют разрешения.

## После13/13: pure DTO candidate review, НЕ проверен

Добавлены `McpBPOwnershipOverrideReview.h/.cpp`: pure ReviewOverridePathCandidates, без UObject access/resolve/loading. Это **owner-path+GUID grouping**, не engine identity certification; name игнорируется. Требует admitted NativeTerminal chain, ordered admitted layers1..8/max128records/240000owner-path TCHAR. Сохраняет layer/record provenance всех sources; ближайший уникальный snapshot record только Candidate. Duplicate same-layer key в любом ancestor → conflict и no candidate для группы (не last-write-wins). Uncomparable owner/GUID → no candidate для всех групп, потому что unknown key может совпасть с любым. bReviewed только завершение анализа DTO, bEngineIdentityVerified/bComplete всегдаfalse; SCS fallback и effective template не выбираются.

**Новые .h/.cpp не собраны/не запущены, tests ещё нет**. Прежние13/13 эту pure review не покрывают. No JSON/gameplay/reparent integration, live plugin/assets не менялись. До real capture/reparent нужен live identity/lifetime/revisions evidence, а не подстановка по path/name.

Последующая separately authorized staging build и exact13 isolated-host Automation verification **13/13 Success**, включая synthetic ParentChain native-terminal/null/cycle. См. verification receipt. Supersedes unbuilt chain status для этой версии; **не actual inherited override selection** (chain fixture без own records), не SCS fallback/full capture/recovery/project-asset validation. bComplete=false, live plugin unchanged.

## Последующая source-only реализация bounded chain

Добавлены FOverrideChainRead/FOverrideLayerRead/EChainStop и ReadOverrideChain в structure-reader .h/.cpp. **Не собраны/не запущены**, прошлые12/12 предшествуют этому коду. Принимает только loaded allowlisted BP; max8layers/128retained records/240000 text TCHARs. ParentClass читается typed FClassProperty direct-storage wrapper с schema/HasGetter/IsResolved gate, ClassGeneratedBy через resolved-gated Observe. Нет TSubclassOf::Get/GetGCPtr/const_cast/CDO/LoadObject/ResolveMember/key Match.

Own records каждого уровня сохранены отдельно; exact parent/generated-by paths и before/after dirty. Проверяется visited/cycle (включая последнее доступное depth), NullParent/Unresolved/Invalid/Unsupported/native terminal/limits/refused own-read/state drift. **OwnerUnavailable объединяет неразрешённый scope или недоступный editor/owner gate**, не удостоверяет исключительно внешнюю зависимость; предыдущий design «отдельный external статус» ещё не реализован полноценно. Уже захваченные pointer paths сохраняют provenance. При rejected own-read ParentClass storage дальше не читается.

Повторный post-check всех retained owners; bAccepted=true только при CLASS_Native terminal и совпавших доступных checks, **bComplete всегдаfalse**. Native terminal требует resolved generating-object=null + CLASS_Native, не просто null. Records не объединяются/не выбираются по names или DTO owner paths. SCS fallback/effective selection/revisions/lifetime остаются открыты. Новая версия source не даёт реального inherited baseline и не разрешает reparent. Нет новых build/tests/asset calls/install.

## Цель

Дополнить own-record reader ограниченным capture цепочки родителей перед будущим reparent. Сейчас цепочка/effective template не реализованы и не запускались;12/12 относятся к synthetic own records/raw member refs/graph subtree. Здесь нет разрешения на build/run/project asset capture/reparent.

## Подтверждённые UE5.6 детали

- Blueprint.h:412: ParentClass — **TSubclassOf<UObject>**, не непосредственно TObjectPtr. Обычный operator/Get нельзя выдавать за no-resolve read.
- Templates/SubclassOf.h:119–133: Get/operator->/conversion идут через dereference/type checking; единственный GetGCPtr:167–170 возвращает mutable reference, **const overload в просмотренном declaration отсутствует**. Не применять const_cast для чтения chain.
- Class.h:3023: UClass.ClassGeneratedBy — TObjectPtr<UObject>; gate IsResolved обязателен до Get/Cast/path.
- Предлагаемый ParentClass path — typed FClassProperty/FObjectProperty direct-storage wrapper getter с проверкой ArrayDim/HasGetter/schema, затем IsResolved; точный native field layout/тип сначала source-review. Не менять property flags и не создавать CDO/GeneratedClass/handler.
- **InheritableComponentHandler.cpp:595–598**: FComponentKey::Match сравнивает `(OwnerClass == OtherKey.OwnerClass) && (AssociatedGuid == OtherKey.AssociatedGuid)`. SCSVariableName в equality не участвует. Не вызывать Match как shortcut: сравнение TObjectPtr может разрешать handles. Для DTO сравнения использовать явно обозначенный owner identity evidence и GUID; path equality без live identity/revision не объявлять полной engine-key эквивалентностью.

## Предлагаемый bounded chain capture

1. Уже загруженный exact-allowlisted inspected BP, idle game thread. Не автоматически load ancestors/dependencies. Текущее own-record чтение остаётся отдельным primitive.
2. Для каждого layer хранить depth, inspected BP path, own records/handler observation, ParentClass observation, ClassGeneratedBy observation, before/after dirty и coverage. Максимум8layers, visited по live BP identity; native terminal/null/unresolved/external-owner/cycle/depth-limit различать.
3. Native parent с resolved ClassGeneratedBy=null — terminal, не «пустой Blueprint layer». Null ParentClass у BP — отдельное отсутствие данных/неполная иерархия, не доказательство успешного завершения.
4. Parent generated BP вне exact allowlist — external-reference record и stop, без расширения scope. Текущее copy hierarchy содержит original telescope/BodyLeg: они уже предусмотрены read allowlist; источники head/body fixture не добавлять автоматически.
5. ReadOwnOverrides каждого layer не создаёт handler. Null own handler **не означает** отсутствия inherited override. И наоборот, handler helper, скрытый config gate, не подменяет raw stored evidence.
6. После обхода повторно сверять editor/owner/dirty для **всех layers**, не только последнего. Даже совпадение dirty не доказывает atomic capture. Runtime revisions и GC lifetime остаются отдельными gates.

## Effective selection — не по display names

- Группировать только записи с подтверждёнными key owner+GUID; ближайший descendant record имеет приоритет **для того же key**, не для того же SCS имени.
- Unresolved/invalid owner, invalid GUID или неоднозначные same-layer duplicate keys → unknown/conflict, а не last-write-wins. Все исходные records сохранить, не схлопывать evidence.
- Переименование SCSVariableName при стабильном owner+GUID — metadata difference; совпадение имени при смене owner/GUID — binding difference. Это особенно существенно для независимых copied parents.
- Выбор из override records не охватывает fallback original SCS template. Если override нет, нужен отдельный captured SCS node/key/template baseline. Не выдавать records0 за visibility=true.
- До доказанного live key comparison не маркировать DTO-only owner-path match как engine-valid binding. Post-reparent исчезнувший old key с тем же display name в новом parent должен быть замечен, а не «исправлен» подстановкой по имени.

## SocketHousing acceptance boundary

Для redistribution-copy до reparent observed template path ведёт в original BodyLeg, flags VisibleFalse/HiddenTrue. Будущий layer snapshot должен показать конкретное происхождение, key owner/GUID и источник fallback/override. После reparent требуется отдельно обнаружить сохранение/утрату key binding и effective flags; нынешний synthetic RawRecord test не удостоверяет эту миграцию. Не создавать локальный override автоматически ради сходства картинки.

## Следующий шаг

Chain DTO/traversal и synthetic two-layer records→review уже прошли latest17/17 в указанном выше scope. Следующий gap — [raw SCS fallback evidence](BeholderOwnershipSCSCapturePlan.md): GetAllNodes const может менять registry; engine effective selection следует generated-class superclass/handler track, а не только BP.ParentClass. Нового SCS reader пока нет. Сначала source-only schema/budget design; новые compile/tests/real capture — только после отдельного согласования. Reparent/repair/full recovery по-прежнему не разрешены.
