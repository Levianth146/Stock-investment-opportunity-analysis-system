import {describe, expect, it} from 'vitest';
import {bestIndex} from './ComparePage';

describe('bestIndex', () => {
  it('cao hơn là tốt hơn, R thấp hơn là tốt hơn', () => {
    expect(bestIndex([40, 70, 55])).toBe(1);
    expect(bestIndex([40, 70, 55], true)).toBe(0);
  });
  it('bỏ qua null và không tô khi chỉ có một giá trị', () => {
    expect(bestIndex([null, 60, undefined])).toBe(-1);
    expect(bestIndex([null, 60, 80])).toBe(2);
  });
});
