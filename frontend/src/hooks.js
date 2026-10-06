import { useCallback, useEffect, useState } from 'react'
import { api } from './api/client'

// Custom hook: fetch `path` on mount (and when `query` changes) and expose
// { data, loading, error, reload }. Pages call reload() after a save.
export function useApi(path, query) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const queryKey = JSON.stringify(query || {})

  const reload = useCallback(async () => {
    if (!path) return
    setLoading(true)
    try {
      setData(await api.get(path, JSON.parse(queryKey)))
      setError(null)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [path, queryKey])

  useEffect(() => {
    reload()
  }, [reload])

  return { data, loading, error, reload }
}
