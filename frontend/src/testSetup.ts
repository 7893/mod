import { config, enableAutoUnmount } from '@vue/test-utils'
import { afterEach, vi } from 'vitest'

// DOM unit tests inspect drawer content locally; browser tests exercise actual Teleport.
config.global.stubs.teleport = true
enableAutoUnmount(afterEach)
afterEach(() => { vi.unstubAllGlobals() })
