// Helper to test at different breakpoints
export const breakpoints = {
  mobile: 375,
  tablet: 768,
  desktop: 1024,
  wide: 1440,
}

export function testResponsive(callback: (width: number) => void) {
  Object.values(breakpoints).forEach(width => {
    // Note: window.resizeTo may not work in all browsers
    // This is primarily for testing utilities
    if (typeof window !== 'undefined') {
      window.resizeTo(width, 800)
      callback(width)
    }
  })
}
