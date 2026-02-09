// Accessibility testing utilities
// Note: Requires jest-axe to be installed for full functionality

export async function testAccessibility(container: HTMLElement): Promise<void> {
  // Basic accessibility checks
  const issues: string[] = []
  
  // Check for images without alt text
  const images = container.querySelectorAll('img')
  images.forEach((img, index) => {
    if (!img.getAttribute('alt') && !img.getAttribute('aria-label')) {
      issues.push(`Image ${index} missing alt text or aria-label`)
    }
  })
  
  // Check for buttons without labels
  const buttons = container.querySelectorAll('button')
  buttons.forEach((button, index) => {
    const hasText = button.textContent?.trim()
    const hasAriaLabel = button.getAttribute('aria-label')
    const hasTitle = button.getAttribute('title')
    
    if (!hasText && !hasAriaLabel && !hasTitle) {
      issues.push(`Button ${index} missing accessible label`)
    }
  })
  
  // Check for form inputs without labels
  const inputs = container.querySelectorAll('input, textarea, select')
  inputs.forEach((input, index) => {
    const id = input.getAttribute('id')
    const hasLabel = id && container.querySelector(`label[for="${id}"]`)
    const hasAriaLabel = input.getAttribute('aria-label')
    const hasAriaLabelledBy = input.getAttribute('aria-labelledby')
    
    if (!hasLabel && !hasAriaLabel && !hasAriaLabelledBy) {
      issues.push(`Input ${index} missing label`)
    }
  })
  
  if (issues.length > 0) {
    console.warn('Accessibility issues found:', issues)
    throw new Error(`Accessibility issues: ${issues.join(', ')}`)
  }
}
