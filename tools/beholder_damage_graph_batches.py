"""UNEXECUTED source-only preparation of one damage-graph batch at a time.

No Unreal/API access, plan generation, asset creation, compilation or retries.
Callers must supply actual GUIDs returned by successful prior editor batches.
"""
import copy
import re

from build_beholder_damage_snapshot_graph import BP, FUNCTION, HELPER


def _guid(value):
    if type(value) is not str or re.fullmatch(r'[0-9a-fA-F]{32}', value) is None:
        raise ValueError('Actual 32-hex editor node GUID required')
    return value.upper()


def prepare_next_batch(operations, *, entry_guid, return_guid, start_index=0,
                       node_guids=None, max_operations=200, graph_name=FUNCTION):
    """Prepare DATA only; no operation is considered applied by this function.

    start_index is advanced only by a caller AFTER confirmed editor success.
    node_guids maps original create-node aliases to confirmed editor GUIDs.
    Missing bindings reject preparation; there is no guessed GUID or auto-retry.
    """
    if type(operations) not in (list, tuple) or not operations:
        raise ValueError('Nonempty stored graph operation list required')
    if graph_name not in (FUNCTION, HELPER):
        raise ValueError('Only the two isolated damage calculator graphs are supported')
    if type(start_index) is not int or not 0 <= start_index < len(operations):
        raise ValueError('Start index must address an unapplied operation')
    if type(max_operations) is not int or not 1 <= max_operations <= 200:
        raise ValueError('Graph batch limit must be within 1..200')
    bindings = dict(node_guids or {})
    if 'entry' in bindings or 'entry_return' in bindings:
        raise ValueError('Entry/return bindings must be supplied explicitly')
    bindings.update(entry=_guid(entry_guid), entry_return=_guid(return_guid))
    for alias, guid in bindings.items():
        if type(alias) is not str or not alias:
            raise ValueError('Nonempty original graph alias required')
        bindings[alias] = _guid(guid)
    if len(set(bindings.values())) != len(bindings):
        raise ValueError('Distinct entry/return/prior-node aliases require distinct actual GUIDs')
    # Check original alias order without executing or generating any plan.
    prior_aliases = set()
    all_aliases = set()
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise ValueError('Each graph operation must be a mapping')
        if operation.get('edit') == 'create_node':
            alias = operation.get('id')
            if (type(alias) is not str or not alias or alias in all_aliases
                    or alias in ('entry', 'entry_return')):
                raise ValueError('Unique nonreserved create-node alias required')
            all_aliases.add(alias)
            if index < start_index:
                prior_aliases.add(alias)
    if any(alias not in prior_aliases for alias in bindings if alias not in ('entry', 'entry_return')):
        raise ValueError('Bindings may only describe nodes from prior confirmed operations')
    stop = min(start_index+max_operations, len(operations))
    local_aliases = set()

    def resolve(reference):
        if type(reference) is not str or not reference.startswith('$'):
            raise ValueError('Stored plan must reference nodes through original $aliases')
        alias = reference[1:]
        if alias in local_aliases:
            return reference
        if alias in bindings:
            return bindings[alias]
        raise ValueError('Missing confirmed GUID or earlier local node: '+alias)

    prepared = []
    for original in operations[start_index:stop]:
        operation = copy.deepcopy(original)
        edit = operation.get('edit')
        if edit not in ('create_node', 'connect_pins', 'set_pin_default_value'):
            raise ValueError('Unsupported operation in isolated damage calculator plan')
        if operation.get('graphName', graph_name) != graph_name:
            raise ValueError('Operation targets another graph')
        operation['graphName'] = graph_name
        if edit == 'create_node':
            local_aliases.add(operation['id'])
        if 'nodeId' in operation:
            operation['nodeId'] = resolve(operation['nodeId'])
        for shorthand, node_key, pin_key in (('from', 'fromNodeId', 'fromPinName'),
                                              ('to', 'toNodeId', 'toPinName')):
            if shorthand in operation:
                if node_key in operation or pin_key in operation:
                    raise ValueError('Mixed shorthand and explicit pin references')
                reference = operation.pop(shorthand)
                if type(reference) is not str or '.' not in reference:
                    raise ValueError('Expected $alias.PinName reference')
                node, pin = reference.split('.', 1)
                if not pin:
                    raise ValueError('Nonempty graph pin name required')
                operation[node_key], operation[pin_key] = resolve(node), pin
            elif node_key in operation:
                operation[node_key] = resolve(operation[node_key])
        prepared.append(operation)
    return dict(blueprintPath=BP, graphName=graph_name, operations=prepared,
                startIndex=start_index, nextIndexAfterConfirmedSuccess=stop,
                createdAliases=tuple(operation['id'] for operation in prepared
                                     if operation['edit'] == 'create_node'),
                completeAfterConfirmedSuccess=stop == len(operations),
                editorExecutionPerformed=False, installationConfirmed=False)


def prepare_complete_function(function_plan, *, entry_guid, return_guid):
    """Preferred path: refuse partial bodies instead of staging broken graphs."""
    operations = function_plan['operations']
    if len(operations) > 200:
        raise ValueError('Refactor the function; partial-body installation is not supported here')
    return prepare_next_batch(operations, graph_name=function_plan['graphName'],
                              entry_guid=entry_guid, return_guid=return_guid)
