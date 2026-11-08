import { expect, test } from '@playwright/test'

import { installApiMocks } from './mock-api'

test('ai commit: generated commit message is shown in the modal', async ({ page }) => {
  const commitMessage = 'feat: mocked commit message'

  const api = await installApiMocks(page, {
    dirty: true,
    llmEnabled: true,
    commitMessage,
  })

  await page.goto('/repo/1')
  await expect(page.getByRole('heading', { name: 'alpha', exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Сгенерировать коммит' }).click()

  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(dialog.locator('textarea')).toHaveValue(commitMessage)

  expect(api.commitMessageRequests()).toBe(1)
  expect(api.commitRequests()).toBe(0)
})
