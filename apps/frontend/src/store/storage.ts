/** localStorage nếu thực sự hoạt động, else memory (test/SSR). Persist không được crash. */
export function resolveStorage(): Storage {
  try {
    const ls = globalThis.localStorage;
    if (ls && typeof ls.setItem === "function") return ls;
  } catch {
    /* localStorage bị chặn -> memory */
  }
  const mem = new Map<string, string>();
  return {
    get length() {
      return mem.size;
    },
    clear: () => mem.clear(),
    getItem: (k) => mem.get(k) ?? null,
    key: (i) => [...mem.keys()][i] ?? null,
    removeItem: (k) => void mem.delete(k),
    setItem: (k, v) => void mem.set(k, v),
  };
}
