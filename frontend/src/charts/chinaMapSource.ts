export interface ChinaMapGeoJsonFeature {
  type: 'Feature'
  properties: {
    name: string
    [key: string]: unknown
  }
  geometry: Record<string, unknown>
}

export interface ChinaMapGeoJson {
  type: 'FeatureCollection'
  features: ChinaMapGeoJsonFeature[]
}

type FetchLike = (
  input: string,
  init?: RequestInit,
) => Promise<Pick<Response, 'ok' | 'status' | 'json'>>

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function isChinaMapGeoJson(value: unknown): value is ChinaMapGeoJson {
  if (!isRecord(value) || value.type !== 'FeatureCollection' || !Array.isArray(value.features)) {
    return false
  }
  if (value.features.length === 0) return false

  return value.features.every((feature) => (
    isRecord(feature)
    && feature.type === 'Feature'
    && isRecord(feature.geometry)
    && isRecord(feature.properties)
    && typeof feature.properties.name === 'string'
    && feature.properties.name.trim().length > 0
  ))
}

export async function fetchChinaMapGeoJson(
  sourceUrl: string,
  signal?: AbortSignal,
  fetcher: FetchLike = fetch,
): Promise<ChinaMapGeoJson> {
  const url = sourceUrl.trim()
  if (!url) throw new Error('China map source URL is not configured')

  const response = await fetcher(url, {
    signal,
    credentials: 'same-origin',
    headers: { Accept: 'application/geo+json, application/json' },
  })
  if (!response.ok) throw new Error(`China map source returned HTTP ${response.status}`)

  const payload: unknown = await response.json()
  if (!isChinaMapGeoJson(payload)) {
    throw new Error('China map source is not a named GeoJSON FeatureCollection')
  }
  return payload
}
