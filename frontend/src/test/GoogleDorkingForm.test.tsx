import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { GoogleDorkingForm } from '../components/pipelines/GoogleDorkingForm'
import type { GoogleDorkingConfig } from '../api/pipelines'

function renderForm(onSubmit = vi.fn(), loading = false) {
  render(<GoogleDorkingForm onSubmit={onSubmit} loading={loading} />)
  return { onSubmit }
}

describe('GoogleDorkingForm', () => {
  describe('keyword parsing', () => {
    it('parses newline-separated keywords', async () => {
      const onSubmit = vi.fn()
      renderForm(onSubmit)

      await userEvent.type(screen.getByRole('textbox', { name: /keywords/i }), 'leaked photos\nprivate videos')
      fireEvent.submit(screen.getByRole('button', { name: /run google dorking/i }).closest('form')!)

      await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
      const config: GoogleDorkingConfig = onSubmit.mock.calls[0][0]
      expect(config.keywords).toEqual(['leaked photos', 'private videos'])
    })

    it('parses comma-separated keywords', async () => {
      const onSubmit = vi.fn()
      renderForm(onSubmit)

      await userEvent.type(screen.getByRole('textbox', { name: /keywords/i }), 'leaked photos, private videos')
      fireEvent.submit(screen.getByRole('button', { name: /run google dorking/i }).closest('form')!)

      await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
      expect(onSubmit.mock.calls[0][0].keywords).toEqual(['leaked photos', 'private videos'])
    })

    it('parses mixed newline and comma keywords', async () => {
      const onSubmit = vi.fn()
      renderForm(onSubmit)

      await userEvent.type(screen.getByRole('textbox', { name: /keywords/i }), 'kw1,kw2\nkw3')
      fireEvent.submit(screen.getByRole('button', { name: /run google dorking/i }).closest('form')!)

      await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
      expect(onSubmit.mock.calls[0][0].keywords).toEqual(['kw1', 'kw2', 'kw3'])
    })

    it('trims whitespace from keywords', async () => {
      const onSubmit = vi.fn()
      renderForm(onSubmit)

      await userEvent.type(screen.getByRole('textbox', { name: /keywords/i }), '  leaked  ,  private  ')
      fireEvent.submit(screen.getByRole('button', { name: /run google dorking/i }).closest('form')!)

      await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
      expect(onSubmit.mock.calls[0][0].keywords).toEqual(['leaked', 'private'])
    })

    it('shows an error and does not submit when keywords are empty', async () => {
      const onSubmit = vi.fn()
      renderForm(onSubmit)

      fireEvent.submit(screen.getByRole('button', { name: /run google dorking/i }).closest('form')!)

      expect(screen.getByText(/at least one keyword is required/i)).toBeInTheDocument()
      expect(onSubmit).not.toHaveBeenCalled()
    })
  })

  describe('default values', () => {
    it('submits with correct defaults', async () => {
      const onSubmit = vi.fn()
      renderForm(onSubmit)

      await userEvent.type(screen.getByRole('textbox', { name: /keywords/i }), 'test')
      fireEvent.submit(screen.getByRole('button', { name: /run google dorking/i }).closest('form')!)

      await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
      const config: GoogleDorkingConfig = onSubmit.mock.calls[0][0]
      expect(config.timeframe).toBe(30)
      expect(config.num_of_results).toBe(100)
      expect(config.verbatim).toBe(true)
      expect(config.sites).toEqual([])
      expect(config.clients).toEqual([])
      expect(config.rule_out).toEqual([])
    })
  })

  describe('sites field', () => {
    it('parses sites as a list', async () => {
      const onSubmit = vi.fn()
      renderForm(onSubmit)

      const textareas = screen.getAllByRole('textbox')
      // keywords is index 0, sites is index 1
      await userEvent.type(textareas[0], 'test')
      await userEvent.type(textareas[1], 'telegram.org\nt.me')
      fireEvent.submit(screen.getByRole('button', { name: /run google dorking/i }).closest('form')!)

      await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
      expect(onSubmit.mock.calls[0][0].sites).toEqual(['telegram.org', 't.me'])
    })

    it('passes empty list when sites field is blank', async () => {
      const onSubmit = vi.fn()
      renderForm(onSubmit)

      await userEvent.type(screen.getAllByRole('textbox')[0], 'test')
      fireEvent.submit(screen.getByRole('button', { name: /run google dorking/i }).closest('form')!)

      await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
      expect(onSubmit.mock.calls[0][0].sites).toEqual([])
    })
  })

  describe('UI state', () => {
    it('shows keyword badges as user types', async () => {
      renderForm()
      await userEvent.type(screen.getByRole('textbox', { name: /keywords/i }), 'leaked photos')
      // badge appears (there may also be placeholder text with same string — use getAllByText)
      expect(screen.getAllByText('leaked photos').length).toBeGreaterThanOrEqual(1)
    })

    it('disables the submit button while loading', () => {
      renderForm(vi.fn(), true)
      expect(screen.getByRole('button', { name: /starting pipeline/i })).toBeDisabled()
    })

    it('toggles advanced options section', async () => {
      renderForm()
      expect(screen.queryByText(/client \/ brand terms/i)).not.toBeInTheDocument()

      await userEvent.click(screen.getByText(/advanced options/i))
      expect(screen.getByText(/client \/ brand terms/i)).toBeInTheDocument()

      await userEvent.click(screen.getByText(/advanced options/i))
      expect(screen.queryByText(/client \/ brand terms/i)).not.toBeInTheDocument()
    })

    it('unchecking verbatim sets it to false', async () => {
      const onSubmit = vi.fn()
      renderForm(onSubmit)

      await userEvent.click(screen.getByRole('checkbox', { name: /verbatim/i }))
      await userEvent.type(screen.getByRole('textbox', { name: /keywords/i }), 'test')
      fireEvent.submit(screen.getByRole('button', { name: /run google dorking/i }).closest('form')!)

      await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
      expect(onSubmit.mock.calls[0][0].verbatim).toBe(false)
    })
  })
})
