import { SignIn } from '@clerk/clerk-react'

export default function SignInPage() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="w-full max-w-md px-4">
        <SignIn
          routing="path"
          path="/sign-in"
        />
      </div>
    </div>
  )
}
