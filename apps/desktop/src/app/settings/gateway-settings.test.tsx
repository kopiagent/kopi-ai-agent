import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { atom } from 'nanostores'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ProfileInfo } from '@/types/kopi'

const getConnectionConfig = vi.fn()
const saveConnectionConfig = vi.fn()
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
  saveConnectionConfig.mockResolvedValue(localConnection)
  Object.defineProperty(window, 'kopiDesktop', {
    configurable: true,
    value: { getConnectionConfig, saveConnectionConfig }
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

  // KOPI: skipped by design. This upstream test mocks `mode: 'ssh'` to render the
  // SSH panel, but kopi's gateway-mode lock (KOPI_OFFERED_MODES + coerceOfferedMode)
  // coerces a saved 'ssh' mode onto an offered one, so the panel is unreachable in
  // this fork. The lock itself is covered by the 'offers only the local and remote
  // gateway modes' test below. Re-enable if kopi ever ships the SSH ModeCard.
  it.skip('shows and clears an SSH remote-profile mapping for a named Desktop profile', async () => {
    getConnectionConfig.mockImplementation(async profile =>
      profile === 'work'
        ? {
            ...localConnection,
            mode: 'ssh',
            profile: 'work',
            sshHost: 'remote-box',
            sshUser: 'alice',
            sshPort: 22,
            sshKeyPath: '',
            sshRemoteKopiPath: '/opt/kopi/bin/kopi',
            sshRemoteProfile: 'default'
          }
        : localConnection
    )
    saveConnectionConfig.mockReturnValue(new Promise(() => {}))
    const { GatewaySettings } = await import('./gateway-settings')

    render(<GatewaySettings />)
    fireEvent.click(await screen.findByRole('button', { name: 'work' }))

    await waitFor(() => expect(getConnectionConfig).toHaveBeenLastCalledWith('work'))
    expect(await screen.findByText('Remote profile (optional)')).toBeTruthy()

    const input = screen.getByPlaceholderText('work')

    expect((input as HTMLInputElement).value).toBe('default')
    fireEvent.change(input, { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save for next restart' }))

    await waitFor(() =>
      expect(saveConnectionConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          profile: 'work',
          sshRemoteProfile: ''
        })
      )
    )
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
})
