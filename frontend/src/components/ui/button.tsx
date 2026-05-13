import * as React from "react"

const Button = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: string, size?: string }>(
  ({ className = "", variant, size, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={`inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 border border-input bg-transparent hover:bg-accent hover:text-accent-foreground ${className}`}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button }
