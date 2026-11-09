// Custom material expression. Inputs: LocalPosition, UV, Opening, MaxAperture.
// Main output: DeltaLocal. Additional Float3 output: NormalLocal.
const float Pi = 3.141592653589793;
const float RestAperture = 0.05;
float radius = max(length(LocalPosition), 0.0001);
float phi = atan2(LocalPosition.y, LocalPosition.x);
float surface = floor(UV.x / 2.0 + 0.00001);
float restTheta = acos(clamp(LocalPosition.z / radius, -1.0, 1.0));
float t = saturate((restTheta - RestAperture) / (Pi - RestAperture));
if (surface > 1.5) t = 0.0;
float aperture = saturate(Opening) * clamp(MaxAperture, 0.01, 1.4);
float theta = lerp(aperture, Pi, t);
float st = sin(theta), ct = cos(theta);
float sp = sin(phi), cp = cos(phi);
float3 radial = float3(st * cp, st * sp, ct);
float3 newPosition = radius * radial;
if (surface < 0.5) NormalLocal = radial;
else if (surface < 1.5) NormalLocal = -radial;
else NormalLocal = float3(-ct * cp, -ct * sp, st);
return newPosition - LocalPosition;
