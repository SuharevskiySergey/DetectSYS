# Binding inspector — source-only спецификация, не запуск

Подготовлен [native reader design](BeholderOwnershipNativeReaderDesign.md): подтверждённые raw accessors, mutable-iterator риск и открытые raw-parent/traversal/loader границы. Native capability не создана; plugin source/build/install/run не выполнялись.

## Назначение и статус

Дополнить pre-reparent baseline внутренними references и происхождением component overrides. Пользовательское «продолжай» после предложения подготовки разрешает подготовку, **не editor execution, tests или reparent**. Реализация/доступность Python reflection не проверены запуском; этот документ не executable inspector и не готовый recovery backup.

## Ограничение входов

## Установленный source blocker: обычный Python getter недостаточен

Продолжен полный путь getter в локальном UE5.6:

1. `PythonScriptPlugin/Private/PyGenUtil.cpp:1417–1439` — deprecation handling и передача в PyUtil.
2. `PythonScriptPlugin/Private/PyUtil.cpp:816–839` — **до конверсии** вызывает `PropertyAccessUtil::CanGetPropertyValue`; при PermissionDenied выдаёт исключение, без чтения значения.
3. `Engine/Source/Runtime/CoreUObject/Private/UObject/PropertyAccessUtil.cpp:422–429` — разрешает только `CPF_Edit | CPF_BlueprintVisible | CPF_BlueprintAssignable`; иначе PermissionDenied/AccessProtected.

Таким образом, одного reflected UPROPERTY недостаточно. Проверенные объявления VariableReference, FunctionReference, BoundGraph, Records/ComponentKey не имеют этих разрешающих specifiers; FMemberReference поля с SaveGame также ими не наделены. Обычный `get_editor_property` этих raw полей **не является пригодным путём полного capture** при проверенных штатных declarations. Это source conclusion, не результат editor execution/автоматизированного теста; динамические изменения flags сторонним кодом не проверялись и не предлагаются.

Expression с EditAnywhere — отдельный случай: его потенциальная доступность не закрывает недоступный BoundGraph/member reference. Не запускать Python для заведомо неполного capture и не изменять property flags/access metadata ради обхода. Предыдущий вывод «C++ private/protected само по себе недостаточно» остаётся верным: фактический запрет здесь задают property flags в нижележащем getter.

**Статус подготовки:** Python-only полная реализация заблокирована до альтернативного подтверждённого read API. Следующий вариант — отдельно согласованный **source-only дизайн native read capability** с прямым C++ чтением raw references/override records, без resolve/Modify/compile/save. Это не разрешение менять EngineWire, собирать/устанавливать plugin или запускать reader. Native design также обязан проверить public read accessors, отсутствие lazy mutation, bounded graph traversal и rig coverage; нельзя обещать полный recovery export заранее.

## Allowlist

Шесть точных staged paths под `/Game/BeholderPrototype/OwnershipIsolation/`: BP_OwnershipTelescope, BP_OwnershipBodyLeg, BP_OwnershipRedistribution, BP_OwnershipHead, CR_OwnershipHead, BP_OwnershipBodyFixture.

Original parents для read-only происхождения: `/Game/BeholderPrototype/Telescopic/BP_BeholderTelescopic_Test`, `/Game/BeholderPrototype/Body/BP_BeholderBodyLeg`. Внешние references только записывать как paths; произвольно рекурсивно загружать зависимости запрещено. Control Rig имеет отдельную graph model: unsupported coverage у CR нельзя заменять нулевым числом K2 nodes.

## Подтверждённые локальным UE5.6 source поля

| Объект | Поля | Источник относительно Engine/Source |
|---|---|---|
| UK2Node_Variable | VariableReference | Editor/BlueprintGraph/Classes/K2Node_Variable.h:55–56 |
| UK2Node_CallFunction | FunctionReference | Editor/BlueprintGraph/Classes/K2Node_CallFunction.h:74–75 |
| FMemberReference | MemberParent, MemberScope, MemberName, MemberGuid, bSelfContext, bWasDeprecated | Runtime/Engine/Classes/Engine/MemberReference.h:68–95 |
| UK2Node_MathExpression | Expression | Editor/BlueprintGraph/Classes/K2Node_MathExpression.h:39–44 |
| UK2Node_Composite (parent MathExpression) | BoundGraph | Editor/BlueprintGraph/Classes/K2Node_Composite.h:29–30 |
| FComponentKey | OwnerClass, SCSVariableName, AssociatedGuid | Runtime/Engine/Classes/Engine/InheritableComponentHandler.h:57–65 |
| FComponentOverrideRecord | ComponentClass, ComponentTemplate, ComponentKey | тот же header:68–83 |
| UInheritableComponentHandler | Records | тот же header:170–171 |

