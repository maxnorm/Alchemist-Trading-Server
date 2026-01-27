/**
 * Motion Token System
 * Centralized animation configuration for GSAP
 * All durations in seconds, all easings use GSAP syntax
 */

export const motion = {
  // Duration tokens
  duration: {
    instant: 0.1,
    fast: 0.2,
    normal: 0.3,
    slow: 0.5,
    slower: 0.8,
  },

  // Easing tokens (GSAP syntax)
  ease: {
    // Standard easings
    inOut: 'power2.inOut',
    out: 'power2.out',
    in: 'power2.in',
    
    // Specialized
    elastic: 'elastic.out(1, 0.5)',
    bounce: 'bounce.out',
    
    // Subtle for data-heavy UIs
    subtle: 'power1.out',
  },

  // Stagger tokens (for sequential animations)
  stagger: {
    tight: 0.05,
    normal: 0.1,
    loose: 0.15,
  },

  // Presets for common animations
  presets: {
    // Panel entrance (cards, modals, drawers)
    panelEnter: {
      duration: 0.3,
      ease: 'power2.out',
      opacity: 0,
      y: 20,
    },
    
    // Hover emphasis (very subtle)
    hoverEmphasis: {
      duration: 0.2,
      ease: 'power1.out',
      scale: 1.02,
    },
    
    // Drawer/modal transitions
    drawerSlide: {
      duration: 0.4,
      ease: 'power2.inOut',
      x: '100%',
    },
    
    // Fade transitions
    fade: {
      duration: 0.2,
      ease: 'power1.out',
      opacity: 0,
    },
  },
} as const

/**
 * Reduced motion check
 * Respects user's prefers-reduced-motion setting
 */
export const prefersReducedMotion = (): boolean => {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Get safe duration (returns 0 if reduced motion is preferred)
 */
export const getSafeDuration = (duration: number): number => {
  return prefersReducedMotion() ? 0 : duration
}
