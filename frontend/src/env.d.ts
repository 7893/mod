/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CHINA_MAP_GEOJSON_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
