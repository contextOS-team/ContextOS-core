// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ProfileTab } from './profile-tab'

const { updateUserMock } = vi.hoisted(() => ({
  updateUserMock: vi.fn(),
}))

vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      updateUser: updateUserMock,
    },
  }),
}))

describe('ProfileTab password sign-in', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    updateUserMock.mockResolvedValue({ error: null })
  })

  it('explains that password sign-in can be added without removing Google sign-in', () => {
    render(<ProfileTab userEmail="owner@example.com" userFullName="Owner" />)

    expect(screen.getByText('Set or change password')).toBeTruthy()
    expect(screen.getByText(/existing Google sign-in will continue to work/i)).toBeTruthy()
  })

  it('rejects passwords shorter than 12 characters', async () => {
    const user = userEvent.setup()
    render(<ProfileTab userEmail="owner@example.com" userFullName="Owner" />)

    await user.type(screen.getByLabelText('New password'), 'shortpass')
    await user.type(screen.getByLabelText('Confirm password'), 'shortpass')
    fireEvent.submit(screen.getByRole('button', { name: 'Set password' }).closest('form')!)

    expect(screen.getByText('Password must be at least 12 characters')).toBeTruthy()
    expect(updateUserMock).not.toHaveBeenCalled()
  })

  it('sets a password on the authenticated Supabase user', async () => {
    const user = userEvent.setup()
    render(<ProfileTab userEmail="owner@example.com" userFullName="Owner" />)

    await user.type(screen.getByLabelText('New password'), 'strong-password-2026')
    await user.type(screen.getByLabelText('Confirm password'), 'strong-password-2026')
    await user.click(screen.getByRole('button', { name: 'Set password' }))

    await waitFor(() => {
      expect(updateUserMock).toHaveBeenCalledWith({ password: 'strong-password-2026' })
    })
    expect(screen.getByText(/Password saved\. You can now sign in with owner@example\.com/i)).toBeTruthy()
  })
})
