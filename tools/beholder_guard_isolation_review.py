"""Standalone-tested planning-data reviewer; no filesystem, Unreal or install API.

Accepts decoded JSON DATA only. No result from this module authorizes work.
Reference lists describe requested review, not verified dependency closure.
"""
import re


SOURCES = {
    'telescope_base': '/Game/BeholderPrototype/Telescopic/BP_BeholderTelescopic_Test',
    'body_leg': '/Game/BeholderPrototype/Body/BP_BeholderBodyLeg',
    'redistribution_leg': '/Game/BeholderPrototype/Telescopic/BP_BeholderStageRedistribution_Test',
    'head_controller': '/Game/BeholderPrototype/BP_Lapa5_Head',
    'head_rig': '/Game/BeholderPrototype/CR_Lapa5_Head',
    'body_fixture': '/Game/BeholderPrototype/Body/BP_BeholderBody_Test',
}
_PATH = re.compile(r'/Game/(?:[A-Za-z0-9_]+/)+[A-Za-z0-9_]+\Z')
_TOP = {'schema', 'kind', 'dependencyClosureComplete', 'installationAuthorized',
        'executionAuthorized', 'motionAuthorized', 'nativeOwnershipImplemented',
        'assets', 'unresolvedInstallationGates', 'forbiddenAutomaticActions', 'evidenceBoundary'}
_ASSET = {'role', 'source', 'destination', 'referenceReview', 'guardBoundaries', 'preserve'}
_EDGE = {'kind', 'member', 'members', 'targetRole', 'unresolved'}
_KINDS = {'parent_class', 'component_class', 'graph_class_references',
          'inherited_member_ownership', 'self_member_ownership'}
_REQUIRED_REFERENCES = {
    'telescope_base': {
        ('component_class', 'head_controller', 'HeadModule.ChildActorClass'),
        ('graph_class_references', 'head_controller', ''),
        ('self_member_ownership', 'telescope_base', '')},
    'body_leg': {
        ('parent_class', 'telescope_base', ''),
        ('inherited_member_ownership', 'telescope_base', ''),
        ('graph_class_references', 'head_controller', '')},
    'redistribution_leg': {
        ('parent_class', 'body_leg', ''),
        ('graph_class_references', 'body_leg', ''),
        ('inherited_member_ownership', 'telescope_base', '')},
    'head_controller': {
        ('component_class', 'head_rig', 'HeadRig.ControlRigClass'),
        ('self_member_ownership', 'head_controller', '')},
    'head_rig': set(),
    'body_fixture': {
        ('graph_class_references', 'telescope_base', ''),
        ('graph_class_references', 'body_leg', '')},
}
_REQUIRED_BOUNDARIES = {
    'telescope_base': {'public_command_entry', 'update_before_state_write',
                       'construction_snap', 'ApplyExtension'},
    'body_leg': {'parent_event_handoff', 'probe_revision_and_provenance',
                 'public_derived_plan_writer'},
    'redistribution_leg': {'start_reverse_entry', 'public_updater_entry',
                           'ApplyRedistribution0', 'ApplyRedistribution5',
                           'Cancel_Abort_Release', 'parent_tick_and_construction'},
    'head_controller': {'public_command_entry', 'PreForwardsSolve_before_state_write',
                        'eyelid_material_write', 'mapped_mesh_output_and_reset'},
    'head_rig': {'ForwardsSolve', 'RotateClaw0', 'RotateClaw1', 'RotateClaw2'},
    'body_fixture': {'multi_leg_admission_before_first_goal', 'per_leg_outcomes',
                     'Hold_Component_Index_identity', 'Abort_Cancel_Release',
                     'watch_startup', 'watchdog_tick'},
}
_RIG_PRESERVE = {'sphere_center_pivot_compensation', 'bone_mapping', 'no_shared_rig_edits'}


