export const GoogleButton = () => {
  const handleClick = () => {
    const apiBaseUrl = process.env.REACT_APP_API_URL || process.env.NEXT_PUBLIC_API_URL || "https://onrender.com";
    const clientId = process.env.REACT_APP_GOOGLE_CLIENT_ID || process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    const redirectUri = `${apiBaseUrl}/api/auth/callback/google`;
    
    // Construct a direct, secure handshake to Google with your own credentials
    window.location.href = `https://google.com{clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=code&scope=email%20profile`;
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      data-testid="google-signin-button"
      className="w-full h-11 inline-flex items-center justify-center gap-3 rounded-lg border border-slate-700 bg-slate-900/60 text-sm font-medium text-slate-100 hover:bg-slate-800 hover:border-slate-600 transition-colors"
    >
      <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true">
        <path fill="#EA4335" d="M12 10.2v3.9h5.5c-.24 1.4-1.7 4.1-5.5 4.1-3.3 0-6-2.7-6-6.1s2.7-6.1 6-6.1c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.8 3.5 14.6 2.5 12 2.5 6.8 2.5 2.6 6.7 2.6 12s4.2 9.5 9.4 9.5c5.4 0 9-3.8 9-9.2 0-.6-.1-1.1-.2-1.6H12Z" />
      </svg>
      Continue with Google
    </button>
  );
};
