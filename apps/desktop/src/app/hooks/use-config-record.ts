import { useQuery } from '@tanstack/react-query'

import { getKopiConfigRecord } from '@/kopi'
import { queryClient, writeCache } from '@/lib/query-client'
import type { KopiConfigRecord } from '@/types/kopi'

// One shared cache for the whole profile config record (`GET /api/config`).
// Every settings surface (MCP, model, config) reads and writes through this key
// so a save in one shows in the others, and revisiting a tab paints the cache
// instead of blanking on a fresh fetch.
//
// Distinct from session/hooks/use-kopi-config.ts, which is side-effecting —
// it pushes personality/cwd/voice/… into the session stores for live chat.
export const KOPI_CONFIG_KEY = ['kopi-config-record'] as const

// staleTime 0 → serve cache instantly, background-revalidate on every mount.
export const useKopiConfigRecord = () =>
  useQuery({ queryKey: KOPI_CONFIG_KEY, queryFn: getKopiConfigRecord, staleTime: 0 })

export const setKopiConfigCache = writeCache<KopiConfigRecord>(KOPI_CONFIG_KEY)

export const invalidateKopiConfig = () => queryClient.invalidateQueries({ queryKey: KOPI_CONFIG_KEY })