def review_isolation_manifest(manifest):
    """Return detached issue DATA, never an executable batch or approval.

    Even an empty planning issue list cannot certify real copied assets, graph
    remapping, owner authentication, physical stop or installation readiness.
    """
    issues = []

    def issue(code, pointer):
        issues.append({'code': code, 'pointer': pointer})

    def strings(value):
        return type(value) is list and bool(value) and all(type(x) is str and x for x in value)

    if type(manifest) is not dict:
        issue('object_required', '/')
    else:
        if set(manifest) != _TOP:
            issue('top_level_fields_mismatch', '/')
        if manifest.get('schema') != 'beholder.guard-isolation-plan.v1':
            issue('schema_mismatch', '/schema')
        if manifest.get('kind') != 'planning_data_only':
            issue('planning_data_required', '/kind')
        for name in ('dependencyClosureComplete', 'installationAuthorized', 'executionAuthorized',
                     'motionAuthorized', 'nativeOwnershipImplemented'):
            if manifest.get(name) is not False:
                issue('unsubstantiated_readiness_or_authorization', '/'+name)
        for name in ('unresolvedInstallationGates', 'forbiddenAutomaticActions'):
            if not strings(manifest.get(name)):
                issue('nonempty_string_list_required', '/'+name)
        if type(manifest.get('evidenceBoundary')) is not str or not manifest['evidenceBoundary']:
            issue('evidence_boundary_required', '/evidenceBoundary')
        assets = manifest.get('assets')
        seen, destinations = set(), set()
        protected = {path.casefold() for path in SOURCES.values()}
        if type(assets) is not list:
            issue('asset_list_required', '/assets')
            assets = []
        for index, asset in enumerate(assets):
            pointer = '/assets/'+str(index)
            if type(asset) is not dict:
                issue('asset_object_required', pointer)
                continue
            if set(asset)-_ASSET or not (_ASSET-{'preserve'}).issubset(asset):
                issue('asset_fields_mismatch', pointer)
            role = asset.get('role')
            if type(role) is not str or role not in SOURCES:
                issue('unknown_role', pointer+'/role')
                continue
            if role in seen:
                issue('duplicate_role', pointer+'/role')
            seen.add(role)
            if asset.get('source') != SOURCES[role]:
                issue('source_mismatch', pointer+'/source')
            destination = asset.get('destination')
            if destination is None:
                issue('destination_unresolved', pointer+'/destination')
            elif type(destination) is not str or not _PATH.fullmatch(destination):
                issue('canonical_package_path_required', pointer+'/destination')
            else:
                folded = destination.casefold()
                if folded in protected:
                    issue('destination_is_protected_source', pointer+'/destination')
                if folded in destinations:
                    issue('duplicate_destination', pointer+'/destination')
                destinations.add(folded)
            if not strings(asset.get('guardBoundaries')):
                issue('guard_boundaries_required', pointer+'/guardBoundaries')
            elif not _REQUIRED_BOUNDARIES[role].issubset(asset['guardBoundaries']):
                issue('required_guard_boundary_missing', pointer+'/guardBoundaries')
            if 'preserve' in asset and not strings(asset['preserve']):
                issue('preserve_list_invalid', pointer+'/preserve')
            if role == 'head_rig' and (not strings(asset.get('preserve'))
                                       or not _RIG_PRESERVE.issubset(asset['preserve'])):
                issue('rig_preservation_requirement_missing', pointer+'/preserve')
            edges = asset.get('referenceReview')
            if type(edges) is not list:
                issue('reference_list_required', pointer+'/referenceReview')
                continue
            if role != 'head_rig' and not edges:
                issue('reference_review_missing', pointer+'/referenceReview')
            slots_seen, reference_signatures = False, set()
            for edge_index, edge in enumerate(edges):
                ep = pointer+'/referenceReview/'+str(edge_index)
                if type(edge) is not dict:
                    issue('reference_object_required', ep)
                    continue
                if set(edge)-_EDGE:
                    issue('unknown_reference_fields', ep)
                kind, target = edge.get('kind'), edge.get('targetRole')
                if type(kind) is not str or kind not in _KINDS:
                    issue('reference_kind_invalid', ep+'/kind')
                if type(target) is not str or target not in SOURCES:
                    issue('reference_target_unresolved', ep+'/targetRole')
                member = edge.get('member', '')
                if type(kind) is str and type(target) is str and type(member) is str:
                    signature = (kind, target, member)
                    if signature in reference_signatures:
                        issue('duplicate_reference', ep)
                    reference_signatures.add(signature)
                if kind != 'component_class' and ('member' in edge or 'members' in edge):
                    issue('unexpected_member_selector', ep)
                if kind == 'component_class':
                    if role == 'body_fixture':
                        if slots_seen:
                            issue('duplicate_body_slot_selection', ep)
                        slots_seen = True
                        members = edge.get('members')
                        expected = ['Leg'+str(i)+'.ChildActorClass' for i in range(8)]
                        if members != expected:
                            issue('eight_ordered_slots_required', ep+'/members')
                        if target not in ('body_leg', 'redistribution_leg'):
                            issue('slot_class_selection_unresolved', ep+'/targetRole')
                        if 'member' in edge:
                            issue('unexpected_member_selector', ep+'/member')
                    elif type(edge.get('member')) is not str or not edge['member']:
                        issue('component_member_required', ep+'/member')
                    elif 'members' in edge:
                        issue('unexpected_member_selector', ep+'/members')
            if not _REQUIRED_REFERENCES[role].issubset(reference_signatures):
                issue('required_reference_missing', pointer+'/referenceReview')
            if role == 'body_fixture' and not slots_seen:
                issue('body_slots_missing', pointer+'/referenceReview')
        for role in sorted(set(SOURCES)-seen):
            issue('required_role_missing', '/assets/'+role)
        # These are deliberately open decisions, never erased by a path edit.
        if type(manifest.get('unresolvedInstallationGates')) is list:
            for index in range(len(manifest['unresolvedInstallationGates'])):
                issue('installation_gate_unresolved', '/unresolvedInstallationGates/'+str(index))
    return {
        'kind': 'local_planning_review',
        'issues': issues,
        'planningFieldsConsistent': not issues,
        'dependencyClosureVerified': False,
        'nativeOwnershipAuthenticated': False,
        'installationReady': False,
        'installationAuthorized': False,
        'executionAuthorized': False,
        'motionAuthorized': False,
    }
