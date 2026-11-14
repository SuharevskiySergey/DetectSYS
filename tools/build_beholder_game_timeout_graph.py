"""Optional game-clock deadline for isolated redistribution, not wall time.

Non-idempotent layer over the installed step cap. Zero disables the deadline.
Each accepted direction captures a fresh start without recapturing contact.
"""
import json

from build_beholder_plane_graph import Plan
import build_beholder_step_cap_graph as cap

TIMEOUT_VALID = ('((RedistributionGameTimeout >= 0.000000) && (RedistributionGameTimeout <= 600.000000) && '
                 '((RedistributionGameTimeout == 0.000000) || (RedistributionGameTimeout >= 0.010000)))')
CLOCK_VALID = ('(game_now >= 0.000000) && (game_now <= 1000000000000.000000) && '
               '(RedistributionGameStart >= 0.000000) && (game_now >= RedistributionGameStart)')
WITHIN_BUDGET = ('((RedistributionGameTimeout == 0.000000) || '
                 '((game_now-RedistributionGameStart) <= RedistributionGameTimeout))')


def plans(ids):
    keys = {'time', 'elapsed', 'forward', 'reverse', 'forward_prev', 'forward_next', 'reverse_prev', 'reverse_next'}
    if set(ids) != keys or any(not v for v in ids.values()):
        raise ValueError('Fresh inspected IDs required')
    members = [dict(edit='add_variable', variableName=name, variableType='float', defaultValue=0,
                    isPublic=public, category='Experimental Redistribution')
               for name, public in [('RedistributionGameTimeout', True), ('RedistributionGameStart', False)]]
    edits = cap.plans({key: ids[key] for key in ('time', 'elapsed', 'forward', 'reverse')})['integration']
    edits = [op for op in edits if op['nodeId'] != ids['elapsed']]
    for op in edits:
        op['propertyValue'] = '('+op['propertyValue']+') && '+TIMEOUT_VALID
        if op['nodeId'] == ids['time']:
            op['propertyValue'] += ' && ('+CLOCK_VALID+') && '+WITHIN_BUDGET
    p = Plan('UpdateStageRedistribution')
    p.call('gameclock', 'GetGameTimeInSeconds', '/Script/Engine.KismetSystemLibrary')
    p.ops.append(dict(edit='connect_pins', **{'from': '$gameclock.ReturnValue',
                     'toNodeId': ids['time'], 'toPinName': 'game_now'}))
    edits += p.ops
    for key, graph in [('forward', 'TryExperimentalStageRedistribution'), ('reverse', 'TryExperimentalUniformRedistribution')]:
        p = Plan(graph)
        p.call('startclock', 'GetGameTimeInSeconds', '/Script/Engine.KismetSystemLibrary')
        p.setter('gamestart', 'RedistributionGameStart')
        p.wire('startclock.ReturnValue', 'gamestart.RedistributionGameStart')
        p.ops.append(dict(edit='connect_pins', fromNodeId=ids[key+'_prev'], fromPinName='then', to='$gamestart.execute'))
        p.ops.append(dict(edit='connect_pins', **{'from': '$gamestart.then',
                         'toNodeId': ids[key+'_next'], 'toPinName': 'execute'}))
        edits += p.ops
    return dict(members=members, integration=edits)


if __name__ == '__main__':
    import sys
    print(json.dumps(plans(json.loads(sys.argv[1]))))
