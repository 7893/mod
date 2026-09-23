import { describe, expect, it, vi } from 'vitest'
import { fetchChinaMapGeoJson, isChinaMapGeoJson } from '../chinaMapSource.ts'

const VALID_GEOJSON = {
  type: 'FeatureCollection',
  features: [{
    type: 'Feature',
    properties: { name: '测试省域' },
    geometry: { type: 'Polygon', coordinates: [] },
  }],
}

describe('chinaMapSource', () => {
  it('accepts only named, non-empty GeoJSON feature collections', () => {
    expect(isChinaMapGeoJson(VALID_GEOJSON)).toBe(true)
    expect(isChinaMapGeoJson({ type: 'FeatureCollection', features: [] })).toBe(false)
    expect(isChinaMapGeoJson({ type: 'FeatureCollection', features: [{
      type: 'Feature',
      properties: {},
      geometry: { type: 'Polygon', coordinates: [] },
    }] })).toBe(false)
  })

  it('fetches a deployment-owned source without cross-origin credentials', async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => VALID_GEOJSON,
    })

    await expect(fetchChinaMapGeoJson(' https://maps.example.test/china.geojson ', undefined, fetcher))
      .resolves.toEqual(VALID_GEOJSON)
    expect(fetcher).toHaveBeenCalledWith('https://maps.example.test/china.geojson', {
      signal: undefined,
      credentials: 'same-origin',
      headers: { Accept: 'application/geo+json, application/json' },
    })
  })

  it('rejects an invalid response instead of registering arbitrary data', async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ type: 'Topology', objects: {} }),
    })

    await expect(fetchChinaMapGeoJson('/china.geojson', undefined, fetcher))
      .rejects.toThrow('named GeoJSON FeatureCollection')
  })
})
