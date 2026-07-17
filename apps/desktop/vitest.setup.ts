import '@testing-library/react'

class MemoryStorage implements Storage {
  private data = new Map<string, string>()

  get length(): number {
    return this.data.size
  }

  clear(): void {
    this.data.clear()
  }

  getItem(key: string): string | null {
    return this.data.get(String(key)) ?? null
  }

  key(index: number): string | null {
    return Array.from(this.data.keys())[index] ?? null
  }

  removeItem(key: string): void {
    this.data.delete(String(key))
  }

  setItem(key: string, value: string): void {
    this.data.set(String(key), String(value))
  }
}

const ensureStorage = (name: 'localStorage' | 'sessionStorage') => {
  const target = globalThis.window ?? globalThis

  try {
    if (target[name]) {return}
  } catch {
    // Some environments expose a throwing storage getter.
  }

  Object.defineProperty(target, name, {
    configurable: true,
    value: new MemoryStorage()
  })
}

ensureStorage('localStorage')
ensureStorage('sessionStorage')

// React 19 + Testing Library 16: opt into the act environment so render(),
// fireEvent(), and findBy* queries automatically flush state updates without
// spurious "not wrapped in act(...)" warnings.
;(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true