Наличие UPROPERTY **не гарантирует** доступ через Python: поля member reference protected, component key private; нет подтверждения доступности wrappers/struct traversal. Не угадывать snake_case имена и не обходить ограничения вызовом setters. Объявление call-function FunctionReference подтверждено; его Python binding пока нет.

### Source review Python reflection: уточнение, не runtime проверка

Локальный `Engine/Plugins/Experimental/PythonScriptPlugin/Source/PythonScriptPlugin/Private/PyWrapperObject.cpp:749–849`: `get_editor_property` разрешает имя через wrapper metadata, ищет FProperty через Class->FindPropertyByName и передаёт его в PyGenUtil::GetPropertyValue. В данном lookup нет отдельного запрета по C++ protected/private. Аналогичный struct lookup в `PyWrapperStruct.cpp:1000–1031` использует ScriptStruct->FindPropertyByName. Следовательно, C++ access modifier **сам по себе не основание объявлять чтение невозможным**.

Это не доказательство полной Python доступности: нужны wrapper для конкретной структуры, успешная конверсия property value и проверка нижележащего PyGenUtil getter (включая property flags/metadata getter). Также ещё не подтверждены read-only входы для перечисления всех graphs/nodes, handler Records и rig model. В editor ничего не импортировалось/не вызывалось. До подтверждения этих границ не писать код, который заявляет complete capture; недоступность не заменять обходом через mutating resolve/refresh.

## Требуемый результат

- Header: schema version, UUID capture, engine version, точный allowlist, время начала/конца, последовательность reads; revisions и package dirty до/после только если есть подтверждённый read API. Не изображать атомарность без pinned revisions.
- Asset: path/class/parent, declared variables с VarGuid при доступности, own graph paths; отдельно ожидаемое/полученное покрытие inherited graphs и rig model.
- Node: graph path, object path/class, NodeGuid; raw variable/function member reference: parent path/null, scope/name/GUID/self-context/deprecated. NodeGuid и MemberGuid — разные поля. Null MemberParent при self-context допустим и не является ошибкой.
- MathExpression: raw Expression, BoundGraph path/null, полный bounded обход вложенных graphs с visited set и records внутренних nodes/references. Не преобразовывать GUID-формулы в display names и не rebuild expressions.
- Overrides: inspected BP, handler owner, template object path, ComponentKey owner/name/GUID; отдельно effective source по parent chain. Не подменять owner записи именем inspected descendant. Сохранить SocketHousing bVisible=False/bHiddenInGame=True у двух descendants.
- Каждое недоступное поле: status=unsupported/error, field path, причина. Null, пустой массив и недоступное чтение различать. Для лимита depth/nodes/bytes — truncated=true и точная незакрытая область. Любой critical unsupported/truncated оставляет capture incomplete.
- Output только в новый UUID JSON под Saved; без overwrite. Hash файла после записи — идентификатор артефакта, не native authentication.

## Запрещённые операции

Никаких Modify, setters, rename, refresh/reconstruct/rebind, resolve-member helpers с возможным обновлением mutable references, CreateOverride, import/paste/export clipboard, compile/save assets, parent writes, CDO.call_method/gameplay, rig solve, spawn, PIE. Не использовать DisplayTitle вместо raw binding. Не включать native plugin changes/build как автоматический fallback.

## Алгоритм допуска будущей реализации

1. Source/API-проверкой подтвердить read traversal Blueprint→graphs→nodes и структуры references. Если protected/private поля не доступны, записать конкретный blocker и предложить отдельно согласованный native reader; не запускать пробный editor Python под видом обычного чтения.
2. Подготовить код без выполнения, с allowlist, явными limits, visited set и fail-closed coverage. Провести source review отсутствия mutation helpers и скрытых resolves.
3. Отдельно запросить разрешение на один editor capture: только этот reader, перечисленные assets, UUID JSON, без compile/save/test/PIE. Предусмотреть остановку при unsupported, dirty/revision drift или ошибке; без автоматических repairs.
4. Отдельные tests требуют отдельного разрешения. Capture не даёт разрешение на reparent и не заменяет recovery backup: восстановление внутреннего состояния из JSON не реализовано.

## Открытая recovery граница

До reparent согласовать независимое сохранение исходного состояния copied packages и способ восстановления с учётом памяти редактора. Обратный reparent не rollback; raw file replacement при загруженных packages не безопасный автоматический restore. Не выполнять ни один из этих способов без отдельного согласования.
