import { useCallback, useEffect, useState } from 'react'

/** Load data on mount; `reload` fetches again after a change. */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const reload = useCallback(() => {
    setLoading(true)
    return load()
      .then((d) => {
        setData(d)
        setError(null)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
    // `deps` is the caller's dependency list, forwarded on purpose (like useEffect's own).
    // oxlint-disable-next-line react-hooks/exhaustive-deps, react/use-memo
  }, deps)

  useEffect(() => {
    reload()
  }, [reload])

  return { data, error, loading, reload, setData }
}

export const fmtDate = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('ko-KR') : '-')
