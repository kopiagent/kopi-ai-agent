import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { atom } from 'nanostores'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ProfileInfo } from '@/types/kopi'

const getConnectionConfig = vi.fn()
const profiles = atom<ProfileInfo[]>([])

vi.mock('@/store/profile', () => ({
  $profiles: profiles,
  refreshActiveProfile: vi.fn()
}))

const localConnection = {
  cloudOrg: '',
  envOverride: false,
  mode: 'local',
  remoteAuthMode: 'token',
  remoteOauthConnected: false,
  remoteTokenPreview: null,
  remoteTokenSet: false,
  remoteUrl: ''
}

beforeEach(() => {
  profiles.set([
    {
      has_env: false,
      is_default: true,
      model: null,
      name: 'default',
      path: '/tmp/kopi',
      provider: null,
      skill_count: 0
    },
    {
      has_env: false,
      is_default: false,
      model: null,
      name: 'work',
      path: '/tmp/kopi/profiles/work',
      provider: null,
      skill_count: 0
    }
  ])
  getConnectionConfig.mockResolvedValue(localConnection)
  Object.defineProperty(window, 'kopiDesktop', {
    configurable: true,
    value: { getConnectionConfig }
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('GatewaySettings', () => {
  it('labels local mode as default inheritance for a named profile', async () => {
    const { GatewaySettings } = await import('./gateway-settings')

    render(<GatewaySettings />)
    expect(await screen.findByText('Local gateway')).toBeTruthy()
    expect(
      screen.getByText('Start a private Kopi backend on localhost. This is the default and works offline.')
    ).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'work' }))

    await waitFor(() => expect(getConnectionConfig).toHaveBeenLastCalledWith('work'))
    expect(await screen.findByText('Use default gateway')).toBeTruthy()
    expect(screen.getByText("Remove this profile's override and use the default connection.")).toBeTruthy()
    expect(
      screen.queryByText('Start a private Kopi backend on localhost. This is the default and works offline.')
    ).toBeNull()
  })

  // KOPI divergence: the picker offers Local + Remote only. Upstream ships two
  // more cards (Kopi Cloud, Connect via SSH); a sync that reintroduces them
  // must fail here rather than silently restoring modes we don't support.
  it('offers only the local and remote gateway modes', async () => {
    const { GatewaySettings } = await import('./gateway-settings')

    render(<GatewaySettings />)
    expect(await screen.findByText('Local gateway')).toBeTruthy()
    expect(screen.getByText('Remote gateway')).toBeTruthy()
    expect(screen.queryByText('Kopi Cloud')).toBeNull()
    expect(screen.queryByText('Connect via SSH')).toBeNull()
  })

  it('coerces a saved cloud connection onto the remote card', async () => {
    getConnectionConfig.mockResolvedValue({
      ...localConnection,
      mode: 'cloud',
      remoteUrl: 'https://agent.example.com'
    })
    const { GatewaySettings } = await import('./gateway-settings')

    render(<GatewaySettings />)
    // The hidden 'cloud' mode must not leave the picker without a selection.
    expect(await screen.findByText('Remote gateway')).toBeTruthy()
    expect(screen.queryByText('Kopi Cloud')).toBeNull()
  })
})
