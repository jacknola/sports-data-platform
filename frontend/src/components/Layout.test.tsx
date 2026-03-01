/**
 * Tests for src/components/Layout.tsx
 *
 * Verifies:
 * - All navigation items are rendered
 * - The active route receives the active class
 * - Children are rendered inside the main content area
 * - System status indicator is present
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Layout from './Layout'

function renderLayout(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Layout>
        <div data-testid="page-content">Page Content</div>
      </Layout>
    </MemoryRouter>
  )
}

describe('Layout', () => {
  describe('navigation items', () => {
    it('renders Dashboard link', () => {
      renderLayout()
      expect(screen.getByText('Dashboard')).toBeInTheDocument()
    })

    it('renders Best Bets link', () => {
      renderLayout()
      expect(screen.getByText('Best Bets')).toBeInTheDocument()
    })

    it('renders College Basketball link', () => {
      renderLayout()
      expect(screen.getByText('College Basketball')).toBeInTheDocument()
    })

    it('renders Agents link', () => {
      renderLayout()
      expect(screen.getByText('Agents')).toBeInTheDocument()
    })

    it('renders Analysis link', () => {
      renderLayout()
      expect(screen.getByText('Analysis')).toBeInTheDocument()
    })

    it('renders Settings link', () => {
      renderLayout()
      expect(screen.getByText('Settings')).toBeInTheDocument()
    })

    it('renders all 6 nav items', () => {
      renderLayout()
      // All nav links have an href, count the <a> tags in the sidebar
      const links = screen.getAllByRole('link')
      expect(links.length).toBeGreaterThanOrEqual(6)
    })
  })

  describe('branding', () => {
    it('renders the Sports AI heading', () => {
      renderLayout()
      expect(screen.getByText('Sports AI')).toBeInTheDocument()
    })

    it('renders the Intelligence Platform subtitle', () => {
      renderLayout()
      expect(screen.getByText('Intelligence Platform')).toBeInTheDocument()
    })
  })

  describe('children rendering', () => {
    it('renders children inside the main content area', () => {
      renderLayout()
      expect(screen.getByTestId('page-content')).toBeInTheDocument()
    })

    it('renders child text content', () => {
      renderLayout()
      expect(screen.getByText('Page Content')).toBeInTheDocument()
    })
  })

  describe('system status', () => {
    it('shows system status section', () => {
      renderLayout()
      expect(screen.getByText('System Status')).toBeInTheDocument()
    })

    it('shows operational status message', () => {
      renderLayout()
      expect(screen.getByText('All Systems Operational')).toBeInTheDocument()
    })
  })

  describe('active route highlighting', () => {
    it('Dashboard link has active styling on root path', () => {
      renderLayout('/')
      const dashboardLink = screen.getByText('Dashboard').closest('a')
      expect(dashboardLink?.className).toContain('bg-primary-50')
    })

    it('non-active links do not have active styling', () => {
      renderLayout('/')
      const betsLink = screen.getByText('Best Bets').closest('a')
      expect(betsLink?.className).not.toContain('bg-primary-50')
    })

    it('College Basketball link is active on /college-basketball path', () => {
      renderLayout('/college-basketball')
      const link = screen.getByText('College Basketball').closest('a')
      expect(link?.className).toContain('bg-primary-50')
    })
  })
})
