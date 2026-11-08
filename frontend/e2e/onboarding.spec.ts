import { expect, test } from '@playwright/test'

import { installApiMocks } from './mock-api'

test('onboarding: scanning the workspace adds a repository row', async ({ page }) => {
  const pageErrors: Error[] = []
  page.on('pageerror', (error) => pageErrors.push(error))

  await installApiMocks(page, { hasRepositoriesBeforeScan: false })

  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Дашборд' })).toBeVisible()
  await expect(
    page.getByText('Нет репозиториев по текущим фильтрам.'),
  ).toBeVisible()

  await page.getByRole('button', { name: 'Сканировать' }).click()

  await expect(page.getByRole('link', { name: 'alpha', exact: true })).toBeVisible()
  await expect(
    page.getByText('Нет репозиториев по текущим фильтрам.'),
  ).toHaveCount(0)

  expect(pageErrors).toEqual([])
})
