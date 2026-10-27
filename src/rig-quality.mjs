/** Offline geometric preflight for Inochi2D authoring candidates.
 * Input is a TRIANGULATED POSE SNAPSHOT, not an INP/INX reader.
 * Geometry failures are necessary but insufficient evidence of visible quality.
 */
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const isFinitePoint = (p) => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite);
const area2 = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);

/** @returns {object} Deterministic mesh quality diagnostics. */
export function analyzePose(sample, { collapseRatio = 0.05, stretchRatio = 5 } = {}) {
  if (!sample || typeof sample !== 'object') throw new TypeError('sample must be an object');
  const { neutral, posed, triangles, canvas } = sample;
  if (!Array.isArray(neutral) || !Array.isArray(posed) || neutral.length < 3 || posed.length !== neutral.length)
    throw new TypeError('neutral and posed must have equally sized vertex arrays (at least 3 vertices)');
  if (![...neutral, ...posed].every(isFinitePoint)) throw new TypeError('vertices must be finite [x,y] pairs');
  if (!Array.isArray(triangles) || triangles.length === 0) throw new TypeError('triangles must be a nonempty index triplet array');
  if (canvas !== undefined && (!Array.isArray(canvas) || canvas.length !== 2 || !canvas.every(x => Number.isFinite(x) && x > 0)))
    throw new TypeError('canvas must be [width,height] positive numbers');
  if (!(collapseRatio > 0 && collapseRatio < 1) || !(stretchRatio > 1)) throw new RangeError('invalid collapse/stretch threshold');
  let inverted = 0, collapsed = 0, overstretched = 0, degenerateNeutral = 0;
  let minAreaRatio = Infinity, maxAreaRatio = 0;
  for (const tri of triangles) {
    if (!Array.isArray(tri) || tri.length !== 3 || tri.some(i => !Number.isInteger(i) || i < 0 || i >= neutral.length) || new Set(tri).size !== 3)
      throw new TypeError('each triangle must contain 3 distinct valid vertex indices');
    const n = area2(neutral[tri[0]], neutral[tri[1]], neutral[tri[2]]);
    const p = area2(posed[tri[0]], posed[tri[1]], posed[tri[2]]);
    if (Math.abs(n) <= 1e-9) { degenerateNeutral++; continue; }
    if (p * n <= 0) inverted++;
    const ratio = Math.abs(p / n);
    minAreaRatio = Math.min(minAreaRatio, ratio);
    maxAreaRatio = Math.max(maxAreaRatio, ratio);
    if (ratio < collapseRatio) collapsed++;
    if (ratio > stretchRatio) overstretched++;
  }
  let outsideCanvas = 0;
  if (canvas) for (const [x, y] of posed) if (x < 0 || y < 0 || x > canvas[0] || y > canvas[1]) outsideCanvas++;
  const issues = inverted + collapsed + overstretched + degenerateNeutral + outsideCanvas;
  return {
    part: sample.part ?? null,
    pose: sample.pose ?? null,
    vertices: neutral.length,
    triangles: triangles.length,
    inverted, collapsed, overstretched, degenerateNeutral, outsideCanvas,
    minAreaRatio: Number.isFinite(minAreaRatio) ? minAreaRatio : null,
    maxAreaRatio: Number.isFinite(maxAreaRatio) && maxAreaRatio > 0 ? maxAreaRatio : null,
    geometryPass: issues === 0,
  };
}

/** Compares failures, not aesthetic quality; baseline/candidate must use comparable pose samples. */
export function comparePoseCandidates(baseline, candidate) {
  if (baseline.pose !== candidate.pose || baseline.part !== candidate.part)
    throw new Error('candidate and baseline must have the same part and pose');
  const b = analyzePose(baseline);
  const c = analyzePose(candidate);
  const critical = x => x.inverted + x.collapsed + x.overstretched + x.degenerateNeutral + x.outsideCanvas;
  return {
    part: b.part, pose: b.pose, baseline: b, candidate: c,
    fewerGeometryDefects: critical(c) < critical(b),
    equivalentGeometryDefects: critical(c) === critical(b),
    warning: 'Geometric integrity alone cannot establish rigging quality, artist fidelity, or animation smoothness.',
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const file = process.argv[2];
  if (!file) {
    console.error('Usage: node src/rig-quality.mjs <pose-samples.json>');
    process.exitCode = 2;
  } else {
    try {
      const doc = JSON.parse(readFileSync(file, 'utf8'));
      const samples = Array.isArray(doc.samples) ? doc.samples : null;
      if (!samples?.length) throw new Error('Expected {"samples": [ ... ]}');
      const results = samples.map(sample => analyzePose(sample));
      process.stdout.write(`${JSON.stringify({ results, geometryPass: results.every(r => r.geometryPass) }, null, 2)}\n`);
      if (results.some(r => !r.geometryPass)) process.exitCode = 1;
    } catch (error) {
      console.error(error.message);
      process.exitCode = 2;
    }
  }
}
