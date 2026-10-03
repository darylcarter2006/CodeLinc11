/* Browser storage under "cc-" keys. Wrapped because storage can be unavailable (private mode, blocked). */

export const storage = {
  get<T>(key: string): T | null {
    try {
      return JSON.parse(localStorage.getItem('cc-' + key) ?? 'null') as T | null
    } catch {
      return null
    }
  },
  set(key: string, value: unknown): void {
    try {
      if (value == null) localStorage.removeItem('cc-' + key)
      else localStorage.setItem('cc-' + key, JSON.stringify(value))
    } catch {
      // Ignore: the app keeps working in memory.
    }
  },
}
