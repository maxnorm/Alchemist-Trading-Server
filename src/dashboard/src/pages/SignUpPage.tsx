import { Link } from 'react-router-dom'

export default function SignUpPage() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="w-full max-w-md px-4">
        <div className="bg-card border border-border rounded-sm p-8 text-center">
          <h1 className="text-2xl font-bold text-foreground mb-4">Invitation Required</h1>
          <p className="text-muted-foreground mb-6">
            You need a valid invitation to create an account. Please contact an administrator
            to receive an invitation link.
          </p>
          <p className="text-sm text-muted-foreground mb-6">
            If you already have an account, you can sign in instead.
          </p>
          <Link
            to="/sign-in"
            className="inline-block bg-orange-400 hover:bg-orange-300 text-primary-foreground font-medium py-2 px-6 rounded-sm transition-colors"
          >
            Go to Sign In
          </Link>
        </div>
      </div>
    </div>
  )
}
