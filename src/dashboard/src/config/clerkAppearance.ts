/**
 * Shared Clerk appearance configuration matching the terminal/print theme
 * 
 * Theme characteristics:
 * - Monochrome grayscale palette (mono-100 to mono-800)
 * - Orange accent (#E38B29) for primary actions
 * - Sharp corners (0.25rem border radius)
 * - Dark mode first with light mode support
 * - Uses CSS variables that automatically adapt to theme
 */
export const clerkAppearance = {
  elements: {
    // Root container
    rootBox: 'mx-auto w-full',
    
    // Card styling - matches our card component
    card: 'bg-card border border-border rounded-sm shadow-none',
    cardBox: 'bg-card',
    
    // Header styling
    headerTitle: 'text-foreground text-2xl font-bold',
    headerSubtitle: 'text-muted-foreground text-sm mt-2',
    
    // Primary button - uses orange accent
    formButtonPrimary: 
      'bg-orange-400 text-primary-foreground hover:bg-orange-300 rounded-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 focus-visible:ring-offset-2 focus-visible:ring-offset-background',
    
    // Secondary/reset button
    formButtonReset: 
      'text-muted-foreground hover:text-foreground',
    
    // Form field styling
    formFieldInput: 
      'bg-background border-border text-foreground rounded-sm focus:border-orange-400 focus:ring-2 focus:ring-orange-400 focus:ring-offset-0 transition-colors',
    formFieldLabel: 
      'text-foreground font-medium text-sm',
    formFieldInputShowPasswordButton: 
      'text-muted-foreground hover:text-foreground',
    
    // Social buttons - match secondary button style
    socialButtonsBlockButton: 
      'border border-border bg-card hover:bg-mono-300 text-foreground font-normal rounded-sm transition-colors',
    socialButtonsBlockButtonText: 
      'text-foreground font-normal',
    
    // Footer links
    footerActionLink: 
      'text-orange-400 hover:text-orange-300 font-medium',
    footerActionText: 
      'text-muted-foreground',
    
    // Identity preview (for multi-step flows)
    identityPreviewText: 
      'text-foreground',
    identityPreviewEditButton: 
      'text-orange-400 hover:text-orange-300',
    
    // Divider
    dividerLine: 
      'bg-border',
    dividerText: 
      'text-muted-foreground text-sm',
    
    // Form field row
    formFieldRow: 
      'gap-4',
    
    // Alert messages
    alertText: 
      'text-foreground text-sm',
    formFieldErrorText: 
      'text-destructive text-sm',
    
    // OTP input
    otpCodeFieldInput: 
      'border-border text-foreground bg-background focus:border-orange-400 focus:ring-2 focus:ring-orange-400 rounded-sm',
    
    // Select dropdown
    selectButton: 
      'border-border bg-background text-foreground hover:bg-mono-300 rounded-sm',
    selectOptionsContainer: 
      'bg-popover border border-border rounded-sm shadow-lg',
    selectOption: 
      'text-foreground hover:bg-mono-300',
    
    // Checkbox
    formFieldCheckbox: 
      'border-border text-orange-400 focus:ring-orange-400 rounded-sm',
    
    // User button (dropdown menu)
    userButtonPopoverCard: 
      'bg-popover border border-border rounded-sm shadow-lg',
    userButtonPopoverActionButton: 
      'text-foreground hover:bg-mono-300 rounded-sm',
    userButtonPopoverActionButtonText: 
      'text-foreground',
    userButtonPopoverActionButtonIcon: 
      'text-muted-foreground',
    userButtonPopoverFooter: 
      'border-t border-border',
    
    // Avatar
    avatarBox: 
      'rounded-sm',
    avatarImage: 
      'rounded-sm',
    
    // Badge
    badge: 
      'bg-orange-400 text-primary-foreground rounded-sm',
    
    // Navbar (for user button menu)
    navbar: 
      'bg-card border-b border-border',
    navbarButton: 
      'text-foreground hover:bg-mono-300 rounded-sm',
    
    // Menu items
    menuButton: 
      'text-foreground hover:bg-mono-300 rounded-sm',
    menuItem: 
      'text-foreground hover:bg-mono-300 rounded-sm',
    menuList: 
      'bg-popover border border-border rounded-sm shadow-lg',
    
    // Profile section
    profileSection: 
      'border-b border-border',
    profileSectionTitle: 
      'text-foreground font-medium',
    profileSectionContent: 
      'text-muted-foreground',
    profileSectionPrimaryButton: 
      'text-orange-400 hover:text-orange-300',
    
    // Page scrollbox
    pageScrollBox: 
      'bg-background',
    
    // Modal backdrop
    modalBackdrop: 
      'bg-mono-100/80 backdrop-blur-sm',
    modalContent: 
      'bg-card border border-border rounded-sm shadow-xl',
    
    // Breadcrumbs
    breadcrumbsItem: 
      'text-muted-foreground',
    breadcrumbsItemDivider: 
      'text-muted-foreground',
    breadcrumbsItemActive: 
      'text-foreground',
  },
  
  layout: {
    // Social buttons at the top for better UX
    socialButtonsPlacement: 'top' as const,
    
    // Hide optional fields by default for cleaner UI
    showOptionalFields: false,
  },
  
  variables: {
    // Border radius - sharp corners for technical feel
    borderRadius: '0.25rem',
    
    // Use CSS variables for colors (these will adapt to theme)
    colorPrimary: 'hsl(var(--orange-400))',
    colorDanger: 'hsl(var(--destructive))',
    colorSuccess: 'hsl(var(--success))',
    colorWarning: 'hsl(var(--warning))',
    
    colorBackground: 'hsl(var(--background))',
    colorInputBackground: 'hsl(var(--background))',
    colorInputText: 'hsl(var(--foreground))',
    
    colorText: 'hsl(var(--foreground))',
    colorTextSecondary: 'hsl(var(--muted-foreground))',
    colorTextOnPrimaryBackground: 'hsl(var(--primary-foreground))',
    
    // Spacing
    spacingUnit: '1rem',
    
    // Font
    fontFamily: 'inherit',
    fontFamilyButtons: 'inherit',
    fontSize: '0.875rem',
    fontWeight: {
      normal: '400',
      medium: '500',
      bold: '600',
    },
  },
}
