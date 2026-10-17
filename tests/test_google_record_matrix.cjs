const test=require('node:test');
const assert=require('node:assert/strict');
const {compareRecords}=require('../scripts/google_record_matrix.cjs');

test('an identical record has no changed ranges',()=>{
  const result=compareRecords([1,2,3],[1,2,3]);
  assert.equal(result.equal,true);
  assert.deepEqual(result.difference_ranges,[]);
});

test('adjacent substitutions are grouped into half-open ranges',()=>{
  const result=compareRecords([1,2,3,4],[1,9,8,4]);
  assert.equal(result.common_prefix_bytes,1);
  assert.equal(result.common_suffix_bytes,1);
  assert.deepEqual(result.difference_ranges,[[1,3]]);
});

test('an insertion preserves an aligned suffix despite positional differences',()=>{
  const result=compareRecords([1,2,3],[1,8,2,3]);
  assert.equal(result.left_bytes,3);
  assert.equal(result.right_bytes,4);
  assert.equal(result.common_prefix_bytes,1);
  assert.equal(result.common_suffix_bytes,2);
  assert.equal(result.positional_difference_count,3);
});
