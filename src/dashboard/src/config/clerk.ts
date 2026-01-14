export const clerkConfig = {
  publishableKey: import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || '',
}

if (!clerkConfig.publishableKey) {
  console.warn('VITE_CLERK_PUBLISHABLE_KEY is not set')
}
