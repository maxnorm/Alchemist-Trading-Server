import { ReactNode, useRef } from 'react'
import { useGSAP } from '@gsap/react'
import gsap from 'gsap'
import { motion, getSafeDuration } from '@/styles/motion'
import { cn } from '@/utils/cn'

export interface AnimatedPanelProps {
  children: ReactNode
  className?: string
  delay?: number
  disabled?: boolean
}

/**
 * AnimatedPanel - Wraps content with entrance animation
 * Uses GSAP with proper cleanup via useGSAP hook
 */
export function AnimatedPanel({
  children,
  className,
  delay = 0,
  disabled = false,
}: AnimatedPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null)

  useGSAP(() => {
    if (disabled || !panelRef.current) return

    const duration = getSafeDuration(motion.presets.panelEnter.duration)
    
    gsap.fromTo(
      panelRef.current,
      {
        opacity: 0,
        y: 20,
      },
      {
        opacity: 1,
        y: 0,
        duration,
        ease: motion.presets.panelEnter.ease,
        delay: getSafeDuration(delay),
      }
    )
  }, { scope: panelRef, dependencies: [disabled, delay] })

  return (
    <div ref={panelRef} className={cn(className)}>
      {children}
    </div>
  )
}

export interface AnimatedListProps {
  children: ReactNode[]
  className?: string
  stagger?: number
  disabled?: boolean
}

/**
 * AnimatedList - Animates list items with stagger effect
 */
export function AnimatedList({
  children,
  className,
  stagger = motion.stagger.normal,
  disabled = false,
}: AnimatedListProps) {
  const listRef = useRef<HTMLDivElement>(null)

  useGSAP(() => {
    if (disabled || !listRef.current) return

    const items = listRef.current.children
    const duration = getSafeDuration(motion.presets.panelEnter.duration)
    const staggerAmount = getSafeDuration(stagger)

    gsap.fromTo(
      items,
      {
        opacity: 0,
        y: 10,
      },
      {
        opacity: 1,
        y: 0,
        duration,
        ease: motion.presets.panelEnter.ease,
        stagger: staggerAmount,
      }
    )
  }, { scope: listRef, dependencies: [disabled, stagger] })

  return (
    <div ref={listRef} className={cn(className)}>
      {children}
    </div>
  )
}
