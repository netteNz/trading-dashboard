// Indicator instances are identified by fn + kwargs (EMA 20 ≠ EMA 50).
// Kwargs are compared with sorted keys so {a, b} and {b, a} match.

const kwKey = (kwargs) => {
  const kw = kwargs ?? {};
  return JSON.stringify(Object.keys(kw).sort().map(k => [k, kw[k]]));
};

export const sameInstance = (a, b) => a.fn === b.fn && kwKey(a.kwargs) === kwKey(b.kwargs);

export const hasInstance = (list, ind) => list.some(a => sameInstance(a, ind));

// Order-insensitive equality of two indicator lists.
export const sameSet = (a, b) =>
  a.length === b.length && a.every(x => hasInstance(b, x)) && b.every(x => hasInstance(a, x));
