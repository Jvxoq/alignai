export default function AuthLayout({ children }) {
  return (
    <div className="auth-layout">
      <div className="auth-brand">
        <h1>AlignAI</h1>
        <p>Feature alignment auditing powered by AI</p>
      </div>
      <main className="auth-main">{children}</main>
    </div>
  );
}