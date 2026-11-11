"""Analytic interpolation-error bounds for ideal linear stage/angle paths.

For point p(f), f in [0,1], ||p''||<=B implies deviation from the chord
between neighbouring samples <=B*h*h/8. No runtime or general collision proof.
"""
import math

from beholder_contact_ik import forward_contact
from beholder_support_polygon import finite_vector
from generate_beholder_telescope import COUNT, LENGTH, STROKE, radius


def point_curvature_bound(initial_stages, final_stages, final_angles, local_point, sleeve_index=COUNT-1):
    """Bound second derivative w.r.t. interpolation FRACTION, not time.

    Ri(f)=Rz(f*yaw)*Ry(-f*pitch). With Wi=sum(|pitch|+|yaw|) in radians
    through joint i: ||Qi'||<=Wi and ||Qi''||<=Wi**2. A linear stroke
    contributes STROKE*(max(stage)*Wi**2+2*abs(deltaStage)*Wi).
    The rigid terminal offset contributes ||offset||*Wlast**2.
    """
    initial_stages, final_stages = tuple(initial_stages), tuple(final_stages)
    final_angles = tuple(tuple(a) for a in final_angles)
    point = finite_vector(local_point, 3)
    forward_contact(initial_stages, [(0, 0)]*COUNT, point, sleeve_index)
    forward_contact(final_stages, final_angles, point, sleeve_index)
    angular, terms = 0.0, []
    for i in range(sleeve_index+1):
        angular += math.radians(abs(final_angles[i][0])+abs(final_angles[i][1]))
        terms.append(STROKE*(max(initial_stages[i], final_stages[i])*angular*angular
                             +2*abs(final_stages[i]-initial_stages[i])*angular))
    terms.append(math.hypot(*point)*angular*angular)
    bound = math.fsum(terms)
    if not math.isfinite(bound):
        raise ValueError('Curvature bound exceeds numeric range')
    # Engineering rounding cushion, not interval-arithmetic floating-point proof.
    return bound*(1+1e-12)+1e-12


def contact_plane_certificate(initial_stages, final_stages, final_angles, contact_tip,
                              claw_vertices_tip, sphere_center_tip, world_scale_bound,
                              sample_rows, contact_tolerance, plane_tolerance, numerical_cushion=1e-8):
    """Conservative all-fraction contact/plane bounds from exact-path samples.

    Caller must supply samples from the SAME linear stages/angles/body path.
    Uniformly translating the body adds zero second derivative. The world
    basis must be orthogonal, bounded in norm by world_scale_bound.
    """
    if not math.isfinite(world_scale_bound) or not 0 < world_scale_bound <= 1e8:
        raise ValueError('Positive bounded world scale required')
    if any(not math.isfinite(t) or not 0 <= t <= 1 for t in (contact_tolerance, plane_tolerance)):
        raise ValueError('Finite tolerances in 0..1 cm required')
    if not math.isfinite(numerical_cushion) or numerical_cushion < 1e-8:
        raise ValueError('Finite numerical cushion at least 1e-8 cm required')
    vertices = [finite_vector(v, 3) for v in claw_vertices_tip]
    if len(vertices) != 12:
        raise ValueError('Twelve claw vertices required')
    center = finite_vector(sphere_center_tip, 3)
    rows = list(sample_rows)
    if len(rows) < 2 or rows[0]['fraction'] != 0 or rows[-1]['fraction'] != 1:
        raise ValueError('Ordered samples including fractions 0 and 1 required')
    for row in rows:
        if any(not math.isfinite(row[k]) for k in ('fraction', 'contactDriftCm', 'headPlaneMinimumCm', 'sleevePlaneMinimumCm')):
            raise ValueError('Finite sample metrics required')
        if row['contactDriftCm'] < 0:
            raise ValueError('Nonnegative contact drift required')
    gaps = [b['fraction']-a['fraction'] for a, b in zip(rows, rows[1:])]
    if any(h <= 0 for h in gaps):
        raise ValueError('Strictly increasing sample fractions required')
    h = max(gaps)

    def curvature(point, index=COUNT-1):
        return world_scale_bound*point_curvature_bound(initial_stages, final_stages, final_angles, point, index)

    bounds = dict(contact=curvature(contact_tip), head=max(curvature(p) for p in vertices+[center]),
                  sleeves=max(curvature((-LENGTH, radius(i), 0), i) for i in range(COUNT)))
    # Plane normals accepted by the sampler may differ from unit norm by 1e-6.
    # Include that tolerance and an explicit engineering numeric cushion.
    errors = {name: value*h*h/8*(1 if name == 'contact' else 1.000001)+numerical_cushion
              for name, value in bounds.items()}
    upper = max(r['contactDriftCm'] for r in rows)+errors['contact']
    head_lower = min(r['headPlaneMinimumCm'] for r in rows)-errors['head']
    sleeve_lower = min(r['sleevePlaneMinimumCm'] for r in rows)-errors['sleeves']
    contact_pass, head_pass, sleeves_pass = upper <= contact_tolerance, head_lower >= -plane_tolerance, sleeve_lower >= -plane_tolerance
    return dict(contactAndPlaneBoundPasses=contact_pass and head_pass and sleeves_pass,
                contactBoundPasses=contact_pass, headPlaneBoundPasses=head_pass, sleevePlaneBoundPasses=sleeves_pass,
                maximumFractionGap=h, curvatureBoundsWorldCm=bounds, betweenSampleErrorWorldCm=errors,
                numericalCushionWorldCm=numerical_cushion, formalIntervalArithmetic=False,
                contactDriftUpperBoundCm=upper, headPlaneLowerBoundCm=head_lower, sleevePlaneLowerBoundCm=sleeve_lower,
                assumesExactLinearInterpolation=True, runtimeCertified=False,
                continuousCollisionCertified=False, motionAuthorized=False)
