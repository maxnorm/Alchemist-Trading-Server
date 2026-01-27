import { Navigate } from 'react-router-dom'
import { useAuth, useUser } from '@clerk/clerk-react'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

interface ProtectedRouteProps {
  children: React.ReactNode
  requiredRoles?: string[]
}

export function ProtectedRoute({ children, requiredRoles }: ProtectedRouteProps) {
  const { isSignedIn, isLoaded } = useAuth()
  const { user, isLoaded: userLoaded } = useUser()

  // Show loading while checking authentication
  if (!isLoaded || !userLoaded) {
    return (
      <div className="flex items-center justify-center h-full">
        <LoadingSpinner />
      </div>
    )
  }

  // Redirect to sign-in if not authenticated
  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace />
  }

  // Check roles if required (kept for future use - currently all routes are accessible to authenticated users)
  // Roles are stored in Clerk public metadata as ["admin"] or ["user"]
  if (requiredRoles && user) {
    // Get roles from user's public metadata or organization memberships
    const userRoles = (user.publicMetadata?.roles as string[]) || []
    const hasRole = requiredRoles.some((role) => userRoles.includes(role))

    if (!hasRole) {
      return <Navigate to="/unauthorized" replace />
    }
  }

  return <>{children}</>
}
