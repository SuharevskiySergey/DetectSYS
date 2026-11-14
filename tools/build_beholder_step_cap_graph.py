"""Non-idempotent optional per-native-Tick stage-step cap on isolated test BP.

Default 1 is unrestricted over normalised stage positions. Smaller positive
values slow controller time after a stall; unused wall time is never queued.
The setting is live: each Tick validates and applies its current value.
"""
import json

import build_beholder_redistribution_graph as forward
import build_beholder_uniform_return_graph as reverse

CAP_VALID = '(RedistributionMaxStageStep >= 0.001000) && (RedistributionMaxStageStep <= 1.000000)'
ELAPSED = ('min(RedistributionElapsed+min(dt,RedistributionMaxStageStep*RedistributionDuration/'
           'max(RedistributionExtension,1.000000-RedistributionExtension)),RedistributionDuration)')


def expression(ops, alias):
    return next(o['expression'] for o in ops if o.get('id') == alias)


def plans(ids):
    if set(ids) != {'time', 'elapsed', 'forward', 'reverse'} or any(not v for v in ids.values()):
        raise ValueError('Fresh inspected node IDs required')
    members = [dict(edit='add_variable', variableName='RedistributionMaxStageStep', variableType='float',
                    defaultValue=1, isPublic=True, category='Experimental Redistribution')]
    rows = [('UpdateStageRedistribution', 'time', '('+expression(forward.update(), 'time')+') && ('+CAP_VALID+')'),
            ('UpdateStageRedistribution', 'elapsed', ELAPSED),
            ('TryExperimentalStageRedistribution', 'forward', '('+expression(forward.request(), 'eligible')+') && ('+CAP_VALID+')'),
            ('TryExperimentalUniformRedistribution', 'reverse', '('+expression(reverse.request(), 'eligible')+') && ('+CAP_VALID+')')]
    edits = [dict(edit='set_node_property', graphName=g, nodeId=ids[key], propertyName='Expression', propertyValue=value)
             for g, key, value in rows]
    return dict(members=members, integration=edits)


if __name__ == '__main__':
    import sys
    print(json.dumps(plans(json.loads(sys.argv[1]))))
