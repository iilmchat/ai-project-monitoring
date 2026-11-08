import { expect, test } from '@playwright/test'

import { installApiMocks } from './mock-api'

test('settings: language switches to English and theme switches to dark', async ({
  page,
}) => {
  await installApiMocks(page)

  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: 'Настройки' })).toBeVisible()

  await page.getByRole('button', { name: 'EN', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem('iiruchating.locale')))
    .toBe('en')

  await page.getByRole('button', { name: 'Toggle theme' }).click()
  await expect(page.locator('html')).toHaveClass(/dark/)
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem('theme')))
    .toBe('dark')

  await page.reload()
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()
  await expect(page.locator('html')).toHaveClass(/dark/)
})
