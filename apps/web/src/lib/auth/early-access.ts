// Detects allowlist rejection from handle_new_user(). Supabase wraps the
// trigger error as either the raw message or "Database error saving new user"
// depending on SDK version, so match on either.
export function isEarlyAccessError(message: string | null | undefined): boolean {
  if (!message) return false
  const m = message.toLowerCase()
  return m.includes('early_access_required') || m.includes('database error saving new user')
}

export const EARLY_ACCESS_MESSAGE =
  "You're not on the early-access list yet. We'll let you know when a spot opens up."
