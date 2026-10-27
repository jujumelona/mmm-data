import test from 'node:test';
import assert from 'node:assert/strict';
import { analyzePose, comparePoseCandidates } from '../src/rig-quality.mjs';

const sample = () => ({ part: 'head', pose: 'turn-right', neutral: [[0, 0], [10, 0], [0, 10]], posed: [[0, 0], [10, 0], [0, 10]], triangles: [[0, 1, 2]], canvas: [32, 32] });

test('geometry checker accepts unchanged healthy triangle', () => {
  const r = analyzePose(sample());
  assert.equal(r.geometryPass, true);
  assert.equal(r.inverted, 0);
});
test('geometry checker reports triangle fold-over', () => {
  const s = sample(); s.posed[2] = [0, -10];
  const r = analyzePose(s);
  assert.equal(r.inverted, 1);
  assert.equal(r.geometryPass, false);
});
test('geometry checker reports severe collapse', () => {
  const s = sample(); s.posed[2] = [0, 0.1];
  assert.equal(analyzePose(s).collapsed, 1);
});
test('geometry checker validates indices and finite coordinates', () => {
  const s = sample(); s.triangles = [[0, 1, 1]];
  assert.throws(() => analyzePose(s), /distinct/);
  const t = sample(); t.posed[2][1] = NaN;
  assert.throws(() => analyzePose(t), /finite/);
});
test('comparison does not claim artistic superiority', () => {
  const b = sample(); b.posed[2] = [0, -10];
  const c = sample();
  const r = comparePoseCandidates(b, c);
  assert.equal(r.fewerGeometryDefects, true);
  assert.match(r.warning, /cannot establish rigging quality/);
});
