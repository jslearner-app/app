// Standard Google OAuth 2.0 (authorization code flow); the backend exchanges the code at /api/auth/google.
const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || process.env.REACT_APP_GOOGLE_CLIENT_ID;
export const GOOGLE_STATE_KEY = "ls_google_oauth_state";
export const googleRedirectUri = () => window.location.origin + "/auth/google";

export const GoogleButton = () => {
  const handleClick = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const state = crypto.randomUUID();
    sessionStorage.setItem(GOOGLE_STATE_KEY, state);
    const params = new URLSearchParams({
      client_id: GOOGLE_CLIENT_ID,
      redirect_uri: googleRedirectUri(),
      response_type: "code",
      scope: "openid email profile",
      state,
      prompt: "select_account",
    });
    window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={!GOOGLE_CLIENT_ID}
      title={GOOGLE_CLIENT_ID ? undefined : "Google sign-in isn't configured yet"}
      data-testid="google-signin-button"
      className="w-full h-11 inline-flex items-center justify-center gap-3 rounded-lg border border-slate-700 bg-slate-900/60 text-sm font-medium text-slate-100 hover:bg-slate-800 hover:border-slate-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    >
      <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true">
        <path fill="#EA4335" d="M12 10.2v3.9h5.5c-.24 1.4-1.7 4.1-5.5 4.1-3.3 0-6-2.7-6-6.1s2.7-6.1 6-6.1c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.8 3.5 14.6 2.5 12 2.5 6.8 2.5 2.6 6.7 2.6 12s4.2 9.5 9.4 9.5c5.4 0 9-3.8 9-9.2 0-.6-.1-1.1-.2-1.6H12Z" />
      </svg>
      Continue with Google
    </button>
  );
};
