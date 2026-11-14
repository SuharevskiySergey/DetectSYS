"""Non-idempotent diagnostic-only native step telemetry on the isolated test BP.

Counters/maxima are lifetime values, not reset at direction changes. An observer
must capture the sample-count baseline for each accepted motion. No actuation.
"""
from build_beholder_plane_graph import Plan
from build_beholder_redistribution_graph import BP

PREFIX = 'RedistributionNativeStep'


def members():
    fields = [('Samples', 'int'), ('LastUpdate', 'int'), ('Direction', 'float'),
              ('Last', 'float'), ('Maximum', 'float'), ('MaximumExcess', 'float'),
              ('Violation', 'bool'), ('Invalid', 'bool')]
    return [dict(edit='add_variable', variableName=PREFIX+n, variableType=t,
                 defaultValue=False if t == 'bool' else 0, isPublic=True,
                 category='Experimental Redistribution Diagnostics') for n,t in fields]+[
        dict(edit='add_variable', variableName=PREFIX+f'Before{i}', variableType='float',
             defaultValue=0, isPublic=False, category='Experimental Redistribution Diagnostics') for i in range(10)]


def capture():
    p = Plan('CaptureRedistributionNativeStep')
    p.function('capture_entry')
    previous = 'capture_entry.then'
    for i in range(10):
        p.getter(f'capture_get{i}', f'Stage{i}Position')
        name = PREFIX+f'Before{i}'
        p.setter(f'capture_set{i}', name)
        p.wire(f'capture_get{i}.Stage{i}Position', f'capture_set{i}.{name}')
        p.wire(previous, f'capture_set{i}.execute')
        previous = f'capture_set{i}.then'
    return p.ops


def record():
    p = Plan('RecordRedistributionNativeStep')
    p.function('record_entry')
    delta = '0.000000'
    for i in range(10):
        delta = f'max({delta},abs(Stage{i}Position-{PREFIX}Before{i}))'
    valid = ' && '.join(f'({n} >= -0.000001) && ({n} <= 1.000001)'
                       for i in range(10) for n in (f'Stage{i}Position', PREFIX+f'Before{i}'))
    rows = [('Last', delta), ('Maximum', f'max({PREFIX}Maximum,{PREFIX}Last)'),
            ('MaximumExcess', f'max({PREFIX}MaximumExcess,max(0.000000,{PREFIX}Last-RedistributionMaxStageStep))'),
            ('Violation', f'{PREFIX}Violation || ({PREFIX}Last > RedistributionMaxStageStep+0.000002)'),
            ('Invalid', f'{PREFIX}Invalid || (({valid}) == false)'),
            ('LastUpdate', None), ('Direction', None), ('Samples', None)]
    previous = 'record_entry.then'
    for suffix, expression in rows:
        name = PREFIX+suffix
        alias = 'record_'+suffix
        if expression is not None:
            p.node(alias+'_value', 'MathExpression', expression=expression)
            source = alias+'_value.ReturnValue'
        elif suffix == 'Samples':
            p.getter(alias+'_get', name)
            p.call(alias+'_value', 'Add_IntInt', defaults={'B': 1})
            p.wire(alias+'_get.'+name, alias+'_value.A')
            source = alias+'_value.ReturnValue'
        else:
            member = 'RedistributionUpdates' if suffix == 'LastUpdate' else 'RedistributionDirection'
            p.getter(alias+'_get', member)
            source = alias+'_get.'+member
        p.setter(alias, name)
        p.wire(source, alias+'.'+name)
        p.wire(previous, alias+'.execute')
        previous = alias+'.then'
    return p.ops


def integration(ids):
    if set(ids) != {'self', 'progress', 'first', 'second', 'contact_after'} or any(not v for v in ids.values()):
        raise ValueError('Fresh inspected UpdateStageRedistribution node IDs required')
    p = Plan('UpdateStageRedistribution')
    p.call('audit_capture', 'CaptureRedistributionNativeStep', BP)
    p.call('audit_record', 'RecordRedistributionNativeStep', BP)
    # Existing exec outputs replace their old link; reconnect the same chain
    # through the new helpers, leaving every native guard/contact check intact.
    def wire(a, ap, b, bp):
        p.ops.append(dict(edit='connect_pins', graphName=p.graph,
                          fromNodeId=ids.get(a, '$'+a), fromPinName=ap,
                          toNodeId=ids.get(b, '$'+b), toPinName=bp))
    wire('self','self','audit_capture','self')
    wire('self','self','audit_record','self')
    wire('progress','then','audit_capture','execute')
    wire('audit_capture','then','first','execute')
    wire('second','then','audit_record','execute')
    wire('audit_record','then','contact_after','execute')
    return p.ops
